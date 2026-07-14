use crate::ducky::{KeyboardLayout, KeyboardOs};
use crate::status::{self as status_led, Stage};
use crate::storage::{GLOBAL_STORAGE, SharedStorage};
use core::sync::atomic::{AtomicU8, Ordering};
use picoserve::response::{IntoResponse, Json, StatusCode};
use serde::Serialize;
use serde::{Deserialize, Deserializer};

/// Response returned after keyboard target mutations.
#[derive(Serialize)]
pub(crate) struct KeyboardResponse {
    pub(crate) keyboard_layout: &'static str,
    pub(crate) keyboard_os: &'static str,
    pub(crate) message: &'static str,
    pub(crate) notice: &'static str,
}

impl KeyboardResponse {
    /// Whether the update request failed validation.
    pub(super) fn is_error(&self) -> bool {
        self.notice == "error"
    }
}

pub(super) async fn update_response(request: KeyboardTargetRequest) -> impl IntoResponse {
    let response = update_target(request).await;
    let status = if response.is_error() {
        StatusCode::BAD_REQUEST
    } else {
        StatusCode::OK
    };

    Json(response).into_response().with_status_code(status)
}

/// Deserialized keyboard target update request.
pub(super) struct KeyboardTargetRequest {
    layout: Option<KeyboardLayout>,
    os: Option<KeyboardOs>,
    valid: bool,
}

static ACTIVE_LAYOUT: AtomicU8 = AtomicU8::new(KeyboardLayout::Us as u8);
static ACTIVE_OS: AtomicU8 = AtomicU8::new(KeyboardOs::Windows as u8);

const KEYBOARD_TARGET_PATH: &str = "/keyboard.cfg";
const KEYBOARD_TARGET_BUFFER_SIZE: usize = 16;

impl<'de> Deserialize<'de> for KeyboardTargetRequest {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        struct RequestVisitor;

        impl<'de> serde::de::Visitor<'de> for RequestVisitor {
            type Value = KeyboardTargetRequest;

            fn expecting(&self, formatter: &mut core::fmt::Formatter) -> core::fmt::Result {
                formatter.write_str("a keyboard target object")
            }

            fn visit_map<A>(self, mut map: A) -> Result<Self::Value, A::Error>
            where
                A: serde::de::MapAccess<'de>,
            {
                let mut layout = None;
                let mut os = None;
                let mut valid = true;

                while let Some(key) = map.next_key::<&str>()? {
                    match key {
                        "layout" => {
                            let code = map.next_value::<&str>()?;
                            layout = layout_from_code(code);
                            valid &= layout.is_some();
                        }
                        "os" => {
                            let code = map.next_value::<&str>()?;
                            os = os_from_code(code);
                            valid &= os.is_some();
                        }
                        _ => {
                            let _: serde::de::IgnoredAny = map.next_value()?;
                        }
                    }
                }

                Ok(KeyboardTargetRequest { layout, os, valid })
            }
        }

        deserializer.deserialize_map(RequestVisitor)
    }
}

fn layout_from_code(code: &str) -> Option<KeyboardLayout> {
    match code {
        "US" => Some(KeyboardLayout::Us),
        "UK" => Some(KeyboardLayout::Uk),
        "DE" => Some(KeyboardLayout::De),
        "FR" => Some(KeyboardLayout::Fr),
        _ => None,
    }
}

fn layout_code(layout: KeyboardLayout) -> &'static str {
    match layout {
        KeyboardLayout::Us => "US",
        KeyboardLayout::Uk => "UK",
        KeyboardLayout::De => "DE",
        KeyboardLayout::Fr => "FR",
    }
}

fn os_from_code(code: &str) -> Option<KeyboardOs> {
    match code {
        "WIN" => Some(KeyboardOs::Windows),
        "MAC" => Some(KeyboardOs::MacOs),
        "LINUX" => Some(KeyboardOs::Linux),
        _ => None,
    }
}

fn os_code(os: KeyboardOs) -> &'static str {
    match os {
        KeyboardOs::Windows => "WIN",
        KeyboardOs::MacOs => "MAC",
        KeyboardOs::Linux => "LINUX",
    }
}

fn decode_layout(value: u8) -> KeyboardLayout {
    match value {
        value if value == KeyboardLayout::Uk as u8 => KeyboardLayout::Uk,
        value if value == KeyboardLayout::De as u8 => KeyboardLayout::De,
        value if value == KeyboardLayout::Fr as u8 => KeyboardLayout::Fr,
        _ => KeyboardLayout::Us,
    }
}

