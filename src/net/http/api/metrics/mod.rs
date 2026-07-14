pub mod controller;
mod service;

pub(crate) use service::MetricsResponse;

/// Records the latest Armory upload transfer metrics.
pub(crate) fn record_upload(bytes: usize, duration_ms: u64) {
    service::record_upload(bytes, duration_ms);
}

/// Returns a bounded snapshot of current runtime and storage metrics.
pub(crate) async fn snapshot() -> MetricsResponse {
    service::snapshot().await
}
