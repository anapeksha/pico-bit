// src/net/http/api/payload.rs

use crate::ducky::{DuckyParser, ErrorDiagnostic};
use crate::storage::{GLOBAL_STORAGE, SharedStorage};
use core::cell::RefCell;
use core::sync::atomic::Ordering;
use embassy_sync::blocking_mutex::Mutex;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use picoserve::Router;
use picoserve::extract::JsonWithUnescapeBufferSize; // FIX 1: Import the unescape-capable extractor
use picoserve::response::{IntoResponse, Json};
use picoserve::routing::{PathRouter, get};
use serde::{Deserialize, Deserializer, Serialize};

#[derive(Serialize)]
struct PayloadResponse<'a> {
    code: &'a str,
}

// Stays a Zero-Sized Type (ZST) to keep your handler stack overhead at 0 bytes!
struct SavePayloadRequest;

// FIX 2: Create a wrapper struct to handle the custom string deserialization step
struct CodeStringWrapper;

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

            // This handles transient unescaped string slices coming from the scratch buffer
            fn visit_str<E>(self, v: &str) -> Result<Self::Value, E>
            where
                E: serde::de::Error,
            {
                if v.len() > 2048 {
                    return Err(E::custom("Payload content exceeds 2048 bytes"));
                }

                // Safely stream the unescaped characters directly into global memory
                STAGING_BUFFER.lock(|cell| {
                    let mut staging = cell.borrow_mut();
                    staging.bytes[..v.len()].copy_from_slice(v.as_bytes());
                    staging.len = v.len();
                });

                Ok(CodeStringWrapper)
            }

            // Fallback for strings that do not require unescaping
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

// FIX 3: Manually implement Deserialize for the request to handle object map keys safely
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
                        // Route the value processing directly through our custom unescape handler
                        let _: CodeStringWrapper = map.next_value()?;
                        found_code = true;
                    } else {
                        // Dynamically ignore any other parameters safely
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

#[derive(Serialize)]
struct ValidationResponse {
    success: bool,
    error_line: Option<usize>,
    message: Option<&'static str>,
}

struct StagingBuffer {
    bytes: [u8; 2048],
    len: usize,
}

static STAGING_BUFFER: Mutex<CriticalSectionRawMutex, RefCell<StagingBuffer>> =
    Mutex::new(RefCell::new(StagingBuffer {
        bytes: [0u8; 2048],
        len: 0,
    }));

fn get_storage() -> &'static SharedStorage {
    let ptr = GLOBAL_STORAGE.load(Ordering::Acquire);
    if ptr.is_null() {
        panic!("GLOBAL_STORAGE accessed before initialization!");
    }
    unsafe { &*ptr }
}

async fn get_payload() -> impl IntoResponse {
    static mut BUFFER: [u8; 2048] = [0u8; 2048];

    let storage = get_storage();
    let storage_guard = storage.lock().await;
    let buffer_ref: &'static mut [u8; 2048] = unsafe { &mut *core::ptr::addr_of_mut!(BUFFER) };

    match storage_guard.read("payload.txt", buffer_ref) {
        Ok(bytes_read) => {
            if let Ok(text) = core::str::from_utf8(bytes_read) {
                Json(PayloadResponse { code: text })
            } else {
                Json(PayloadResponse {
                    code: "Error: Invalid UTF-8 data stored on flash.",
                })
            }
        }
        Err(_) => Json(PayloadResponse { code: "" }),
    }
}

// FIX 4: Update the signature to enforce the unescape extractor block
async fn save_payload(
    JsonWithUnescapeBufferSize(_): JsonWithUnescapeBufferSize<SavePayloadRequest, 2048>,
) -> impl IntoResponse {
    let mut validation_error = None;

    STAGING_BUFFER.lock(|cell| {
        let staging = cell.borrow();
        let valid_str = match core::str::from_utf8(&staging.bytes[..staging.len]) {
            Ok(s) => s,
            Err(_) => {
                validation_error = Some((None, "Invalid UTF-8 sequence sent in payload body."));
                return;
            }
        };

        let mut line_num = 1;
        for line in valid_str.lines() {
            let trimmed = line.trim();
            if !trimmed.is_empty() {
                if let Err(ducky_err) = DuckyParser::parse_line(trimmed) {
                    let diagnostic = ErrorDiagnostic::new(line_num, ducky_err, line);
                    diagnostic.log_diagnostic();

                    validation_error = Some((
                        Some(diagnostic.line_number),
                        "Syntax validation failed. Flash update aborted.",
                    ));
                    return;
                }
            }
            line_num += 1;
        }
    });

    if let Some((error_line, message)) = validation_error {
        return Json(ValidationResponse {
            success: false,
            error_line,
            message: Some(message),
        });
    }

    let storage = get_storage();
    let storage_guard = storage.lock().await;

    let write_result = STAGING_BUFFER.lock(|cell| {
        let mut staging = cell.borrow_mut();
        let len = staging.len;
        let target_slice = &mut staging.bytes[..len];

        storage_guard.write("payload.txt", target_slice)
    });

    match write_result {
        Ok(_) => Json(ValidationResponse {
            success: true,
            error_line: None,
            message: Some("Payload updated successfully."),
        }),
        Err(_) => Json(ValidationResponse {
            success: false,
            error_line: None,
            message: Some("Error: Hardware flash partition write execution failed."),
        }),
    }
}

pub fn build<R: PathRouter>(router: Router<R, ()>) -> Router<impl PathRouter, ()> {
    router.route("/api/payload", get(get_payload).post(save_payload))
}
