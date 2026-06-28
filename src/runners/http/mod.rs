mod classify;
mod direct;
mod json;
mod replay;
mod request;

use defmt::{error, info, warn};
use embassy_net::Stack;
use embassy_net::tcp::TcpSocket;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::mutex::Mutex;
use embassy_time::{Duration, with_timeout};
use picoserve::{Config, DisconnectionInfo, Server, Timeouts};

use crate::net::AppRouter;
use crate::storage::StorageManager;

use classify::{StartupRequest, classify_startup_request, looks_like_http_request};
use direct::{
    serve_armory, serve_bootstrap, serve_empty_not_found, serve_keyboard_target, serve_no_content,
    serve_payload, serve_root_asset, serve_runs,
};
use replay::PrefilteredSocket;

pub(super) const HTTP_PREFLIGHT_BYTES: usize = 64;
const HTTP_PREFLIGHT_TIMEOUT_MS: u64 = 300;

#[embassy_executor::task]
pub(super) async fn server_task(
    stack: &'static Stack<'static>,
    router: &'static AppRouter,
    storage: &'static Mutex<CriticalSectionRawMutex, StorageManager>,
) {
    let config = Config::new(Timeouts {
        write: picoserve::time::Duration::from_secs(10),
        ..Timeouts::default()
    });

    let router = router.build();

    let mut rx_buffer = [0u8; 512];
    let mut tx_buffer = [0u8; 1024];
    let mut picoserve_buffer = [0u8; 2048];

    info!("HTTP worker initialised...");

    loop {
        let mut socket = TcpSocket::new(*stack, &mut rx_buffer, &mut tx_buffer);

        if let Err(e) = socket.accept(80).await {
            warn!("[Worker] Accept failed: {:?}", e);
            continue;
        }

        let remote_address = socket.remote_endpoint();
        info!("[Worker] Connected to {}", remote_address);

        let mut prefix = [0u8; HTTP_PREFLIGHT_BYTES];
        let prefix_len = match with_timeout(
            Duration::from_millis(HTTP_PREFLIGHT_TIMEOUT_MS),
            socket.read(&mut prefix),
        )
        .await
        {
            Ok(Ok(0)) => {
                info!("[Worker] Empty HTTP preflight; closing socket.");
                continue;
            }
            Ok(Ok(len)) => len,
            Ok(Err(e)) => {
                warn!("[Worker] HTTP preflight read failed: {:?}", e);
                continue;
            }
            Err(_) => {
                info!("[Worker] Idle HTTP preflight timed out; closing socket.");
                continue;
            }
        };

        if !looks_like_http_request(&prefix[..prefix_len]) {
            warn!("[Worker] Non-HTTP preflight rejected.");
            continue;
        }

        let request = classify_startup_request(&prefix[..prefix_len]);
        match request {
            StartupRequest::Root => {
                info!("[Worker] Serving root asset directly.");
                if let Err(e) = serve_root_asset(&mut socket).await {
                    warn!("[Worker] Root asset response failed: {:?}", e);
                }
                continue;
            }
            StartupRequest::Bootstrap => {
                info!("[Worker] Serving bootstrap directly.");
                if let Err(e) = serve_bootstrap(&mut socket).await {
                    warn!("[Worker] Bootstrap response failed: {:?}", e);
                }
                continue;
            }
            StartupRequest::Armory => {
                info!("[Worker] Serving armory directly.");
                if let Err(e) = serve_armory(&mut socket, storage).await {
                    warn!("[Worker] Armory response failed: {:?}", e);
                }
                continue;
            }
            StartupRequest::Payload => {
                info!("[Worker] Serving payload directly.");
                if let Err(e) = serve_payload(&mut socket, storage).await {
                    warn!("[Worker] Payload response failed: {:?}", e);
                }
                continue;
            }
            StartupRequest::Runs => {
                info!("[Worker] Serving runs directly.");
                if let Err(e) = serve_runs(&mut socket).await {
                    warn!("[Worker] Runs response failed: {:?}", e);
                }
                continue;
            }
            StartupRequest::IgnoredBrowserProbe => {
                info!("[Worker] Serving browser probe directly.");
                if let Err(e) = serve_empty_not_found(&mut socket).await {
                    warn!("[Worker] Browser probe response failed: {:?}", e);
                }
                continue;
            }
            StartupRequest::OtherGet => {
                info!("[Worker] Serving unhandled browser GET directly.");
                if let Err(e) = serve_empty_not_found(&mut socket).await {
                    warn!("[Worker] Unhandled GET response failed: {:?}", e);
                }
                continue;
            }
            StartupRequest::Options => {
                info!("[Worker] Serving OPTIONS directly.");
                if let Err(e) = serve_no_content(&mut socket).await {
                    warn!("[Worker] OPTIONS response failed: {:?}", e);
                }
                continue;
            }
            StartupRequest::KeyboardTarget => {
                info!("[Worker] Serving keyboard target directly.");
                if let Err(e) = serve_keyboard_target(&mut socket, &prefix[..prefix_len]).await {
                    warn!("[Worker] Keyboard target response failed: {:?}", e);
                }
                continue;
            }
            StartupRequest::Other => {}
        }

        let socket = PrefilteredSocket::new(socket, prefix, prefix_len);

        info!("[Worker] Starting HTTP serve...");
        match Server::new(&router, &config, &mut picoserve_buffer)
            .serve(socket)
            .await
        {
            Ok(DisconnectionInfo {
                handled_requests_count,
                ..
            }) => {
                info!(
                    "Successfully handled {} requests before closing.",
                    handled_requests_count
                );
            }
            Err(err) => {
                error!("Picoserve engine processing error: {:?}", err);
            }
        }
        info!("[Worker] HTTP serve returned.");
    }
}
