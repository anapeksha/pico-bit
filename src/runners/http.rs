use defmt::{error, info, warn};
use embassy_net::Stack;
use embassy_net::tcp::TcpSocket;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::mutex::Mutex;
use embassy_time::{Duration, with_timeout};
use picoserve::io::{ErrorType, Read, Socket, Write};
use picoserve::{Config, DisconnectionInfo, EmbassyRuntime, Server, Timeouts};

use crate::net::AppRouter;
use crate::storage::StorageManager;

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
                info!("[Worker] Serving root asset.");
                if let Err(e) = serve_root_asset(&mut socket).await {
                    warn!("[Worker] Root asset response failed: {:?}", e);
                }
                continue;
            }
            StartupRequest::Bootstrap => {
                info!("[Worker] Serving bootstrap.");
                if let Err(e) = serve_bootstrap(&mut socket).await {
                    warn!("[Worker] Bootstrap response failed: {:?}", e);
                }
                continue;
            }
            StartupRequest::Armory => {
                info!("[Worker] Serving armory.");
                if let Err(e) = serve_armory(&mut socket, storage).await {
                    warn!("[Worker] Armory response failed: {:?}", e);
                }
                continue;
            }
            StartupRequest::Payload => {
                info!("[Worker] Serving payload.");
                if let Err(e) = serve_payload(&mut socket, storage).await {
                    warn!("[Worker] Payload response failed: {:?}", e);
                }
                continue;
            }
            StartupRequest::Runs => {
                info!("[Worker] Serving runs.");
                if let Err(e) = serve_runs(&mut socket).await {
                    warn!("[Worker] Runs response failed: {:?}", e);
                }
                continue;
            }
            StartupRequest::IgnoredBrowserProbe => {
                info!("[Worker] Serving browser probe.");
                if let Err(e) = serve_empty_not_found(&mut socket).await {
                    warn!("[Worker] Browser probe response failed: {:?}", e);
                }
                continue;
            }
            StartupRequest::OtherGet => {
                info!("[Worker] Serving unhandled browser GET.");
                if let Err(e) = serve_empty_not_found(&mut socket).await {
                    warn!("[Worker] Unhandled GET response failed: {:?}", e);
                }
                continue;
            }
            StartupRequest::Options => {
                info!("[Worker] Serving OPTIONS.");
                if let Err(e) = serve_no_content(&mut socket).await {
                    warn!("[Worker] OPTIONS response failed: {:?}", e);
                }
                continue;
            }
            StartupRequest::KeyboardTarget => {
                info!("[Worker] Serving keyboard target.");
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

#[derive(Clone, Copy)]
enum StartupRequest {
    Root,
    Bootstrap,
    Armory,
    Payload,
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

    if request_starts_with(bytes, b"GET /api/payload ") {
        return StartupRequest::Payload;
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

use crate::storage::ListedFile;
const STARTUP_FILE_LIMIT: usize = 16;

static STARTUP_LISTED_FILES: Mutex<CriticalSectionRawMutex, [ListedFile; STARTUP_FILE_LIMIT]> =
    Mutex::new([ListedFile::empty(); STARTUP_FILE_LIMIT]);

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

pub(super) async fn serve_bootstrap(
    socket: &mut TcpSocket<'_>,
) -> Result<(), embassy_net::tcp::Error> {
    let (keyboard_os, keyboard_layout) = crate::net::active_keyboard_target_codes();
    let mut body = FixedBody::<512>::new();

    body.raw(b"{\"ap_password\":");
    body.json_string(crate::net::wifi_ap_password().as_bytes());
    body.raw(b",\"ap_ssid\":");
    body.json_string(crate::net::wifi_ap_ssid().as_bytes());
    body.raw(b",\"host_hid_active\":true,\"keyboard_layout\":");
    body.json_string(keyboard_layout.as_bytes());
    body.raw(b",\"keyboard_os\":");
    body.json_string(keyboard_os.as_bytes());
    body.raw(b",\"ncm_active\":true,\"ncm_url\":\"http://192.168.7.1\",\"seeded\":false}");

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
}

pub(super) async fn serve_keyboard_target(
    socket: &mut TcpSocket<'_>,
    prefix: &[u8],
) -> Result<(), embassy_net::tcp::Error> {
    let mut request = [0u8; 1024];
    let request_len = socket_read_prefetched_request(socket, prefix, &mut request).await;
    let body = request_body(&request[..request_len]).unwrap_or(&[]);

    let (current_os, current_layout) = crate::net::active_keyboard_target_codes();
    let os = keyboard_os_from_body(body).unwrap_or(current_os);
    let layout = keyboard_layout_from_body(body).unwrap_or(current_layout);
    let ok = crate::net::update_keyboard_target_codes(os, layout);

    let (response_os, response_layout) = crate::net::active_keyboard_target_codes();

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

pub(super) async fn serve_runs(socket: &mut TcpSocket<'_>) -> Result<(), embassy_net::tcp::Error> {
    write_json_headers(socket).await?;
    write_http_chunk(
        socket,
        b"{\"run_history\":[{\"ok\":true,\"preview\":\"payload.dd\",\"sequence\":1,\"source\":\"bootstrap\"}],\"seeded\":false}",
    )
    .await?;
    write_final_chunk(socket).await
}

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

pub(super) async fn serve_armory(
    socket: &mut TcpSocket<'_>,
    storage: &'static Mutex<CriticalSectionRawMutex, StorageManager>,
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

        if written > 0 {
            write_http_chunk(socket, b",").await?;
        }
        written += 1;

        if !is_payload {
            has_binary = true;
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
}

async fn write_fixed_json_response(
    socket: &mut TcpSocket<'_>,
    body: &[u8],
) -> Result<(), embassy_net::tcp::Error> {
    socket
        .write_all(
            b"HTTP/1.1 200 OK\r\n\
Content-Type: application/json\r\n\
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
