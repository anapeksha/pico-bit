use defmt::{error, info, warn};
use embassy_net::Stack;
use embassy_net::tcp::TcpSocket;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::mutex::Mutex;
use embassy_time::{Duration, with_timeout};
use littlefs2::fs::{File as LfsFile, FileAllocation};
use picoserve::io::{ErrorType, Read, Socket, Write};
use picoserve::{Config, DisconnectionInfo, EmbassyRuntime, Server, Timeouts};

use crate::net::{self as app_net, AppRouter, PayloadActionResult};
use crate::status::{self as status_led, Stage};
use crate::storage::{
    FlashDriver, LISTED_FILE_NAME_MAX, LISTED_FILE_PATH_MAX, ListedFile, StorageManager,
};

/// Bytes read up front to classify browser startup requests safely.
pub(super) const HTTP_PREFLIGHT_BYTES: usize = 64;
const HTTP_PREFLIGHT_TIMEOUT_MS: u64 = 300;
const ARMORY_BINARY_NAME: &str = "payload.bin";
const ARMORY_BINARY_PATH: &str = "/armory/payload.bin";
const ARMORY_DIR: &str = "/armory";
const ARMORY_PREFIX: &str = "/armory/";
const ARMORY_UPLOAD_LIMIT: usize = 750 * 1024;
const ARMORY_STREAM_CHUNK_SIZE: usize = 4096;

/// Accepts HTTP sockets for either the Wi-Fi portal or restricted NCM surface.
#[embassy_executor::task(pool_size = 2)]
pub async fn http_task(
    link: &'static str,
    surface: HttpSurface,
    stack: &'static Stack<'static>,
    router: &'static AppRouter,
    storage: &'static Mutex<CriticalSectionRawMutex, StorageManager>,
) {
    let config = Config::new(Timeouts {
        write: picoserve::time::Duration::from_secs(10),
        ..Timeouts::default()
    });

    let router = router.build();

    let mut rx_buffer = [0u8; ARMORY_STREAM_CHUNK_SIZE];
    let mut tx_buffer = [0u8; 1024];
    let mut picoserve_buffer = [0u8; 2048];

    info!("{} HTTP worker initialised...", link);

    loop {
        let mut socket = TcpSocket::new(*stack, &mut rx_buffer, &mut tx_buffer);

        if let Err(e) = socket.accept(80).await {
            warn!("[{} Worker] Accept failed: {:?}", link, e);
            continue;
        }

        let remote_address = socket.remote_endpoint();
        info!("[{} Worker] Connected to {}", link, remote_address);

        let mut prefix = [0u8; HTTP_PREFLIGHT_BYTES];
        let prefix_len = match with_timeout(
            Duration::from_millis(HTTP_PREFLIGHT_TIMEOUT_MS),
            socket.read(&mut prefix),
        )
        .await
        {
            Ok(Ok(0)) => {
                info!("[{} Worker] Empty HTTP preflight; closing socket.", link);
                continue;
            }
            Ok(Ok(len)) => len,
            Ok(Err(e)) => {
                warn!("[{} Worker] HTTP preflight read failed: {:?}", link, e);
                continue;
            }
            Err(_) => {
                info!(
                    "[{} Worker] Idle HTTP preflight timed out; closing socket.",
                    link
                );
                continue;
            }
        };

        if !looks_like_http_request(&prefix[..prefix_len]) {
            warn!("[{} Worker] Non-HTTP preflight rejected.", link);
            continue;
        }

        let request = classify_startup_request(&prefix[..prefix_len]);
        if !surface.allows(request) {
            info!("[{} Worker] Route is not enabled on this surface.", link);
            if let Err(e) = serve_empty_not_found(&mut socket).await {
                warn!("[{} Worker] Disabled route response failed: {:?}", link, e);
            }
            continue;
        }

        match request {
            StartupRequest::Root => {
                info!("[{} Worker] Serving root asset.", link);
                if let Err(e) = serve_root_asset(&mut socket).await {
                    warn!("[{} Worker] Root asset response failed: {:?}", link, e);
                }
                continue;
            }
            StartupRequest::Bootstrap => {
                info!("[{} Worker] Serving bootstrap.", link);
                if let Err(e) = serve_bootstrap(&mut socket).await {
                    warn!("[{} Worker] Bootstrap response failed: {:?}", link, e);
                }
                continue;
            }
            StartupRequest::Armory => {
                info!("[{} Worker] Serving armory.", link);
                if let Err(e) = serve_armory(&mut socket, storage, surface).await {
                    warn!("[{} Worker] Armory response failed: {:?}", link, e);
                }
                continue;
            }
            StartupRequest::ArmoryUpload => {
                info!("[{} Worker] Uploading armory binary.", link);
                if let Err(e) =
                    serve_armory_upload(&mut socket, storage, &prefix[..prefix_len]).await
                {
                    warn!("[{} Worker] Armory upload response failed: {:?}", link, e);
                }
                continue;
            }
            StartupRequest::ArmoryAsset => {
                info!("[{} Worker] Serving armory asset.", link);
                if let Err(e) =
                    serve_armory_asset(&mut socket, storage, surface, &prefix[..prefix_len]).await
                {
                    warn!("[{} Worker] Armory asset response failed: {:?}", link, e);
                }
                continue;
            }
            StartupRequest::ArmoryDelete => {
                info!("[{} Worker] Deleting armory asset.", link);
                if let Err(e) =
                    serve_armory_delete(&mut socket, storage, &prefix[..prefix_len]).await
                {
                    warn!("[{} Worker] Armory delete response failed: {:?}", link, e);
                }
                continue;
            }
            StartupRequest::Payload => {
                info!("[{} Worker] Serving payload.", link);
                if let Err(e) = serve_payload(&mut socket, storage).await {
                    warn!("[{} Worker] Payload response failed: {:?}", link, e);
                }
                continue;
            }
            StartupRequest::PayloadSave => {
                info!("[{} Worker] Saving payload.", link);
                if let Err(e) = serve_payload_save(&mut socket, &prefix[..prefix_len]).await {
                    warn!("[{} Worker] Payload save response failed: {:?}", link, e);
                }
                continue;
            }
            StartupRequest::PayloadRun => {
                info!("[{} Worker] Running payload.", link);
                if let Err(e) = serve_payload_run(&mut socket).await {
                    warn!("[{} Worker] Payload run response failed: {:?}", link, e);
                }
                continue;
            }
            StartupRequest::Runs => {
                info!("[{} Worker] Serving runs.", link);
                if let Err(e) = serve_runs(&mut socket).await {
                    warn!("[{} Worker] Runs response failed: {:?}", link, e);
                }
                continue;
            }
            StartupRequest::IgnoredBrowserProbe => {
                info!("[{} Worker] Serving browser probe.", link);
                if let Err(e) = serve_empty_not_found(&mut socket).await {
                    warn!("[{} Worker] Browser probe response failed: {:?}", link, e);
                }
                continue;
            }
            StartupRequest::OtherGet => {
                info!("[{} Worker] Serving unhandled browser GET.", link);
                if let Err(e) = serve_empty_not_found(&mut socket).await {
                    warn!("[{} Worker] Unhandled GET response failed: {:?}", link, e);
                }
                continue;
            }
            StartupRequest::Options => {
                info!("[{} Worker] Serving OPTIONS.", link);
                if let Err(e) = serve_no_content(&mut socket).await {
                    warn!("[{} Worker] OPTIONS response failed: {:?}", link, e);
                }
                continue;
            }
            StartupRequest::KeyboardTarget => {
                info!("[{} Worker] Serving keyboard target.", link);
                if let Err(e) = serve_keyboard_target(&mut socket, &prefix[..prefix_len]).await {
                    warn!("[{} Worker] Keyboard target response failed: {:?}", link, e);
                }
                continue;
            }
            StartupRequest::Other => {}
        }

        let socket = PrefilteredSocket::new(socket, prefix, prefix_len);

        info!("[{} Worker] Starting HTTP serve...", link);
        match Server::new(&router, &config, &mut picoserve_buffer)
            .serve(socket)
            .await
        {
            Ok(DisconnectionInfo {
                handled_requests_count,
                ..
            }) => {
                info!(
                    "{} worker handled {} requests before closing.",
                    link, handled_requests_count
                );
            }
            Err(err) => {
                error!("{} picoserve processing error: {:?}", link, err);
            }
        }
        info!("[{} Worker] HTTP serve returned.", link);
    }
}

