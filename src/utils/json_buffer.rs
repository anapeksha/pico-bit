#[cfg(feature = "firmware")]
use picoserve::io::Write;
#[cfg(feature = "firmware")]
use picoserve::response::chunked::ChunkWriter;

const JSON_CHUNK_BUFFER_SIZE: usize = 512;

#[allow(async_fn_in_trait)]
pub(crate) trait JsonChunkSink {
    type Error;

    async fn write_json_chunk(&mut self, bytes: &[u8]) -> Result<(), Self::Error>;
}

#[cfg(feature = "firmware")]
impl<W: Write> JsonChunkSink for ChunkWriter<W> {
    type Error = W::Error;

    async fn write_json_chunk(&mut self, bytes: &[u8]) -> Result<(), Self::Error> {
        self.write_chunk(bytes).await
    }
}

pub(crate) struct JsonChunkBuffer<'a, S: JsonChunkSink> {
    sink: &'a mut S,
    buffer: [u8; JSON_CHUNK_BUFFER_SIZE],
    len: usize,
}

impl<'a, S: JsonChunkSink> JsonChunkBuffer<'a, S> {
    pub(crate) fn new(sink: &'a mut S) -> Self {
        Self {
            sink,
            buffer: [0u8; JSON_CHUNK_BUFFER_SIZE],
            len: 0,
        }
    }

    pub(crate) async fn flush(&mut self) -> Result<(), S::Error> {
        if self.len > 0 {
            self.sink.write_json_chunk(&self.buffer[..self.len]).await?;
            self.len = 0;
        }

        Ok(())
    }

    pub(crate) async fn raw(&mut self, mut bytes: &[u8]) -> Result<(), S::Error> {
        while !bytes.is_empty() {
            if self.len == self.buffer.len() {
                self.flush().await?;
            }

            let available = self.buffer.len() - self.len;
            let count = bytes.len().min(available);
            self.buffer[self.len..self.len + count].copy_from_slice(&bytes[..count]);
            self.len += count;
            bytes = &bytes[count..];
        }

        Ok(())
    }

    pub(crate) async fn string_start(&mut self) -> Result<(), S::Error> {
        self.raw(b"\"").await
    }

    pub(crate) async fn string_end(&mut self) -> Result<(), S::Error> {
        self.raw(b"\"").await
    }

    pub(crate) async fn string_bytes(&mut self, bytes: &[u8]) -> Result<(), S::Error> {
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
                self.raw(&bytes[start..index]).await?;
            }

            if let Some(escape) = escape {
                self.raw(escape).await?;
            } else {
                let escaped = unicode_escape(bytes[index]);
                self.raw(&escaped).await?;
            }

            index += 1;
            start = index;
        }

        if start < bytes.len() {
            self.raw(&bytes[start..]).await?;
        }

        Ok(())
    }
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

#[cfg(test)]
mod tests {
    extern crate std;

    use super::{JsonChunkBuffer, JsonChunkSink};
    use core::convert::Infallible;
    use core::future::Future;
    use core::pin::Pin;
    use core::task::{Context, Poll, RawWaker, RawWakerVTable, Waker};
    use std::string::String;
    use std::vec::Vec;

    #[derive(Default)]
    struct TestSink {
        chunks: Vec<Vec<u8>>,
    }

    impl JsonChunkSink for TestSink {
        type Error = Infallible;

        async fn write_json_chunk(&mut self, bytes: &[u8]) -> Result<(), Self::Error> {
            self.chunks.push(bytes.to_vec());
            Ok(())
        }
    }

    fn block_on<F: Future>(future: F) -> F::Output {
        fn raw_waker() -> RawWaker {
            fn clone(_: *const ()) -> RawWaker {
                raw_waker()
            }
            fn noop(_: *const ()) {}

            RawWaker::new(
                core::ptr::null(),
                &RawWakerVTable::new(clone, noop, noop, noop),
            )
        }

        let waker = unsafe { Waker::from_raw(raw_waker()) };
        let mut context = Context::from_waker(&waker);
        let mut future = core::pin::pin!(future);

        loop {
            match Future::poll(Pin::as_mut(&mut future), &mut context) {
                Poll::Ready(value) => return value,
                Poll::Pending => {}
            }
        }
    }

    #[test]
    fn escapes_json_strings_without_splitting_contract_bytes() {
        let mut sink = TestSink::default();

        block_on(async {
            let mut json = JsonChunkBuffer::new(&mut sink);
            json.string_start().await.unwrap();
            json.string_bytes("a\"b\\c\n\r\t\u{1f}".as_bytes())
                .await
                .unwrap();
            json.string_end().await.unwrap();
            json.flush().await.unwrap();
        });

        let output = String::from_utf8(sink.chunks.concat()).unwrap();
        assert_eq!(output, "\"a\\\"b\\\\c\\n\\r\\t\\u001f\"");
    }

    #[test]
    fn coalesces_large_writes_into_bounded_chunks() {
        let mut sink = TestSink::default();

        block_on(async {
            let mut json = JsonChunkBuffer::new(&mut sink);
            json.raw(&[b'a'; 1200]).await.unwrap();
            json.flush().await.unwrap();
        });

        assert_eq!(sink.chunks.len(), 3);
        assert_eq!(sink.chunks[0].len(), 512);
        assert_eq!(sink.chunks[1].len(), 512);
        assert_eq!(sink.chunks[2].len(), 176);
    }
}
