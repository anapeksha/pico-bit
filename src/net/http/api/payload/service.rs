use crate::ducky::{DuckyParser, ErrorDiagnostic};
use crate::storage::{GLOBAL_STORAGE, SharedStorage};
use core::cell::RefCell;
use core::sync::atomic::{AtomicBool, Ordering};
use embassy_sync::blocking_mutex::Mutex;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use serde::{Deserialize, Deserializer, Serialize};

pub(super) static TRIGGER_RUN: AtomicBool = AtomicBool::new(false);

#[derive(Serialize)]
pub(super) struct PayloadResponse<'a> {
    code: &'a str,
}

#[derive(Serialize)]
pub(super) struct ValidationResponse {
    success: bool,
    error_line: Option<usize>,
    message: Option<&'static str>,
}

#[derive(Serialize)]
pub(super) struct RunResponse {
    success: bool,
    message: &'static str,
}

pub(super) struct SavePayloadRequest;

struct CodeStringWrapper;

struct StagingBuffer {
    bytes: [u8; 2048],
    len: usize,
}

static STAGING_BUFFER: Mutex<CriticalSectionRawMutex, RefCell<StagingBuffer>> =
    Mutex::new(RefCell::new(StagingBuffer {
        bytes: [0u8; 2048],
        len: 0,
    }));

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

fn validate_staged_buffer() -> Result<(), (Option<usize>, &'static str)> {
    STAGING_BUFFER.lock(|cell| {
        let staging = cell.borrow();
        let valid_str = match core::str::from_utf8(&staging.bytes[..staging.len]) {
            Ok(s) => s,
            Err(_) => return Err((None, "Invalid UTF-8 sequence sent in payload body.")),
        };

        for (line_num, line) in (1..).zip(valid_str.lines()) {
            let trimmed = line.trim();
            if !trimmed.is_empty()
                && let Err(ducky_err) = DuckyParser::parse_line(trimmed)
            {
                let diagnostic = ErrorDiagnostic::new(line_num, ducky_err, line);
                diagnostic.log_diagnostic();

                return Err((Some(diagnostic.line_number), "Syntax validation failed."));
            }
        }
        Ok(())
    })
}

pub(super) async fn read<'a>(buffer: &'a mut [u8; 2048]) -> PayloadResponse<'a> {
    let storage = storage();
    let storage_guard = storage.lock().await;

    match storage_guard.read("payload.dd", buffer) {
        Ok(bytes_read) => match core::str::from_utf8(bytes_read) {
            Ok(text) => PayloadResponse { code: text },
            Err(_) => PayloadResponse {
                code: "Error: Invalid UTF-8 data stored on flash.",
            },
        },
        Err(_) => PayloadResponse { code: "" },
    }
}

pub(super) async fn save_staged() -> ValidationResponse {
    if let Err((error_line, _)) = validate_staged_buffer() {
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
        Err(_) => ValidationResponse {
            success: false,
            error_line: None,
            message: Some("Error: Hardware flash partition write execution failed."),
        },
    }
}

pub(super) fn validate_staged() -> ValidationResponse {
    match validate_staged_buffer() {
        Ok(_) => ValidationResponse {
            success: true,
            error_line: None,
            message: Some("Dry run complete. Script layout is completely valid."),
        },
        Err((error_line, message)) => ValidationResponse {
            success: false,
            error_line,
            message: Some(message),
        },
    }
}

pub(super) fn trigger_run() -> RunResponse {
    TRIGGER_RUN.store(true, Ordering::Release);
    RunResponse {
        success: true,
        message: "Payload injection sequence initialized.",
    }
}