/// HTTP route surface enabled for a worker instance.
#[derive(Clone, Copy, PartialEq)]
pub enum HttpSurface {
    /// Full Wi-Fi dashboard and API surface.
    Portal,
    /// USB NCM surface restricted to Armory binary delivery.
    Ncm,
}

impl HttpSurface {
    fn allows(self, request: StartupRequest) -> bool {
        match self {
            Self::Portal => true,
            Self::Ncm => matches!(
                request,
                StartupRequest::Armory | StartupRequest::ArmoryAsset | StartupRequest::Options
            ),
        }
    }
}

#[derive(Clone, Copy)]
enum StartupRequest {
    Root,
    Bootstrap,
    Armory,
    ArmoryUpload,
    ArmoryAsset,
    ArmoryDelete,
    Payload,
    PayloadSave,
    PayloadRun,
    Runs,
    IgnoredBrowserProbe,
    OtherGet,
    Options,
    KeyboardTarget,
    Other,
}

fn classify_startup_request(bytes: &[u8]) -> StartupRequest {
    if request_starts_with(bytes, b"GET / ") || request_starts_with(bytes, b"HEAD / ") {
        return StartupRequest::Root;
    }

    if request_starts_with(bytes, b"GET /api/bootstrap ") {
        return StartupRequest::Bootstrap;
    }

    if request_starts_with(bytes, b"GET /api/armory ") {
        return StartupRequest::Armory;
    }

    if request_starts_with(bytes, b"POST /api/armory/upload ") {
        return StartupRequest::ArmoryUpload;
    }

    if request_starts_with(bytes, b"DELETE /api/armory/") {
        return StartupRequest::ArmoryDelete;
    }

    if request_starts_with(bytes, b"GET /api/armory/")
        || request_starts_with(bytes, b"HEAD /api/armory/")
    {
        return StartupRequest::ArmoryAsset;
    }

    if request_starts_with(bytes, b"GET /api/payload ") {
        return StartupRequest::Payload;
    }

    if request_starts_with(bytes, b"POST /api/payload ") {
        return StartupRequest::PayloadSave;
    }

    if request_starts_with(bytes, b"POST /api/payload/run ") {
        return StartupRequest::PayloadRun;
    }

    if request_starts_with(bytes, b"GET /api/runs ") {
        return StartupRequest::Runs;
    }

    if request_starts_with(bytes, b"GET /favicon.ico ")
        || request_starts_with(bytes, b"GET /apple-touch-icon")
        || request_starts_with(bytes, b"GET /.well-known/")
        || request_starts_with(bytes, b"GET /manifest")
        || request_starts_with(bytes, b"GET /robots.txt ")
    {
        return StartupRequest::IgnoredBrowserProbe;
    }

    if is_get_or_head_request(bytes) {
        return StartupRequest::OtherGet;
    }

    if request_starts_with(bytes, b"OPTIONS ") {
        return StartupRequest::Options;
    }

    if request_starts_with(bytes, b"POST /api/keyboard/layout ") {
        return StartupRequest::KeyboardTarget;
    }

    StartupRequest::Other
}

fn looks_like_http_request(bytes: &[u8]) -> bool {
    const METHODS: &[&[u8]] = &[
        b"GET ",
        b"POST ",
        b"PUT ",
        b"DELETE ",
        b"HEAD ",
        b"OPTIONS ",
        b"PATCH ",
    ];

    METHODS
        .iter()
        .any(|method| method.starts_with(bytes) || bytes.starts_with(method))
}

fn request_starts_with(bytes: &[u8], pattern: &[u8]) -> bool {
    pattern.starts_with(bytes) || bytes.starts_with(pattern)
}

fn is_get_or_head_request(bytes: &[u8]) -> bool {
    request_starts_with(bytes, b"GET ") || request_starts_with(bytes, b"HEAD ")
}

const STARTUP_FILE_LIMIT: usize = 16;

static STARTUP_LISTED_FILES: Mutex<CriticalSectionRawMutex, [ListedFile; STARTUP_FILE_LIMIT]> =
    Mutex::new([ListedFile::empty(); STARTUP_FILE_LIMIT]);

/// Serves the gzipped single-file dashboard.
///
/// `socket` is the accepted TCP connection. Returns `Ok(())` after the chunked
/// HTML response is written and the connection is closed.
pub(super) async fn serve_root_asset(
    socket: &mut TcpSocket<'_>,
) -> Result<(), embassy_net::tcp::Error> {
    socket
        .write_all(
            b"HTTP/1.1 200 OK\r\n\
Content-Type: text/html\r\n\
Content-Encoding: gzip\r\n\
Vary: Accept-Encoding\r\n\
Cache-Control: no-store\r\n\
Transfer-Encoding: chunked\r\n\
Connection: close\r\n\
\r\n",
        )
        .await?;

    for chunk in app_net::compressed_index_html().chunks(1024) {
        write_chunk_size(socket, chunk.len()).await?;
        socket.write_all(b"\r\n").await?;
        socket.write_all(chunk).await?;
        socket.write_all(b"\r\n").await?;
    }

    socket.write_all(b"0\r\n\r\n").await?;
    socket.close();
    socket.flush().await
}

/// Writes a zero-length 404 response.
///
/// `socket` is the accepted TCP connection. Returns `Ok(())` after the response
/// is written and the connection is closed.
pub(super) async fn serve_empty_not_found(
    socket: &mut TcpSocket<'_>,
) -> Result<(), embassy_net::tcp::Error> {
    socket
        .write_all(
            b"HTTP/1.1 404 Not Found\r\n\
Content-Length: 0\r\n\
Connection: close\r\n\
\r\n",
        )
        .await?;
    socket.close();
    socket.flush().await
}

/// Writes a zero-length 204 response for OPTIONS/preflight requests.
///
/// `socket` is the accepted TCP connection. Returns `Ok(())` after the response
/// is written and the connection is closed.
pub(super) async fn serve_no_content(
    socket: &mut TcpSocket<'_>,
) -> Result<(), embassy_net::tcp::Error> {
    socket
        .write_all(
            b"HTTP/1.1 204 No Content\r\n\
Content-Length: 0\r\n\
Connection: close\r\n\
\r\n",
        )
        .await?;
    socket.close();
    socket.flush().await
}

/// Writes a zero-length 500 response.
///
/// `socket` is the accepted TCP connection. Returns `Ok(())` after the response
/// is written and the connection is closed.
pub(super) async fn serve_empty_internal_error(
    socket: &mut TcpSocket<'_>,
) -> Result<(), embassy_net::tcp::Error> {
    socket
        .write_all(
            b"HTTP/1.1 500 Internal Server Error\r\n\
Content-Length: 0\r\n\
Connection: close\r\n\
\r\n",
        )
        .await?;
    socket.close();
    socket.flush().await
}