fn decode_os(value: u8) -> KeyboardOs {
    match value {
        value if value == KeyboardOs::MacOs as u8 => KeyboardOs::MacOs,
        value if value == KeyboardOs::Linux as u8 => KeyboardOs::Linux,
        _ => KeyboardOs::Windows,
    }
}

/// Active layout used for printable character mapping.
pub(crate) fn active_layout() -> KeyboardLayout {
    decode_layout(ACTIVE_LAYOUT.load(Ordering::Acquire))
}

/// Active OS target used for key alias parsing.
pub(crate) fn active_os() -> KeyboardOs {
    decode_os(ACTIVE_OS.load(Ordering::Acquire))
}

fn set_target(os: KeyboardOs, layout: KeyboardLayout) {
    ACTIVE_OS.store(os as u8, Ordering::Release);
    ACTIVE_LAYOUT.store(layout as u8, Ordering::Release);
}

fn storage() -> Option<&'static SharedStorage> {
    let ptr = GLOBAL_STORAGE.load(Ordering::Acquire);
    if ptr.is_null() {
        None
    } else {
        Some(unsafe { &*ptr })
    }
}

async fn persist_target(os: KeyboardOs, layout: KeyboardLayout) -> bool {
    let Some(storage) = storage() else {
        return false;
    };

    let os = os_code(os).as_bytes();
    let layout = layout_code(layout).as_bytes();
    let mut config = [0u8; KEYBOARD_TARGET_BUFFER_SIZE];
    let len = os.len() + 1 + layout.len();

    config[..os.len()].copy_from_slice(os);
    config[os.len()] = b'\n';
    config[os.len() + 1..len].copy_from_slice(layout);

    storage
        .lock()
        .await
        .write(KEYBOARD_TARGET_PATH, &config[..len])
        .is_ok()
}

fn response(message: &'static str, notice: &'static str) -> KeyboardResponse {
    let layout = active_layout();
    let os = active_os();

    KeyboardResponse {
        keyboard_layout: layout_code(layout),
        keyboard_os: os_code(os),
        message,
        notice,
    }
}

/// Active target represented as compact `(os, layout)` API codes.
pub(crate) fn active_target_codes() -> (&'static str, &'static str) {
    (os_code(active_os()), layout_code(active_layout()))
}

/// Updates the active target from compact API codes.
pub(crate) async fn update_target_codes(os_code_value: &str, layout_code_value: &str) -> bool {
    let Some(os) = os_from_code(os_code_value) else {
        return false;
    };
    let Some(layout) = layout_from_code(layout_code_value) else {
        return false;
    };

    let previous_os = active_os();
    let previous_layout = active_layout();
    set_target(os, layout);

    if persist_target(os, layout).await {
        status_led::show(Stage::KeyboardLayoutChanged);
        true
    } else {
        set_target(previous_os, previous_layout);
        false
    }
}

pub(super) async fn update_target(request: KeyboardTargetRequest) -> KeyboardResponse {
    let current_layout = active_layout();
    let current_os = active_os();

    if !request.valid {
        return response("Unsupported keyboard layout.", "error");
    }

    let layout = request.layout.unwrap_or(current_layout);
    let os = request.os.unwrap_or(current_os);

    if update_target_codes(os_code(os), layout_code(layout)).await {
        response("Keyboard target updated.", "success")
    } else {
        response("Keyboard target could not be saved.", "error")
    }
}

/// Restores the persisted keyboard target, using Windows/US when unavailable.
pub(crate) async fn restore_target() {
    let default_os = KeyboardOs::Windows;
    let default_layout = KeyboardLayout::Us;
    let Some(storage) = storage() else {
        set_target(default_os, default_layout);
        return;
    };

    let mut buffer = [0u8; KEYBOARD_TARGET_BUFFER_SIZE];
    let guard = storage.lock().await;
    let restored = guard
        .read(KEYBOARD_TARGET_PATH, &mut buffer)
        .ok()
        .and_then(|bytes| core::str::from_utf8(bytes).ok())
        .and_then(|config| config.split_once('\n'))
        .and_then(|(os, layout)| Some((os_from_code(os)?, layout_from_code(layout)?)));
    drop(guard);

    match restored {
        Some((os, layout)) => set_target(os, layout),
        None => {
            set_target(default_os, default_layout);
            let _ = persist_target(default_os, default_layout).await;
        }
    }
}
