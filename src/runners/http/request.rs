use embassy_net::tcp::TcpSocket;
use embassy_time::{Duration, with_timeout};

pub(super) async fn read_prefetched_request(
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

pub(super) fn request_body(request: &[u8]) -> Option<&[u8]> {
    let header_end = header_end_index(request)?;
    let body_start = header_end + 4;
    let content_length = content_length(&request[..header_end]).unwrap_or(0);
    let body_end = (body_start + content_length).min(request.len());
    Some(&request[body_start..body_end])
}

pub(super) fn keyboard_layout_from_body(body: &[u8]) -> Option<&'static str> {
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

pub(super) fn keyboard_os_from_body(body: &[u8]) -> Option<&'static str> {
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