/// Serves the fixed bootstrap JSON snapshot.
///
/// `socket` is the accepted TCP connection. Returns `Ok(())` after the fixed
/// JSON response is written and the connection is closed.
pub(super) async fn serve_bootstrap(
    socket: &mut TcpSocket<'_>,
) -> Result<(), embassy_net::tcp::Error> {
    let (keyboard_os, keyboard_layout) = app_net::active_keyboard_target_codes();
    let mut body = FixedBody::<512>::new();

    body.raw(b"{\"ap_password\":");
    body.json_string(app_net::wifi_ap_password().as_bytes());
    body.raw(b",\"ap_ssid\":");
    body.json_string(app_net::wifi_ap_ssid().as_bytes());
    body.raw(b",\"host_hid_active\":");
    body.raw(if app_net::host_hid_active() {
        b"true"
    } else {
        b"false"
    });
    body.raw(b",\"keyboard_layout\":");
    body.json_string(keyboard_layout.as_bytes());
    body.raw(b",\"keyboard_os\":");
    body.json_string(keyboard_os.as_bytes());
    body.raw(b",\"ncm_active\":");
    body.raw(if app_net::ncm_active() {
        b"true"
    } else {
        b"false"
    });
    body.raw(b",\"ncm_url\":");
    body.json_string(app_net::ncm_url().as_bytes());
    body.raw(b",\"seeded\":");
    body.raw(if app_net::seeded_this_boot() {
        b"true"
    } else {
        b"false"
    });
    body.raw(b"}");

    if body.overflowed() {
        return serve_empty_internal_error(socket).await;
    }

    write_fixed_json_response(socket, body.bytes()).await
}

struct FixedBody<const N: usize> {
    bytes: [u8; N],
    len: usize,
    overflowed: bool,
}

impl<const N: usize> FixedBody<N> {
    fn new() -> Self {
        Self {
            bytes: [0u8; N],
            len: 0,
            overflowed: false,
        }
    }

    fn bytes(&self) -> &[u8] {
        &self.bytes[..self.len]
    }

    fn overflowed(&self) -> bool {
        self.overflowed
    }

    fn raw(&mut self, bytes: &[u8]) {
        if self.overflowed || self.len + bytes.len() > self.bytes.len() {
            self.overflowed = true;
            return;
        }

        self.bytes[self.len..self.len + bytes.len()].copy_from_slice(bytes);
        self.len += bytes.len();
    }

    fn json_string(&mut self, bytes: &[u8]) {
        self.raw(b"\"");

        let mut index = 0usize;
        while index < bytes.len() {
            match bytes[index] {
                b'"' => self.raw(b"\\\""),
                b'\\' => self.raw(b"\\\\"),
                b'\n' => self.raw(b"\\n"),
                b'\r' => self.raw(b"\\r"),
                b'\t' => self.raw(b"\\t"),
                0x00..=0x1f => {
                    let escaped = json_unicode_escape(bytes[index]);
                    self.raw(&escaped);
                }
                byte => self.raw(&[byte]),
            }

            index += 1;
        }

        self.raw(b"\"");
    }

    fn usize_value(&mut self, value: usize) {
        let mut digits = [0u8; 20];
        let mut index = digits.len();
        let mut remaining = value;

        if remaining == 0 {
            self.raw(b"0");
            return;
        }

        while remaining > 0 {
            index -= 1;
            digits[index] = b'0' + (remaining % 10) as u8;
            remaining /= 10;
        }

        self.raw(&digits[index..]);
    }
}

#[derive(Clone, Copy)]
enum PayloadBodyError {
    MissingCode,
    InvalidJson,
    TooLarge,
    InvalidUtf8,
}

impl PayloadBodyError {
    fn message(self) -> &'static str {
        match self {
            Self::MissingCode => "Missing payload code.",
            Self::InvalidJson => "Invalid payload request body.",
            Self::TooLarge => "Payload content exceeds 2048 bytes.",
            Self::InvalidUtf8 => "Invalid UTF-8 sequence sent in payload body.",
        }
    }

    fn status(self) -> HttpStatus {
        match self {
            Self::TooLarge => HttpStatus::PayloadTooLarge,
            _ => HttpStatus::BadRequest,
        }
    }
}

/// Updates the active keyboard OS/layout target from a small JSON body.
///
/// `socket` is the accepted TCP connection and `prefix` contains bytes already
/// read by request classification. Returns `Ok(())` after the mutation response
/// is written.
pub(super) async fn serve_keyboard_target(
    socket: &mut TcpSocket<'_>,
    prefix: &[u8],
) -> Result<(), embassy_net::tcp::Error> {
    let mut request = [0u8; 1024];
    let request_len = socket_read_prefetched_request(socket, prefix, &mut request).await;
    let body = request_body(&request[..request_len]).unwrap_or(&[]);

    let (current_os, current_layout) = app_net::active_keyboard_target_codes();
    let os = keyboard_os_from_body(body).unwrap_or(current_os);
    let layout = keyboard_layout_from_body(body).unwrap_or(current_layout);
    let ok = app_net::update_keyboard_target_codes(os, layout);

    let (response_os, response_layout) = app_net::active_keyboard_target_codes();

    write_json_headers(socket).await?;
    write_http_chunk(socket, b"{\"keyboard_layout\":").await?;
    write_json_string_bytes(socket, response_layout.as_bytes()).await?;
    write_http_chunk(socket, b",\"keyboard_os\":").await?;
    write_json_string_bytes(socket, response_os.as_bytes()).await?;

    if ok {
        write_http_chunk(
            socket,
            b",\"message\":\"Keyboard target updated.\",\"notice\":\"success\"}",
        )
        .await?;
    } else {
        write_http_chunk(
            socket,
            b",\"message\":\"Unsupported keyboard layout.\",\"notice\":\"error\"}",
        )
        .await?;
    }

    write_final_chunk(socket).await
}

fn decode_payload_code<'a>(body: &[u8], output: &'a mut [u8]) -> Result<&'a str, PayloadBodyError> {
    let key = b"\"code\"";
    let key_index = body
        .windows(key.len())
        .position(|window| window == key)
        .ok_or(PayloadBodyError::MissingCode)?;
    let mut index = key_index + key.len();

    index = skip_json_whitespace(body, index);
    if body.get(index) != Some(&b':') {
        return Err(PayloadBodyError::InvalidJson);
    }
    index += 1;
    index = skip_json_whitespace(body, index);
    if body.get(index) != Some(&b'"') {
        return Err(PayloadBodyError::InvalidJson);
    }
    index += 1;

    let mut len = 0usize;
    while index < body.len() {
        let byte = body[index];
        index += 1;

        if byte == b'"' {
            return core::str::from_utf8(&output[..len]).map_err(|_| PayloadBodyError::InvalidUtf8);
        }

        let decoded = if byte == b'\\' {
            if index >= body.len() {
                return Err(PayloadBodyError::InvalidJson);
            }

            let escaped = body[index];
            index += 1;
            match escaped {
                b'"' => b'"',
                b'\\' => b'\\',
                b'/' => b'/',
                b'b' => 0x08,
                b'f' => 0x0c,
                b'n' => b'\n',
                b'r' => b'\r',
                b't' => b'\t',
                b'u' => {
                    if index + 4 > body.len() {
                        return Err(PayloadBodyError::InvalidJson);
                    }
                    let value = json_hex_word(&body[index..index + 4])
                        .ok_or(PayloadBodyError::InvalidJson)?;
                    index += 4;
                    if value > 0x7f {
                        return Err(PayloadBodyError::InvalidUtf8);
                    }
                    value as u8
                }
                _ => return Err(PayloadBodyError::InvalidJson),
            }
        } else {
            byte
        };

        if len >= output.len() {
            return Err(PayloadBodyError::TooLarge);
        }

        output[len] = decoded;
        len += 1;
    }

    Err(PayloadBodyError::InvalidJson)
}

fn skip_json_whitespace(bytes: &[u8], mut index: usize) -> usize {
    while index < bytes.len() && matches!(bytes[index], b' ' | b'\n' | b'\r' | b'\t') {
        index += 1;
    }

    index
}

