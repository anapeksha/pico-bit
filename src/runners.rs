use cyw43::PowerManagementMode::Performance;
use cyw43::{A4, Aligned, Runner as Cyw43Runner, State, aligned_bytes};
use cyw43_pio::PioSpi;
use embassy_net::tcp::TcpSocket;
use embassy_net::{Runner as NetRunner, Stack};
use embassy_rp::gpio::Output;
use embassy_rp::peripherals::{PIO0, USB};
use embassy_rp::usb::Driver;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::mutex::Mutex;
use embassy_time::{Duration, Timer, with_timeout};
use embassy_usb::UsbDevice;
use embassy_usb::class::cdc_ncm::embassy_net::{Device, Runner as NcmRunner};
use embassy_usb::class::hid::HidWriter;
use leasehund::DhcpServer;
use littlefs2::io::Error;
use picoserve::io::{ErrorType, Read, Socket, Write};
use picoserve::{Config, DisconnectionInfo, EmbassyRuntime, Server, Timeouts};

use defmt::{error, info, warn};
use embassy_executor::Spawner;
use static_cell::StaticCell;
use usbd_hid::descriptor::KeyboardReport;

use crate::ducky::{DuckyError, DuckyExecutor, DuckyParser, StatefulWriter};
use crate::net::{AppRouter, init_wifi_dhcp, init_wifi_network};
use crate::storage::StorageManager;

const MTU: usize = 1514;
const HTTP_PREFLIGHT_BYTES: usize = 8;
const HTTP_PREFLIGHT_TIMEOUT_MS: u64 = 300;

static FW_BUF: &Aligned<A4, [u8]> = aligned_bytes!("../firmware/43439A0.bin");
static CLM_BUF: &Aligned<A4, [u8]> = aligned_bytes!("../firmware/43439A0_clm.bin");
static NVRAM_BUF: &Aligned<A4, [u8]> = aligned_bytes!("../firmware/nvram_rp2040.bin");

static STATE_STATIC: StaticCell<State> = StaticCell::new();
static ROUTER: StaticCell<AppRouter> = StaticCell::new();

#[embassy_executor::task]
pub async fn usb_task(mut usb: UsbDevice<'static, Driver<'static, USB>>) {
    usb.run().await;
}

#[embassy_executor::task]
pub async fn ncm_task(runner: NcmRunner<'static, Driver<'static, USB>, MTU>) {
    runner.run().await;
}

#[embassy_executor::task]
pub async fn net_task(mut runner: NetRunner<'static, Device<'static, MTU>>) {
    runner.run().await;
}

#[embassy_executor::task]
pub async fn hid_task(
    mut hid: HidWriter<'static, Driver<'static, USB>, 8>,
    storage: &'static Mutex<CriticalSectionRawMutex, StorageManager>,
) {
    info!("Waiting for USB HID execution layer readiness...");
    hid.ready().await;
    info!("USB HID Connected! Initializing runner loop...");

    let mut content_buffer = [0u8; 2048];
    let mut hardware_writer = EmbassyUsbWriter { writer: &mut hid };
    let mut executor = DuckyExecutor::new();
    executor.set_keyboard_layout(crate::net::active_keyboard_layout());

    if let Err(e) = run_script_payload(
        &mut hardware_writer,
        &mut executor,
        storage,
        &mut content_buffer,
    )
    .await
    {
        error!("Script execution failed: {:?}", e);
    }

    loop {
        Timer::after_secs(1).await;
    }
}

#[embassy_executor::task]
pub async fn dhcp_task(mut server: DhcpServer<32, 4>, stack: &'static Stack<'static>) {
    server.run(*stack).await;
}

#[embassy_executor::task]
async fn raw_wifi_runner(
    runner: Cyw43Runner<'static, cyw43::SpiBus<Output<'static>, PioSpi<'static, PIO0, 0>>>,
) {
    runner.run().await;
}

#[embassy_executor::task]
async fn wifi_net_task(mut runner: embassy_net::Runner<'static, cyw43::NetDriver<'static>>) {
    runner.run().await;
}

#[embassy_executor::task]
async fn wifi_dhcp_task(mut server: DhcpServer<32, 4>, stack: &'static Stack<'static>) {
    server.run(*stack).await;
}

