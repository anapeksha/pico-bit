mod api;
mod assets;

use picoserve::Router;
use picoserve::routing::PathRouter;

use crate::ducky::{KeyboardLayout, KeyboardOs};
pub(crate) use api::payload::PayloadActionResult;
pub(crate) use api::runs::RunSource;
use api::runs::RunsSnapshot;

/// Builds the picoserve router used by both Wi-Fi and NCM workers.
pub struct AppRouter;

/// Active keyboard layout for printable `STRING` execution.
pub(crate) fn active_keyboard_layout() -> KeyboardLayout {
    api::keyboard::service::active_layout()
}

/// Active host OS target for key-chord alias parsing.
pub(crate) fn active_keyboard_os() -> KeyboardOs {
    api::keyboard::service::active_os()
}

/// Active keyboard target as compact API codes.
pub(crate) fn active_keyboard_target_codes() -> (&'static str, &'static str) {
    api::keyboard::service::active_target_codes()
}

/// Updates the active keyboard target from compact API codes.
pub(crate) fn update_keyboard_target_codes(os: &str, layout: &str) -> bool {
    api::keyboard::service::update_target_codes(os, layout)
}

/// Atomically consumes a pending manual payload run request.
pub(crate) fn consume_payload_run_trigger() -> bool {
    api::payload::consume_run_trigger()
}

/// Validates and saves staged editor code into `payload.dd`.
pub(crate) async fn save_payload_code(code: &str) -> PayloadActionResult {
    api::payload::save_code(code).await
}

/// Validates the saved payload and arms a manual run.
pub(crate) async fn trigger_payload_run() -> PayloadActionResult {
    api::payload::trigger_run().await
}

/// Updates Host HID readiness exposed by bootstrap.
pub(crate) fn set_host_hid_active(active: bool) {
    api::bootstrap::set_host_hid_active(active);
}

/// Returns Host HID readiness.
pub(crate) fn host_hid_active() -> bool {
    api::bootstrap::host_hid_active()
}

/// Updates NCM readiness exposed by bootstrap.
pub(crate) fn set_ncm_active(active: bool) {
    api::bootstrap::set_ncm_active(active);
}

/// Returns NCM readiness.
pub(crate) fn ncm_active() -> bool {
    api::bootstrap::ncm_active()
}

/// Returns the NCM base URL advertised to the frontend.
pub(crate) fn ncm_url() -> &'static str {
    api::bootstrap::ncm_url()
}

/// Returns whether a non-empty payload has run this boot.
pub(crate) fn seeded_this_boot() -> bool {
    api::bootstrap::seeded_this_boot()
}

/// Records one payload execution result in the bounded run history.
pub(crate) fn record_payload_run(source: RunSource, ok: bool, preview: &str) {
    api::runs::record_run(source, ok, preview);
}

/// Returns a copy of the bounded run history snapshot.
pub(crate) fn runs_snapshot() -> RunsSnapshot {
    api::runs::snapshot()
}

/// Returns the embedded gzipped dashboard artifact.
pub(crate) fn compressed_index_html() -> &'static [u8] {
    assets::compressed_index_html()
}

impl AppRouter {
    /// Builds all API and static dashboard routes.
    pub fn build(&self) -> Router<impl PathRouter, ()> {
        let router = Router::<_, ()>::new();

        let router = api::bootstrap::controller::build(router);
        let router = api::keyboard::controller::build(router);
        let router = api::armory::controller::build(router);
        let router = api::payload::controller::build(router);
        let router = api::runs::controller::build(router);
        assets::build(router)
    }
}