fn json_hex_word(bytes: &[u8]) -> Option<u16> {
    let mut value = 0u16;

    for byte in bytes {
        let digit = match *byte {
            b'0'..=b'9' => *byte - b'0',
            b'a'..=b'f' => *byte - b'a' + 10,
            b'A'..=b'F' => *byte - b'A' + 10,
            _ => return None,
        };
        value = (value << 4) | digit as u16;
    }

    Some(value)
}

/// Serves compact current-session run history.
///
/// `socket` is the accepted TCP connection. Returns `Ok(())` after the chunked
/// JSON response is written and the connection is closed.
pub(super) async fn serve_runs(socket: &mut TcpSocket<'_>) -> Result<(), embassy_net::tcp::Error> {
    let runs = app_net::runs_snapshot();

    write_json_headers(socket).await?;
    write_http_chunk(socket, b"{\"run_history\":[").await?;

    for (index, entry) in runs.entries().iter().enumerate() {
        if index > 0 {
            write_http_chunk(socket, b",").await?;
        }

        write_http_chunk(socket, b"{\"ok\":").await?;
        write_http_chunk(socket, if entry.ok() { b"true" } else { b"false" }).await?;
        write_http_chunk(socket, b",\"preview\":").await?;
        write_json_string_bytes(socket, entry.preview().as_bytes()).await?;
        write_http_chunk(socket, b",\"sequence\":").await?;
        write_json_usize(socket, entry.sequence()).await?;
        write_http_chunk(socket, b",\"source\":").await?;
        write_json_string_bytes(socket, entry.source().as_bytes()).await?;
        write_http_chunk(socket, b"}").await?;
    }

    write_http_chunk(socket, b"],\"seeded\":").await?;
    write_http_chunk(socket, if runs.seeded() { b"true" } else { b"false" }).await?;
    write_http_chunk(socket, b"}").await?;
    write_final_chunk(socket).await
}

/// Streams the current `payload.dd` editor contents as JSON.
///
/// `socket` is the accepted TCP connection and `storage` is the shared LittleFS
/// manager. Returns `Ok(())` after the chunked JSON response is written.
pub(super) async fn serve_payload(
    socket: &mut TcpSocket<'_>,
    storage: &'static Mutex<CriticalSectionRawMutex, StorageManager>,
) -> Result<(), embassy_net::tcp::Error> {
    let mut payload = [0u8; 2048];
    let payload_len = {
        let storage_guard = storage.lock().await;
        storage_guard
            .read("payload.dd", &mut payload)
            .map(|bytes| bytes.len())
            .unwrap_or(0)
    };

    write_json_headers(socket).await?;

    write_http_chunk(socket, b"{\"code\":").await?;
    write_json_string_bytes(socket, &payload[..payload_len]).await?;
    write_http_chunk(socket, b"}").await?;

    write_final_chunk(socket).await
}

/// Saves the posted DuckyScript body into `payload.dd`.
///
/// `socket` is the accepted TCP connection and `prefix` contains bytes already
/// read by request classification. Returns `Ok(())` after the validation/write
/// response is sent.
pub(super) async fn serve_payload_save(
    socket: &mut TcpSocket<'_>,
    prefix: &[u8],
) -> Result<(), embassy_net::tcp::Error> {
    let mut request = [0u8; 4096];
    let request_len = socket_read_prefetched_request(socket, prefix, &mut request).await;
    let body = request_body(&request[..request_len]).unwrap_or(&[]);
    let mut code = [0u8; 2048];

    let result = match decode_payload_code(body, &mut code) {
        Ok(code) => app_net::save_payload_code(code).await,
        Err(error) => {
            return write_payload_error_response(socket, error.message(), error.status()).await;
        }
    };

    write_payload_action_response(socket, result).await
}

/// Triggers execution of the saved `payload.dd` after firmware validation.
///
/// `socket` is the accepted TCP connection. Returns `Ok(())` after the run
/// trigger response is written.
pub(super) async fn serve_payload_run(
    socket: &mut TcpSocket<'_>,
) -> Result<(), embassy_net::tcp::Error> {
    let result = app_net::trigger_payload_run().await;
    write_payload_action_response(socket, result).await
}

/// Serves the bounded Armory file listing.
///
/// `socket` is the accepted TCP connection, `storage` is the shared LittleFS
/// manager, and `surface` decides whether portal-only files are exposed. Returns
/// `Ok(())` after the chunked JSON response is written.
pub(super) async fn serve_armory(
    socket: &mut TcpSocket<'_>,
    storage: &'static Mutex<CriticalSectionRawMutex, StorageManager>,
    surface: HttpSurface,
) -> Result<(), embassy_net::tcp::Error> {
    let file_count = {
        let storage_guard = storage.lock().await;
        let mut files = STARTUP_LISTED_FILES.lock().await;
        storage_guard
            .list_files(&mut files)
            .unwrap_or(0)
            .min(STARTUP_FILE_LIMIT)
    };

    write_json_headers(socket).await?;

    let mut has_binary = false;
    let mut written = 0usize;
    let mut wrote_asset = false;

    write_http_chunk(socket, b"{\"files\":[").await?;

    for index in 0..file_count {
        let (name, size, is_payload, valid) = {
            let files = STARTUP_LISTED_FILES.lock().await;
            let file = files[index];
            let name = file.name();
            let path = file.path();
            (
                StringCopy::<64>::from(name),
                file.size(),
                name == "payload.dd" || path == "/payload.dd",
                !name.is_empty(),
            )
        };

        if !valid {
            continue;
        }

        if surface == HttpSurface::Ncm && is_payload {
            continue;
        }

        if !is_payload && wrote_asset {
            continue;
        }

        if written > 0 {
            write_http_chunk(socket, b",").await?;
        }
        written += 1;

        if !is_payload {
            has_binary = true;
            wrote_asset = true;
        }

        write_http_chunk(socket, b"{\"kind\":\"").await?;
        write_http_chunk(socket, if is_payload { b"ducky" } else { b"asset" }).await?;
        write_http_chunk(socket, b"\",\"name\":").await?;
        write_json_string_bytes(socket, name.as_bytes()).await?;
        write_http_chunk(socket, b",\"size\":").await?;
        write_json_usize(socket, size).await?;
        write_http_chunk(socket, b"}").await?;
    }

    write_http_chunk(socket, b"],\"has_binary\":").await?;
    write_http_chunk(socket, if has_binary { b"true" } else { b"false" }).await?;
    write_http_chunk(socket, b"}").await?;

    write_final_chunk(socket).await
}

/// Streams an Armory asset or portal-only `payload.dd` download.
///
/// `socket` is the accepted TCP connection, `storage` is the shared LittleFS
/// manager, `surface` restricts NCM access, and `prefix` contains classified
/// request bytes. Returns `Ok(())` after the binary response is written.
pub(super) async fn serve_armory_asset(
    socket: &mut TcpSocket<'_>,
    storage: &'static Mutex<CriticalSectionRawMutex, StorageManager>,
    surface: HttpSurface,
    prefix: &[u8],
) -> Result<(), embassy_net::tcp::Error> {
    let mut request = [0u8; 512];
    let request_len = socket_read_prefetched_request(socket, prefix, &mut request).await;
    let Some(target) = armory_asset_target(&request[..request_len]) else {
        return serve_empty_not_found(socket).await;
    };

    if surface == HttpSurface::Ncm && target.is_payload() {
        return serve_empty_not_found(socket).await;
    }

    let mut offset = 0usize;
    let mut buffer = [0u8; 1024];

    match read_armory_asset_chunk(storage, &target, offset, &mut buffer).await {
        Ok(0) => {
            write_binary_headers(socket).await?;
            write_final_chunk(socket).await
        }
        Ok(read) => {
            write_binary_headers(socket).await?;
            write_http_chunk(socket, &buffer[..read]).await?;
            offset += read;

            loop {
                match read_armory_asset_chunk(storage, &target, offset, &mut buffer).await {
                    Ok(0) => break,
                    Ok(read) => {
                        write_http_chunk(socket, &buffer[..read]).await?;
                        offset += read;
                    }
                    Err(()) => break,
                }
            }

            write_final_chunk(socket).await
        }
        Err(()) => serve_empty_not_found(socket).await,
    }
}

