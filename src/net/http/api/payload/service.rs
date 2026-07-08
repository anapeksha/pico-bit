use crate::ducky::{DuckyParser, ErrorDiagnostic};
use crate::net::active_keyboard_os;
use crate::status::{self as status_led, Fault, Stage};
use crate::storage::{GLOBAL_STORAGE, SharedStorage};
use core::cell::RefCell;
use core::sync::atomic::{AtomicBool, Ordering};
use embassy_sync::blocking_mutex::Mutex;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::mutex::Mutex as AsyncMutex;
use littlefs2::io::Error as LfsError;
use picoserve::io::Write;
use picoserve::response::chunked::{ChunkWriter, ChunkedResponse, Chunks, ChunksWritten};
use picoserve::response::{IntoResponse, Json, StatusCode};
use serde::{Deserialize, Deserializer, Serialize};

pub(super) static TRIGGER_RUN: AtomicBool = AtomicBool::new(false);

pub(crate) fn consume_run_trigger() -> bool {
    TRIGGER_RUN.swap(false, Ordering::AcqRel)
}

#[derive(Serialize)]
pub(super) struct ValidationResponse {
    success: bool,
    error_line: Option<usize>,
    message: Option<&'static str>,
}

impl ValidationResponse {
    pub(super) fn is_error(&self) -> bool {
        !self.success
    }

    pub(crate) fn success(&self) -> bool {
        self.success
    }

    pub(crate) fn error_line(&self) -> Option<usize> {
        self.error_line
    }

    pub(crate) fn message(&self) -> Option<&'static str> {
        self.message
    }
}

#[derive(Serialize)]
pub(super) struct RunResponse {
    success: bool,
    message: &'static str,
    error_line: Option<usize>,
}

impl RunResponse {
    pub(super) fn is_error(&self) -> bool {
        !self.success
    }

    pub(crate) fn success(&self) -> bool {
        self.success
    }

    pub(crate) fn error_line(&self) -> Option<usize> {
        self.error_line
    }

    pub(crate) fn message(&self) -> &'static str {
        self.message
    }
}

pub(super) fn read_response() -> impl IntoResponse {
    ChunkedResponse::new(PayloadChunks)
}

pub(super) async fn save_response() -> impl IntoResponse {
    let response = save_staged().await;
    let status = status_for_validation(response.is_error());
    Json(response).into_response().with_status_code(status)
}

pub(super) async fn run_response() -> impl IntoResponse {
    let response = trigger_run().await;
    let status = status_for_validation(response.is_error());
    Json(response).into_response().with_status_code(status)
}

fn status_for_validation(is_error: bool) -> StatusCode {
    if is_error {
        StatusCode::BAD_REQUEST
    } else {
        StatusCode::OK
    }
}

pub(super) struct SavePayloadRequest;

struct CodeStringWrapper;

struct StagingBuffer {
    bytes: [u8; 2048],
    len: usize,
}

struct ReadBuffer {
    bytes: [u8; 2048],
    len: usize,
}

static STAGING_BUFFER: Mutex<CriticalSectionRawMutex, RefCell<StagingBuffer>> =
    Mutex::new(RefCell::new(StagingBuffer {
        bytes: [0u8; 2048],
        len: 0,
    }));
static READ_BUFFER: Mutex<CriticalSectionRawMutex, RefCell<ReadBuffer>> =
    Mutex::new(RefCell::new(ReadBuffer {
        bytes: [0u8; 2048],
        len: 0,
    }));
static READ_SCRATCH: AsyncMutex<CriticalSectionRawMutex, [u8; 2048]> = AsyncMutex::new([0u8; 2048]);

impl<'de> Deserialize<'de> for CodeStringWrapper {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        struct StrVisitor;

        impl<'de> serde::de::Visitor<'de> for StrVisitor {
            type Value = CodeStringWrapper;

            fn expecting(&self, formatter: &mut core::fmt::Formatter) -> core::fmt::Result {
                formatter.write_str("a string up to 2048 bytes long")
            }

            fn visit_str<E>(self, v: &str) -> Result<Self::Value, E>
            where
                E: serde::de::Error,
            {
                if v.len() > 2048 {
                    return Err(E::custom("Payload content exceeds 2048 bytes"));
                }

                stage(v);

                Ok(CodeStringWrapper)
            }

            fn visit_borrowed_str<E>(self, v: &'de str) -> Result<Self::Value, E>
            where
                E: serde::de::Error,
            {
                self.visit_str(v)
            }
        }

        deserializer.deserialize_str(StrVisitor)
    }
}

impl<'de> Deserialize<'de> for SavePayloadRequest {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        struct MapVisitor;

        impl<'de> serde::de::Visitor<'de> for MapVisitor {
            type Value = SavePayloadRequest;

            fn expecting(&self, formatter: &mut core::fmt::Formatter) -> core::fmt::Result {
                formatter.write_str("a JSON object containing a 'code' field")
            }

            fn visit_map<A>(self, mut map: A) -> Result<Self::Value, A::Error>
            where
                A: serde::de::MapAccess<'de>,
            {
                let mut found_code = false;

                while let Some(key) = map.next_key::<&str>()? {
                    if key == "code" {
                        let _: CodeStringWrapper = map.next_value()?;
                        found_code = true;
                    } else {
                        let _: serde::de::IgnoredAny = map.next_value()?;
                    }
                }

                if found_code {
                    Ok(SavePayloadRequest)
                } else {
                    Err(serde::de::Error::missing_field("code"))
                }
            }
        }

        deserializer.deserialize_map(MapVisitor)
    }
}

pub(super) fn stage(code: &str) {
    STAGING_BUFFER.lock(|cell| {
        let mut staging = cell.borrow_mut();
        staging.bytes[..code.len()].copy_from_slice(code.as_bytes());
        staging.len = code.len();
    });
}

