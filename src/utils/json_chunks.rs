use picoserve::io::Write;
use picoserve::response::chunked::ChunkWriter;

pub async fn raw<W: Write>(writer: &mut ChunkWriter<W>, bytes: &[u8]) -> Result<(), W::Error> {
    writer.write_chunk(bytes).await
}

pub async fn bool_value<W: Write>(
    writer: &mut ChunkWriter<W>,
    value: bool,
) -> Result<(), W::Error> {
    raw(writer, if value { b"true" } else { b"false" }).await
}

pub async fn usize_value<W: Write>(
    writer: &mut ChunkWriter<W>,
    value: usize,
) -> Result<(), W::Error> {
    writer.write_fmt(format_args!("{value}")).await
}

pub async fn string<W: Write>(writer: &mut ChunkWriter<W>, value: &str) -> Result<(), W::Error> {
    string_start(writer).await?;
    string_bytes(writer, value.as_bytes()).await?;
    string_end(writer).await
}

pub async fn string_start<W: Write>(writer: &mut ChunkWriter<W>) -> Result<(), W::Error> {
    raw(writer, b"\"").await
}

pub async fn string_end<W: Write>(writer: &mut ChunkWriter<W>) -> Result<(), W::Error> {
    raw(writer, b"\"").await
}

pub async fn string_bytes<W: Write>(
    writer: &mut ChunkWriter<W>,
    bytes: &[u8],
) -> Result<(), W::Error> {
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
            raw(writer, &bytes[start..index]).await?;
        }

        if let Some(escape) = escape {
            raw(writer, escape).await?;
        } else {
            let escaped = unicode_escape(bytes[index]);
            raw(writer, &escaped).await?;
        }

        index += 1;
        start = index;
    }

    if start < bytes.len() {
        raw(writer, &bytes[start..]).await?;
    }

    Ok(())
}

fn unicode_escape(byte: u8) -> [u8; 6] {
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