/// Deletes one Armory file from LittleFS.
///
/// `socket` is the accepted TCP connection, `storage` is the shared LittleFS
/// manager, and `prefix` contains classified request bytes. Returns `Ok(())`
/// after a small mutation JSON response is written.
pub(super) async fn serve_armory_delete(
    socket: &mut TcpSocket<'_>,
    storage: &'static Mutex<CriticalSectionRawMutex, StorageManager>,
    prefix: &[u8],
) -> Result<(), embassy_net::tcp::Error> {
    let mut request = [0u8; 512];
    let request_len = socket_read_prefetched_headers(socket, prefix, &mut request).await;
    let Some(filename) = armory_delete_filename(&request[..request_len]) else {
        return write_armory_mutation_response(
            socket,
            HttpStatus::BadRequest,
            b"",
            "Invalid filename.",
            "error",
            false,
        )
        .await;
    };

    if filename.as_bytes() == b"payload.dd" {
        return write_armory_mutation_response(
            socket,
            HttpStatus::Forbidden,
            filename.as_bytes(),
            "payload.dd is managed by the editor and cannot be deleted.",
            "error",
            true,
        )
        .await;
    }

    let Some(path) = armory_storage_path_unrestricted(filename.as_str()) else {
        return write_armory_mutation_response(
            socket,
            HttpStatus::BadRequest,
            filename.as_bytes(),
            "Invalid filename.",
            "error",
            false,
        )
        .await;
    };

    let deleted = {
        let storage_guard = storage.lock().await;
        storage_guard.erase(path.as_str()).is_ok()
    };

    if deleted {
        write_armory_mutation_response(
            socket,
            HttpStatus::Ok,
            filename.as_bytes(),
            "File removed from flash.",
            "success",
            false,
        )
        .await
    } else {
        write_armory_mutation_response(
            socket,
            HttpStatus::InternalServerError,
            filename.as_bytes(),
            "littlefs2 storage operation failed.",
            "error",
            false,
        )
        .await
    }
}

/// Streams the fixed Armory upload into `/armory/payload.bin`.
///
/// `socket` is the accepted TCP socket, `storage` is the shared LittleFS manager,
/// and `prefix` contains bytes already consumed during request classification.
/// The response is a small fixed JSON mutation result.
pub(super) async fn serve_armory_upload(
    socket: &mut TcpSocket<'_>,
    storage: &'static Mutex<CriticalSectionRawMutex, StorageManager>,
    prefix: &[u8],
) -> Result<(), embassy_net::tcp::Error> {
    let mut request = [0u8; 1024];
    let request_len = socket_read_prefetched_headers(socket, prefix, &mut request).await;
    let Some(header_end) = header_end_index(&request[..request_len]) else {
        return write_armory_upload_response(
            socket,
            HttpStatus::BadRequest,
            "Invalid upload request.",
            "error",
            false,
        )
        .await;
    };

    let content_length = content_length(&request[..header_end]).unwrap_or(0);
    if content_length > ARMORY_UPLOAD_LIMIT {
        status_led::show(Stage::BinaryInjectFailed);
        return write_armory_upload_response(
            socket,
            HttpStatus::PayloadTooLarge,
            "Upload exceeds 750 KB capacity limit.",
            "error",
            false,
        )
        .await;
    }

    status_led::show(Stage::BinaryInjecting);
    let storage_guard = storage.lock().await;

    if prepare_armory_upload(&storage_guard).is_err() {
        drop(storage_guard);
        status_led::show(Stage::BinaryInjectFailed);
        return write_armory_upload_response(
            socket,
            HttpStatus::InternalServerError,
            "littlefs2 storage operation failed.",
            "error",
            false,
        )
        .await;
    }

    let mut file_alloc = FileAllocation::<FlashDriver>::new();
    let file = match storage_guard.open_write_truncate(ARMORY_BINARY_PATH, &mut file_alloc) {
        Ok(file) => file,
        Err(_) => {
            drop(storage_guard);
            status_led::show(Stage::BinaryInjectFailed);
            return write_armory_upload_response(
                socket,
                HttpStatus::InternalServerError,
                "littlefs2 storage operation failed.",
                "error",
                false,
            )
            .await;
        }
    };

    let body_start = header_end + 4;
    let buffered_body_len = request_len.saturating_sub(body_start).min(content_length);
    let mut received = 0usize;
    let mut failed = false;

    if buffered_body_len > 0 {
        let buffered_body = &request[body_start..body_start + buffered_body_len];
        if write_armory_upload_chunk(&file, buffered_body).is_err() {
            failed = true;
        }
        received += buffered_body_len;
    }

    let mut buffer = [0u8; ARMORY_STREAM_CHUNK_SIZE];
    while !failed && received < content_length {
        let remaining = content_length - received;
        let limit = remaining.min(buffer.len());

        match socket.read(&mut buffer[..limit]).await {
            Ok(0) => {
                failed = true;
            }
            Ok(read) => {
                if write_armory_upload_chunk(&file, &buffer[..read]).is_err() {
                    failed = true;
                }
                received += read;
            }
            Err(_) => {
                failed = true;
            }
        }
    }

    let close_failed = unsafe { file.close() }.is_err();

    if failed || received != content_length {
        let _ = storage_guard.erase(ARMORY_BINARY_PATH);
        drop(storage_guard);
        status_led::show(Stage::BinaryInjectFailed);
        return write_armory_upload_response(
            socket,
            HttpStatus::InternalServerError,
            "littlefs2 storage operation failed.",
            "error",
            false,
        )
        .await;
    }

    if close_failed {
        let _ = storage_guard.erase(ARMORY_BINARY_PATH);
        drop(storage_guard);
        status_led::show(Stage::BinaryInjectFailed);
        return write_armory_upload_response(
            socket,
            HttpStatus::InternalServerError,
            "littlefs2 storage operation failed.",
            "error",
            false,
        )
        .await;
    }

    drop(storage_guard);
    status_led::show(Stage::LootImported);
    write_armory_upload_response(
        socket,
        HttpStatus::Ok,
        "Upload committed to flash.",
        "success",
        true,
    )
    .await
}

struct StringCopy<const N: usize> {
    bytes: [u8; N],
    len: usize,
}

impl<const N: usize> StringCopy<N> {
    fn from(value: &str) -> Self {
        let mut copy = Self {
            bytes: [0u8; N],
            len: 0,
        };
        let bytes = value.as_bytes();
        copy.len = bytes.len().min(N);
        copy.bytes[..copy.len].copy_from_slice(&bytes[..copy.len]);
        copy
    }

    fn as_bytes(&self) -> &[u8] {
        &self.bytes[..self.len]
    }

    fn as_str(&self) -> &str {
        core::str::from_utf8(self.as_bytes()).unwrap_or("")
    }
}

#[derive(Clone, Copy)]
enum HttpStatus {
    Ok,
    BadRequest,
    Forbidden,
    PayloadTooLarge,
    InternalServerError,
}