fn storage() -> &'static SharedStorage {
    let ptr = GLOBAL_STORAGE.load(Ordering::Acquire);
    if ptr.is_null() {
        panic!("GLOBAL_STORAGE accessed before initialization!");
    }
    unsafe { &*ptr }
}

fn validate_script_bytes(bytes: &[u8]) -> Result<(), (Option<usize>, &'static str)> {
    let valid_str = match core::str::from_utf8(bytes) {
        Ok(s) => s,
        Err(_) => return Err((None, "Invalid UTF-8 sequence sent in payload body.")),
    };

    for (line_num, line) in (1..).zip(valid_str.lines()) {
        let trimmed = line.trim();
        if !trimmed.is_empty()
            && let Err(ducky_err) = DuckyParser::parse_line_for_os(trimmed, active_keyboard_os())
        {
            let diagnostic = ErrorDiagnostic::new(line_num, ducky_err, line);
            diagnostic.log_diagnostic();

            return Err((Some(diagnostic.line_number), "Syntax validation failed."));
        }
    }

    Ok(())
}

fn validate_staged_buffer() -> Result<(), (Option<usize>, &'static str)> {
    STAGING_BUFFER.lock(|cell| {
        let staging = cell.borrow();
        validate_script_bytes(&staging.bytes[..staging.len])
    })
}

#[derive(Clone, Copy)]
pub(super) struct PayloadChunks;

impl Chunks for PayloadChunks {
    fn content_type(&self) -> &'static str {
        "application/json"
    }

    async fn write_chunks<W: Write>(
        self,
        mut writer: ChunkWriter<W>,
    ) -> Result<ChunksWritten, W::Error> {
        refresh_read_buffer().await;

        writer.write_chunk(b"{\"code\":").await?;
        write_read_buffer_json_string(&mut writer).await?;
        writer.write_chunk(b"}").await?;

        writer.finalize().await
    }
}

async fn refresh_read_buffer() {
    let storage = storage();
    let storage_guard = storage.lock().await;
    let mut scratch = READ_SCRATCH.lock().await;
    let len = match storage_guard.read("payload.dd", &mut scratch[..]) {
        Ok(bytes) => bytes.len(),
        Err(LfsError::NO_SUCH_ENTRY) => {
            status_led::error(Fault::PayloadFindFailed);
            0
        }
        Err(_) => {
            status_led::error(Fault::PayloadReadFailed);
            0
        }
    };

    READ_BUFFER.lock(|read_cell| {
        let mut read = read_cell.borrow_mut();
        read.bytes[..len].copy_from_slice(&scratch[..len]);
        read.len = len;
    });
}

async fn write_read_buffer_json_string<W: Write>(
    writer: &mut ChunkWriter<W>,
) -> Result<(), W::Error> {
    let len = READ_BUFFER.lock(|cell| cell.borrow().len);
    let mut offset = 0usize;
    let mut buffer = [0u8; 96];

    writer.write_chunk(b"\"").await?;

    while offset < len {
        let copied = READ_BUFFER.lock(|cell| {
            let read = cell.borrow();
            let count = (len - offset).min(buffer.len());
            buffer[..count].copy_from_slice(&read.bytes[offset..offset + count]);
            count
        });

        write_json_string_bytes(writer, &buffer[..copied]).await?;
        offset += copied;
    }

    writer.write_chunk(b"\"").await
}

async fn write_json_string_bytes<W: Write>(
    writer: &mut ChunkWriter<W>,
    bytes: &[u8],
) -> Result<(), W::Error> {
    let mut start = 0usize;
    let mut index = 0usize;

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
            writer.write_chunk(&bytes[start..index]).await?;
        }

        if let Some(escape) = escape {
            writer.write_chunk(escape).await?;
        } else {
            let escaped = json_unicode_escape(bytes[index]);
            writer.write_chunk(&escaped).await?;
        }

        index += 1;
        start = index;
    }

    if start < bytes.len() {
        writer.write_chunk(&bytes[start..]).await?;
    }

    Ok(())
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

pub(super) async fn save_staged() -> ValidationResponse {
    if let Err((error_line, _)) = validate_staged_buffer() {
        status_led::error(Fault::ScriptError);
        return ValidationResponse {
            success: false,
            error_line,
            message: Some("Syntax validation failed. Flash update aborted."),
        };
    }

    let storage = storage();
    let storage_guard = storage.lock().await;

    let write_result = STAGING_BUFFER.lock(|cell| {
        let mut staging = cell.borrow_mut();
        let len = staging.len;
        let target_slice = &mut staging.bytes[..len];

        storage_guard.write("payload.dd", target_slice)
    });

    match write_result {
        Ok(_) => ValidationResponse {
            success: true,
            error_line: None,
            message: Some("Payload updated successfully."),
        },
        Err(_) => {
            status_led::error(Fault::PayloadReadFailed);
            ValidationResponse {
                success: false,
                error_line: None,
                message: Some("Error: Hardware flash partition write execution failed."),
            }
        }
    }
}

pub(super) async fn trigger_run() -> RunResponse {
    refresh_read_buffer().await;

    let validation = READ_BUFFER.lock(|cell| {
        let read = cell.borrow();
        validate_script_bytes(&read.bytes[..read.len])
    });

    if let Err((error_line, message)) = validation {
        status_led::error(Fault::ScriptError);
        return RunResponse {
            success: false,
            message,
            error_line,
        };
    }

    TRIGGER_RUN.store(true, Ordering::Release);
    status_led::show(Stage::PayloadRunning);
    RunResponse {
        success: true,
        message: "Payload injection sequence initialized.",
        error_line: None,
    }
}
