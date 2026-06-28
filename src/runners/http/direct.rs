use embassy_net::tcp::TcpSocket;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::mutex::Mutex;
use picoserve::io::Write;

use crate::storage::{ListedFile, StorageManager};

use super::json::{
    StringCopy, write_chunk_size, write_final_chunk, write_http_chunk, write_json_headers,
    write_json_string_bytes, write_json_usize,
};
use super::request::{
    keyboard_layout_from_body, keyboard_os_from_body, read_prefetched_request, request_body,
};

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

pub(super) async fn serve_bootstrap(
    socket: &mut TcpSocket<'_>,
) -> Result<(), embassy_net::tcp::Error> {
    write_json_headers(socket).await?;

    let (keyboard_os, keyboard_layout) = crate::net::active_keyboard_target_codes();

    write_http_chunk(socket, b"{\"ap_password\":").await?;
    write_json_string_bytes(socket, crate::net::wifi_ap_password().as_bytes()).await?;
    write_http_chunk(socket, b",\"ap_ssid\":").await?;
    write_json_string_bytes(socket, crate::net::wifi_ap_ssid().as_bytes()).await?;
    write_http_chunk(socket, b",\"host_hid_active\":true,\"keyboard_layout\":").await?;
    write_json_string_bytes(socket, keyboard_layout.as_bytes()).await?;
    write_http_chunk(socket, b",\"keyboard_os\":").await?;
    write_json_string_bytes(socket, keyboard_os.as_bytes()).await?;
    write_http_chunk(
        socket,
        b",\"ncm_active\":true,\"ncm_url\":\"http://192.168.7.1\",\"seeded\":false}",
    )
    .await?;

    write_final_chunk(socket).await
}

pub(super) async fn serve_keyboard_target(
    socket: &mut TcpSocket<'_>,
    prefix: &[u8],
) -> Result<(), embassy_net::tcp::Error> {
    let mut request = [0u8; 1024];
    let request_len = read_prefetched_request(socket, prefix, &mut request).await;
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