impl HttpStatus {
    fn line(self) -> &'static [u8] {
        match self {
            Self::Ok => b"HTTP/1.1 200 OK\r\n",
            Self::BadRequest => b"HTTP/1.1 400 Bad Request\r\n",
            Self::Forbidden => b"HTTP/1.1 403 Forbidden\r\n",
            Self::PayloadTooLarge => b"HTTP/1.1 413 Payload Too Large\r\n",
            Self::InternalServerError => b"HTTP/1.1 500 Internal Server Error\r\n",
        }
    }
}

/// Writes the fixed Armory upload mutation response.
///
/// `status` selects the HTTP status line. `message` and `notice` are compact UI
/// fields, and `has_binary` reports whether `payload.bin` is now present.
async fn write_armory_upload_response(
    socket: &mut TcpSocket<'_>,
    status: HttpStatus,
    message: &'static str,
    notice: &'static str,
    has_binary: bool,
) -> Result<(), embassy_net::tcp::Error> {
    write_armory_mutation_response(
        socket,
        status,
        ARMORY_BINARY_NAME.as_bytes(),
        message,
        notice,
        has_binary,
    )
    .await
}

/// Writes the shared Armory mutation response.
///
/// `filename` is serialized into the response body. `message`, `notice`, and
/// `has_binary` mirror the frontend Armory mutation contract. Returns `Ok(())`
/// after the fixed JSON response is written.
async fn write_armory_mutation_response(
    socket: &mut TcpSocket<'_>,
    status: HttpStatus,
    filename: &[u8],
    message: &'static str,
    notice: &'static str,
    has_binary: bool,
) -> Result<(), embassy_net::tcp::Error> {
    let mut body = FixedBody::<256>::new();

    body.raw(b"{\"filename\":");
    body.json_string(filename);
    body.raw(b",\"has_binary\":");
    body.raw(if has_binary { b"true" } else { b"false" });
    body.raw(b",\"message\":");
    body.json_string(message.as_bytes());
    body.raw(b",\"notice\":");
    body.json_string(notice.as_bytes());
    body.raw(b"}");

    if body.overflowed() {
        return serve_empty_internal_error(socket).await;
    }

    write_fixed_json_response_with_status(socket, status, body.bytes()).await
}

async fn write_payload_action_response(
    socket: &mut TcpSocket<'_>,
    result: PayloadActionResult,
) -> Result<(), embassy_net::tcp::Error> {
    let mut body = FixedBody::<384>::new();

    body.raw(b"{\"success\":");
    body.raw(if result.success() { b"true" } else { b"false" });
    body.raw(b",\"message\":");
    body.json_string(result.message().as_bytes());
    body.raw(b",\"error_line\":");
    match result.error_line() {
        Some(line) => body.usize_value(line),
        None => body.raw(b"null"),
    }
    body.raw(b"}");

    let status = if result.success() {
        HttpStatus::Ok
    } else {
        HttpStatus::BadRequest
    };

    if body.overflowed() {
        return write_payload_error_response(
            socket,
            "Payload response exceeded fixed response buffer.",
            HttpStatus::InternalServerError,
        )
        .await;
    }

    write_fixed_json_response_with_status(socket, status, body.bytes()).await
}

async fn write_payload_error_response(
    socket: &mut TcpSocket<'_>,
    message: &'static str,
    status: HttpStatus,
) -> Result<(), embassy_net::tcp::Error> {
    let mut body = FixedBody::<256>::new();

    body.raw(b"{\"success\":false,\"message\":");
    body.json_string(message.as_bytes());
    body.raw(b",\"error_line\":null}");

    if body.overflowed() {
        return serve_empty_internal_error(socket).await;
    }

    write_fixed_json_response_with_status(socket, status, body.bytes()).await
}

async fn write_fixed_json_response(
    socket: &mut TcpSocket<'_>,
    body: &[u8],
) -> Result<(), embassy_net::tcp::Error> {
    write_fixed_json_response_with_status(socket, HttpStatus::Ok, body).await
}

async fn write_fixed_json_response_with_status(
    socket: &mut TcpSocket<'_>,
    status: HttpStatus,
    body: &[u8],
) -> Result<(), embassy_net::tcp::Error> {
    socket.write_all(status.line()).await?;
    socket
        .write_all(
            b"Content-Type: application/json\r\n\
Cache-Control: no-store\r\n\
Content-Length: ",
        )
        .await?;
    write_decimal(socket, body.len()).await?;
    socket
        .write_all(
            b"\r\n\
Connection: close\r\n\
\r\n",
        )
        .await?;
    socket.write_all(body).await?;
    socket.close();
    socket.flush().await
}

async fn write_json_headers(socket: &mut TcpSocket<'_>) -> Result<(), embassy_net::tcp::Error> {
    socket
        .write_all(
            b"HTTP/1.1 200 OK\r\n\
Content-Type: application/json\r\n\
Cache-Control: no-store\r\n\
Transfer-Encoding: chunked\r\n\
Connection: close\r\n\
\r\n",
        )
        .await
}

async fn write_binary_headers(socket: &mut TcpSocket<'_>) -> Result<(), embassy_net::tcp::Error> {
    socket
        .write_all(
            b"HTTP/1.1 200 OK\r\n\
Content-Type: application/octet-stream\r\n\
Cache-Control: no-store\r\n\
Transfer-Encoding: chunked\r\n\
Connection: close\r\n\
\r\n",
        )
        .await
}

async fn write_http_chunk(
    socket: &mut TcpSocket<'_>,
    bytes: &[u8],
) -> Result<(), embassy_net::tcp::Error> {
    if bytes.is_empty() {
        return Ok(());
    }

    write_chunk_size(socket, bytes.len()).await?;
    socket.write_all(b"\r\n").await?;
    socket.write_all(bytes).await?;
    socket.write_all(b"\r\n").await
}

async fn write_final_chunk(socket: &mut TcpSocket<'_>) -> Result<(), embassy_net::tcp::Error> {
    socket.write_all(b"0\r\n\r\n").await?;
    socket.close();
    socket.flush().await
}

async fn write_decimal(
    socket: &mut TcpSocket<'_>,
    value: usize,
) -> Result<(), embassy_net::tcp::Error> {
    let mut digits = [0u8; 20];
    let mut index = digits.len();
    let mut remaining = value;

    if remaining == 0 {
        return socket.write_all(b"0").await;
    }

    while remaining > 0 {
        index -= 1;
        digits[index] = b'0' + (remaining % 10) as u8;
        remaining /= 10;
    }

    socket.write_all(&digits[index..]).await
}

async fn write_json_usize(
    socket: &mut TcpSocket<'_>,
    value: usize,
) -> Result<(), embassy_net::tcp::Error> {
    let mut digits = [0u8; 20];
    let mut index = digits.len();
    let mut remaining = value;

    if remaining == 0 {
        return write_http_chunk(socket, b"0").await;
    }

    while remaining > 0 {
        index -= 1;
        digits[index] = b'0' + (remaining % 10) as u8;
        remaining /= 10;
    }

    write_http_chunk(socket, &digits[index..]).await
}

async fn write_json_string_bytes(
    socket: &mut TcpSocket<'_>,
    bytes: &[u8],
) -> Result<(), embassy_net::tcp::Error> {
    write_http_chunk(socket, b"\"").await?;

    let mut start = 0;
    let mut index = 0;

    while index < bytes.len() {
        let escape = match bytes[index] {
            b'"' => Some(&b"\\\""[..]),
            b'\\' => Some(&b"\\\\"[..]),
            b'\n' => Some(&b"\\n"[..]),
            b'\r' => Some(&b"\\r"[..]),
            b'\t' => Some(&b"\\t"[..]),
            0x00..=0x1f => None,
            _ => {
                index += 1;
                continue;
            }
        };

        if start < index {
            write_http_chunk(socket, &bytes[start..index]).await?;
        }

        if let Some(escape) = escape {
            write_http_chunk(socket, escape).await?;
        } else {
            let escaped = json_unicode_escape(bytes[index]);
            write_http_chunk(socket, &escaped).await?;
        }

        index += 1;
        start = index;
    }

    if start < bytes.len() {
        write_http_chunk(socket, &bytes[start..]).await?;
    }

    write_http_chunk(socket, b"\"").await
}