#[embassy_executor::task]
async fn server_task(
    stack: &'static Stack<'static>,
    router: &'static AppRouter,
    _storage: &'static Mutex<CriticalSectionRawMutex, StorageManager>,
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

        if is_root_asset_request(&prefix[..prefix_len]) {
            info!("[Worker] Serving root asset directly.");
            if let Err(e) = serve_root_asset(&mut socket).await {
                warn!("[Worker] Root asset response failed: {:?}", e);
            }
            continue;
        }

        let socket = PrefilteredSocket {
            socket,
            prefix,
            prefix_len,
        };

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

async fn serve_root_asset(socket: &mut TcpSocket<'_>) -> Result<(), embassy_net::tcp::Error> {
    socket
        .write_all(
            b"HTTP/1.1 200 OK\r\n\
Content-Type: text/html\r\n\
Content-Encoding: gzip\r\n\
Vary: Accept-Encoding\r\n\
Transfer-Encoding: chunked\r\n\
Connection: close\r\n\
\r\n",
        )
        .await?;

    for chunk in crate::net::compressed_index_html().chunks(1024) {
        write_chunk_size(socket, chunk.len()).await?;
        socket.write_all(b"\r\n").await?;
        socket.write_all(chunk).await?;
        socket.write_all(b"\r\n").await?;
    }

    socket.write_all(b"0\r\n\r\n").await?;
    socket.close();
    socket.flush().await
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

fn is_root_asset_request(bytes: &[u8]) -> bool {
    bytes.starts_with(b"GET / ") || bytes.starts_with(b"HEAD / ")
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

struct PrefilteredSocket<'socket> {
    socket: TcpSocket<'socket>,
    prefix: [u8; HTTP_PREFLIGHT_BYTES],
    prefix_len: usize,
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

#[embassy_executor::task]
pub async fn wifi_task(
    spi: PioSpi<'static, PIO0, 0>,
    pwr: Output<'static>,
    spawner: Spawner,
    storage: &'static Mutex<CriticalSectionRawMutex, StorageManager>,
) {
    let state = STATE_STATIC.init(cyw43::State::new());
    let (wifi_device, mut control, wifi_runner) =
        cyw43::new(state, pwr, spi, FW_BUF, NVRAM_BUF).await;

    spawner.spawn(raw_wifi_runner(wifi_runner)).unwrap();

    let router = ROUTER.init(AppRouter);

    // 4. Load the configuration blocks
    control.init(CLM_BUF).await;
    control.set_power_management(Performance).await;

    // 5. Initialize the access point stack
    let (wifi_net_stack, wifi_net_runner) = init_wifi_network(control, wifi_device, 5678).await;
    let wifi_dhcp = init_wifi_dhcp();

    info!("Starting network loops...");

    spawner.spawn(wifi_net_task(wifi_net_runner)).unwrap();
    spawner
        .spawn(wifi_dhcp_task(wifi_dhcp, wifi_net_stack))
        .unwrap();
    spawner
        .spawn(server_task(wifi_net_stack, router, storage))
        .unwrap();
}

struct EmbassyUsbWriter<'a> {
    writer: &'a mut HidWriter<'static, Driver<'static, USB>, 8>,
}

impl<'a> StatefulWriter for EmbassyUsbWriter<'a> {
    async fn write_report(&mut self, report: &KeyboardReport) {
        let bytes: [u8; 8] = unsafe { core::mem::transmute_copy(report) };
        let _ = self.writer.write(&bytes).await;
    }

    async fn clear_report(&mut self) {
        let blank = [0u8; 8];
        let _ = self.writer.write(&blank).await;
    }

    async fn delay_ms(&mut self, ms: u32) {
        Timer::after_millis(ms as u64).await;
    }
}

async fn run_script_payload<'buf>(
    writer: &mut EmbassyUsbWriter<'_>,
    executor: &mut DuckyExecutor<'buf>,
    storage: &'static Mutex<CriticalSectionRawMutex, StorageManager>,
    content_buffer: &'buf mut [u8; 2048],
) -> Result<(), crate::ducky::DuckyError> {
    // Step 1: Isolate the storage read into a tight block.
    // This guarantees the Mutex Guard is dropped BEFORE the loop starts.
    let bytes_written_len = {
        let storage_guard = storage.lock().await;
        match storage_guard.read("payload.dd", content_buffer) {
            Ok(bytes) => bytes.len(), // Just keep the numeric size
            Err(Error::NO_SUCH_ENTRY) => {
                warn!("payload.dd not found in storage. Executing fallback...");
                // Copy fallback directly into your buffer to maintain a single memory layout
                let fallback = b"REM Stateless Fallback\nDELAY 500\n";
                content_buffer[..fallback.len()].copy_from_slice(fallback);
                fallback.len()
            }
            Err(_) => {
                error!("Storage read failed due to an unexpected driver error.");
                return Err(crate::ducky::DuckyError::UnknownCommand);
            }
        }
    }; // <--- storage_guard is completely wiped from the stack frame here!

    // Convert only the slice we actually filled
    let script_text = core::str::from_utf8(&content_buffer[..bytes_written_len])
        .map_err(|_| DuckyError::InvalidKey)?;

    let mut current_line_idx = 1;
    for raw_line in script_text.lines() {
        let trimmed = raw_line.trim();
        if trimmed.is_empty() {
            continue;
        }

        if let Ok(command) = DuckyParser::parse_line(trimmed) {
            // The compiler now only tracks the individual execution sub-future here
            match executor
                .execute_command(command, current_line_idx, writer)
                .await
            {
                Ok(Some(custom_delay)) => Timer::after_millis(custom_delay as u64).await,
                Ok(None) => {}
                Err(e) => error!("Line {} Exec Error: {:?}", current_line_idx, e),
            }
        } else {
            error!("Line {} Parse Error", current_line_idx);
        }
        current_line_idx += 1;
    }

    info!("Payload execution loop completed.");
    Ok(())
}
