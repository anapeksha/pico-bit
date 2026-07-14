use core::sync::atomic::{AtomicU32, Ordering};
use serde::Serialize;

use crate::net::http::delivery::STAGED_BINARY_PATH;
use crate::storage::{GLOBAL_STORAGE, SharedStorage};

use super::super::runs;

static UPLOAD_BYTES: AtomicU32 = AtomicU32::new(0);
static UPLOAD_DURATION_MS: AtomicU32 = AtomicU32::new(0);

/// Small machine-oriented runtime metrics snapshot.
#[derive(Serialize)]
pub(crate) struct MetricsResponse {
    littlefs_free_bytes: usize,
    staged_binary_bytes: usize,
    last_run_code: &'static str,
    upload_bytes: u32,
    upload_duration_ms: u32,
}

fn storage() -> Option<&'static SharedStorage> {
    let ptr = GLOBAL_STORAGE.load(Ordering::Acquire);
    if ptr.is_null() {
        None
    } else {
        Some(unsafe { &*ptr })
    }
}

pub(super) fn record_upload(bytes: usize, duration_ms: u64) {
    UPLOAD_BYTES.store(bytes.min(u32::MAX as usize) as u32, Ordering::Release);
    UPLOAD_DURATION_MS.store(duration_ms.min(u32::MAX as u64) as u32, Ordering::Release);
}

pub(crate) async fn snapshot() -> MetricsResponse {
    let (littlefs_free_bytes, staged_binary_bytes) = match storage() {
        Some(storage) => {
            let guard = storage.lock().await;
            (
                guard.available_space().unwrap_or(0),
                guard.file_size(STAGED_BINARY_PATH).unwrap_or(0),
            )
        }
        None => (0, 0),
    };

    let last_run_code = runs::snapshot()
        .entries()
        .first()
        .map(|entry| if entry.ok() { "ok" } else { "error" })
        .unwrap_or("none");

    MetricsResponse {
        littlefs_free_bytes,
        staged_binary_bytes,
        last_run_code,
        upload_bytes: UPLOAD_BYTES.load(Ordering::Acquire),
        upload_duration_ms: UPLOAD_DURATION_MS.load(Ordering::Acquire),
    }
}

impl MetricsResponse {
    pub(crate) fn littlefs_free_bytes(&self) -> usize {
        self.littlefs_free_bytes
    }

    pub(crate) fn staged_binary_bytes(&self) -> usize {
        self.staged_binary_bytes
    }

    pub(crate) fn last_run_code(&self) -> &'static str {
        self.last_run_code
    }

    pub(crate) fn upload_bytes(&self) -> u32 {
        self.upload_bytes
    }

    pub(crate) fn upload_duration_ms(&self) -> u32 {
        self.upload_duration_ms
    }
}