async fn write_chunk_size(
    socket: &mut TcpSocket<'_>,
    value: usize,
) -> Result<(), embassy_net::tcp::Error> {
    let mut digits = [0u8; 8];
    let mut index = digits.len();
    let mut remaining = value;

    if remaining == 0 {
        return socket.write_all(b"0").await;
    }

    while remaining > 0 {
        index -= 1;
        let nibble = (remaining & 0x0f) as u8;
        digits[index] = if nibble < 10 {
            b'0' + nibble
        } else {
            b'a' + (nibble - 10)
        };
        remaining >>= 4;
    }

    socket.write_all(&digits[index..]).await
}

fn json_unicode_escape(byte: u8) -> [u8; 6] {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    [
        b'\\',
        b'u',
        b'0',
        b'0',
        HEX[(byte >> 4) as usize],
        HEX[(byte & 0x0f) as usize],
    ]
}

async fn socket_read_prefetched_request(
    socket: &mut TcpSocket<'_>,
    prefix: &[u8],
    buffer: &mut [u8],
) -> usize {
    let mut len = prefix.len().min(buffer.len());
    buffer[..len].copy_from_slice(&prefix[..len]);

    loop {
        if request_body_ready(&buffer[..len]) || len == buffer.len() {
            break;
        }

        match with_timeout(Duration::from_millis(100), socket.read(&mut buffer[len..])).await {
            Ok(Ok(0)) | Err(_) => break,
            Ok(Ok(read)) => len += read,
            Ok(Err(_)) => break,
        }
    }

    len
}

/// Reads enough bytes to include HTTP headers, preserving any early body bytes.
///
/// `socket` is the active connection, `prefix` is the preflight data already
/// consumed by the classifier, and `buffer` receives the request prefix. Returns
/// the number of valid bytes copied into `buffer`.
async fn socket_read_prefetched_headers(
    socket: &mut TcpSocket<'_>,
    prefix: &[u8],
    buffer: &mut [u8],
) -> usize {
    let mut len = prefix.len().min(buffer.len());
    buffer[..len].copy_from_slice(&prefix[..len]);

    loop {
        if header_end_index(&buffer[..len]).is_some() || len == buffer.len() {
            break;
        }

        match with_timeout(Duration::from_millis(100), socket.read(&mut buffer[len..])).await {
            Ok(Ok(0)) | Err(_) => break,
            Ok(Ok(read)) => len += read,
            Ok(Err(_)) => break,
        }
    }

    len
}

fn request_body(request: &[u8]) -> Option<&[u8]> {
    let header_end = header_end_index(request)?;
    let body_start = header_end + 4;
    let content_length = content_length(&request[..header_end]).unwrap_or(0);
    let body_end = (body_start + content_length).min(request.len());
    Some(&request[body_start..body_end])
}

fn keyboard_layout_from_body(body: &[u8]) -> Option<&'static str> {
    if contains_bytes(body, b"\"layout\":\"UK\"") {
        Some("UK")
    } else if contains_bytes(body, b"\"layout\":\"DE\"") {
        Some("DE")
    } else if contains_bytes(body, b"\"layout\":\"FR\"") {
        Some("FR")
    } else if contains_bytes(body, b"\"layout\":\"US\"") {
        Some("US")
    } else {
        None
    }
}

fn keyboard_os_from_body(body: &[u8]) -> Option<&'static str> {
    if contains_bytes(body, b"\"os\":\"MAC\"") {
        Some("MAC")
    } else if contains_bytes(body, b"\"os\":\"LINUX\"") {
        Some("LINUX")
    } else if contains_bytes(body, b"\"os\":\"WIN\"") {
        Some("WIN")
    } else {
        None
    }
}

fn request_body_ready(request: &[u8]) -> bool {
    let Some(header_end) = header_end_index(request) else {
        return false;
    };

    let content_length = content_length(&request[..header_end]).unwrap_or(0);
    request.len() >= header_end + 4 + content_length
}

fn header_end_index(bytes: &[u8]) -> Option<usize> {
    bytes.windows(4).position(|window| window == b"\r\n\r\n")
}

fn content_length(headers: &[u8]) -> Option<usize> {
    let header = b"content-length:";
    let mut index = 0;

    while index + header.len() <= headers.len() {
        if bytes_eq_ignore_ascii_case(&headers[index..index + header.len()], header) {
            let mut value_index = index + header.len();
            while value_index < headers.len() && headers[value_index] == b' ' {
                value_index += 1;
            }

            let mut value = 0usize;
            let mut found_digit = false;
            while value_index < headers.len() {
                let byte = headers[value_index];
                if !byte.is_ascii_digit() {
                    break;
                }
                found_digit = true;
                value = value
                    .saturating_mul(10)
                    .saturating_add((byte - b'0') as usize);
                value_index += 1;
            }

            return found_digit.then_some(value);
        }

        index += 1;
    }

    None
}

fn bytes_eq_ignore_ascii_case(left: &[u8], right: &[u8]) -> bool {
    left.len() == right.len()
        && left
            .iter()
            .zip(right.iter())
            .all(|(a, b)| a.eq_ignore_ascii_case(b))
}

fn contains_bytes(haystack: &[u8], needle: &[u8]) -> bool {
    needle.is_empty()
        || haystack
            .windows(needle.len())
            .any(|window| window == needle)
}

struct ArmoryAssetTarget {
    path: StringCopy<LISTED_FILE_PATH_MAX>,
    payload: bool,
}

impl ArmoryAssetTarget {
    fn path(&self) -> &str {
        self.path.as_str()
    }

    fn is_payload(&self) -> bool {
        self.payload
    }
}

fn armory_asset_target(request: &[u8]) -> Option<ArmoryAssetTarget> {
    let path = if request.starts_with(b"GET /api/armory/") {
        request_path_after_prefix(request, b"GET /api/armory/")?
    } else if request.starts_with(b"HEAD /api/armory/") {
        request_path_after_prefix(request, b"HEAD /api/armory/")?
    } else {
        return None;
    };

    let filename = decode_armory_asset_filename(path)?;
    let payload = filename.as_bytes() == b"payload.dd";
    let storage_path = if payload {
        StringCopy::from("payload.dd")
    } else {
        armory_storage_path(filename.as_str())?
    };

    Some(ArmoryAssetTarget {
        path: storage_path,
        payload,
    })
}

/// Extracts and decodes the filename from a DELETE Armory request.
///
/// `request` is the buffered HTTP request prefix. Returns a fixed-copy filename
/// when the path is valid and UTF-8.
fn armory_delete_filename(request: &[u8]) -> Option<StringCopy<LISTED_FILE_NAME_MAX>> {
    let path = request_path_after_prefix(request, b"DELETE /api/armory/")?;
    decode_armory_asset_filename(path)
}

fn request_path_after_prefix<'a>(request: &'a [u8], prefix: &[u8]) -> Option<&'a [u8]> {
    let mut end = prefix.len();
    while end < request.len() && request[end] != b' ' {
        end += 1;
    }

    if end == request.len() {
        return None;
    }

    Some(&request[prefix.len()..end])
}

fn valid_armory_asset_filename(filename: &[u8]) -> bool {
    if filename.is_empty() || filename.len() > LISTED_FILE_NAME_MAX {
        return false;
    }

    if filename == b"." || filename == b".." {
        return false;
    }

    filename
        .iter()
        .all(|byte| *byte != b'/' && *byte != b'\\' && *byte != 0)
}

