use embassy_net::tcp::TcpSocket;
use picoserve::io::Write;

pub(super) struct StringCopy<const N: usize> {
    bytes: [u8; N],
    len: usize,
}

impl<const N: usize> StringCopy<N> {
    pub(super) fn from(value: &str) -> Self {
        let mut copy = Self {
            bytes: [0u8; N],
            len: 0,
        };
        let bytes = value.as_bytes();
        copy.len = bytes.len().min(N);
        copy.bytes[..copy.len].copy_from_slice(&bytes[..copy.len]);
        copy
    }

    pub(super) fn as_bytes(&self) -> &[u8] {
        &self.bytes[..self.len]
    }
}

pub(super) async fn write_json_headers(
    socket: &mut TcpSocket<'_>,
) -> Result<(), embassy_net::tcp::Error> {
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

pub(super) async fn write_http_chunk(
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

pub(super) async fn write_final_chunk(
    socket: &mut TcpSocket<'_>,
) -> Result<(), embassy_net::tcp::Error> {
    socket.write_all(b"0\r\n\r\n").await?;
    socket.close();
    socket.flush().await
}

pub(super) async fn write_json_usize(
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

pub(super) async fn write_json_string_bytes(
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

pub(super) async fn write_chunk_size(
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