fn decode_armory_asset_filename(path: &[u8]) -> Option<StringCopy<LISTED_FILE_NAME_MAX>> {
    let mut decoded = StringCopy::<LISTED_FILE_NAME_MAX> {
        bytes: [0u8; LISTED_FILE_NAME_MAX],
        len: 0,
    };
    let mut index = 0usize;

    while index < path.len() {
        let byte = if path[index] == b'%' {
            if index + 2 >= path.len() {
                return None;
            }
            let high = hex_digit(path[index + 1])?;
            let low = hex_digit(path[index + 2])?;
            index += 3;
            (high << 4) | low
        } else {
            let byte = path[index];
            index += 1;
            byte
        };

        if decoded.len >= decoded.bytes.len() {
            return None;
        }

        decoded.bytes[decoded.len] = byte;
        decoded.len += 1;
    }

    if !valid_armory_asset_filename(decoded.as_bytes()) {
        return None;
    }

    core::str::from_utf8(decoded.as_bytes()).ok()?;
    Some(decoded)
}

fn hex_digit(byte: u8) -> Option<u8> {
    match byte {
        b'0'..=b'9' => Some(byte - b'0'),
        b'a'..=b'f' => Some(byte - b'a' + 10),
        b'A'..=b'F' => Some(byte - b'A' + 10),
        _ => None,
    }
}

async fn read_armory_asset_chunk(
    storage: &'static Mutex<CriticalSectionRawMutex, StorageManager>,
    target: &ArmoryAssetTarget,
    offset: usize,
    buffer: &mut [u8],
) -> Result<usize, ()> {
    let storage_guard = storage.lock().await;
    storage_guard
        .read_at(target.path(), offset, buffer)
        .map_err(|_| ())
}

/// Prepares LittleFS for a new fixed Armory upload.
///
/// `storage` must already be locked by the caller. The function ensures the
/// Armory directory exists, removes stale Armory files, and truncates
/// `/armory/payload.bin`. It returns `Ok(())` when the file is ready for chunk
/// appends.
fn prepare_armory_upload(storage: &StorageManager) -> Result<(), ()> {
    storage.ensure_dir(ARMORY_DIR).map_err(|_| ())?;
    remove_existing_armory_files(storage)
}

/// Writes one upload chunk to an already-open LittleFS file.
///
/// `file` is the open `/armory/payload.bin` handle and `bytes` is the received
/// body chunk. Returns `Ok(())` only when LittleFS accepts the full chunk.
fn write_armory_upload_chunk(file: &LfsFile<'_, '_, FlashDriver>, bytes: &[u8]) -> Result<(), ()> {
    match file.write(bytes) {
        Ok(written) if written == bytes.len() => Ok(()),
        _ => Err(()),
    }
}

/// Removes all files under `/armory` before writing the fixed binary.
///
/// `storage` must already be locked by the caller. This prevents stale binaries
/// from consuming flash after a replacement upload.
fn remove_existing_armory_files(storage: &StorageManager) -> Result<(), ()> {
    let mut listed = [ListedFile::empty(); STARTUP_FILE_LIMIT];
    let count = storage
        .list_files(&mut listed)
        .map_err(|_| ())?
        .min(STARTUP_FILE_LIMIT);

    for file in &listed[..count] {
        let path = file.path();
        if path.starts_with(ARMORY_PREFIX) {
            storage.erase(path).map_err(|_| ())?;
        }
    }

    Ok(())
}

fn armory_storage_path(filename: &str) -> Option<StringCopy<LISTED_FILE_PATH_MAX>> {
    if filename != ARMORY_BINARY_NAME {
        return None;
    }

    armory_storage_path_unrestricted(filename)
}

/// Builds `/armory/<filename>` for an already validated Armory filename.
///
/// `filename` is copied into a fixed path buffer. Returns `None` if the path
/// would exceed the fixed LittleFS path buffer.
fn armory_storage_path_unrestricted(filename: &str) -> Option<StringCopy<LISTED_FILE_PATH_MAX>> {
    if !valid_armory_asset_filename(filename.as_bytes()) {
        return None;
    }

    let mut path = StringCopy::<LISTED_FILE_PATH_MAX> {
        bytes: [0u8; LISTED_FILE_PATH_MAX],
        len: 0,
    };
    let prefix = b"/armory/";
    let filename = filename.as_bytes();
    let len = prefix.len() + filename.len();

    if len > path.bytes.len() {
        return None;
    }

    path.bytes[..prefix.len()].copy_from_slice(prefix);
    path.bytes[prefix.len()..len].copy_from_slice(filename);
    path.len = len;
    core::str::from_utf8(path.as_bytes()).ok()?;
    Some(path)
}

struct PrefilteredSocket<'socket> {
    socket: TcpSocket<'socket>,
    prefix: [u8; HTTP_PREFLIGHT_BYTES],
    prefix_len: usize,
}

impl<'socket> PrefilteredSocket<'socket> {
    fn new(
        socket: TcpSocket<'socket>,
        prefix: [u8; HTTP_PREFLIGHT_BYTES],
        prefix_len: usize,
    ) -> Self {
        Self {
            socket,
            prefix,
            prefix_len,
        }
    }
}

struct PrefilteredReader<'a, R> {
    inner: R,
    prefix: &'a [u8],
    position: usize,
}

struct PrefilteredWriter<W> {
    inner: W,
}

impl<R: ErrorType> ErrorType for PrefilteredReader<'_, R> {
    type Error = R::Error;
}

impl<R: Read> Read for PrefilteredReader<'_, R> {
    async fn read(&mut self, buf: &mut [u8]) -> Result<usize, Self::Error> {
        if self.position < self.prefix.len() {
            let available = self.prefix.len() - self.position;
            let count = available.min(buf.len());
            buf[..count].copy_from_slice(&self.prefix[self.position..self.position + count]);
            self.position += count;
            return Ok(count);
        }

        self.inner.read(buf).await
    }
}

impl<W: ErrorType> ErrorType for PrefilteredWriter<W> {
    type Error = W::Error;
}

impl<W: Write> Write for PrefilteredWriter<W> {
    async fn write(&mut self, buf: &[u8]) -> Result<usize, Self::Error> {
        self.inner.write(buf).await
    }

    async fn flush(&mut self) -> Result<(), Self::Error> {
        self.inner.flush().await
    }
}

impl<'socket> Socket<EmbassyRuntime> for PrefilteredSocket<'socket> {
    type Error = embassy_net::tcp::Error;
    type ReadHalf<'a>
        = PrefilteredReader<'a, embassy_net::tcp::TcpReader<'a>>
    where
        'socket: 'a;
    type WriteHalf<'a>
        = PrefilteredWriter<embassy_net::tcp::TcpWriter<'a>>
    where
        'socket: 'a;

    fn split(&mut self) -> (Self::ReadHalf<'_>, Self::WriteHalf<'_>) {
        let (reader, writer) = self.socket.split();

        (
            PrefilteredReader {
                inner: reader,
                prefix: &self.prefix[..self.prefix_len],
                position: 0,
            },
            PrefilteredWriter { inner: writer },
        )
    }

    async fn abort<T: picoserve::time::Timer<EmbassyRuntime>>(
        self,
        timeouts: &Timeouts,
        timer: &mut T,
    ) -> Result<(), picoserve::Error<Self::Error>> {
        Socket::<EmbassyRuntime>::abort(self.socket, timeouts, timer).await
    }

    async fn shutdown<T: picoserve::time::Timer<EmbassyRuntime>>(
        self,
        timeouts: &Timeouts,
        timer: &mut T,
    ) -> Result<(), picoserve::Error<Self::Error>> {
        Socket::<EmbassyRuntime>::shutdown(self.socket, timeouts, timer).await
    }
}
