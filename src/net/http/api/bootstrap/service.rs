use crate::net::{
    http::api::{keyboard, runs},
    wifi_ap_password, wifi_ap_ssid,
};
use core::sync::atomic::{AtomicBool, Ordering};
use serde::Serialize;

const NCM_URL: &str = "http://192.168.7.1";

static HOST_HID_ACTIVE: AtomicBool = AtomicBool::new(false);
static NCM_ACTIVE: AtomicBool = AtomicBool::new(false);

/// Fixed, small startup snapshot returned by `/api/bootstrap`.
#[derive(Serialize)]
pub(super) struct BootstrapResponse {
    ap_password: &'static str,
    ap_ssid: &'static str,
    host_hid_active: bool,
    keyboard_layout: &'static str,
    keyboard_os: &'static str,
    ncm_active: bool,
    ncm_url: &'static str,
    seeded: bool,
}

/// Builds the current bootstrap snapshot without reading LittleFS.
pub(super) fn snapshot() -> BootstrapResponse {
    let (keyboard_os, keyboard_layout) = keyboard::service::active_target_codes();

    BootstrapResponse {
        ap_password: wifi_ap_password(),
        ap_ssid: wifi_ap_ssid(),
        host_hid_active: host_hid_active(),
        keyboard_layout,
        keyboard_os,
        ncm_active: ncm_active(),
        ncm_url: ncm_url(),
        seeded: seeded_this_boot(),
    }
}

/// Updates Host HID readiness for bootstrap consumers.
pub(crate) fn set_host_hid_active(active: bool) {
    HOST_HID_ACTIVE.store(active, Ordering::Release);
}

/// Returns current Host HID readiness.
pub(crate) fn host_hid_active() -> bool {
    HOST_HID_ACTIVE.load(Ordering::Acquire)
}

/// Updates USB NCM readiness for bootstrap consumers.
pub(crate) fn set_ncm_active(active: bool) {
    NCM_ACTIVE.store(active, Ordering::Release);
}

/// Returns current USB NCM readiness.
pub(crate) fn ncm_active() -> bool {
    NCM_ACTIVE.load(Ordering::Acquire)
}

/// Returns the NCM base URL advertised to the dashboard.
pub(crate) fn ncm_url() -> &'static str {
    NCM_URL
}

/// Returns whether the boot payload has been recorded.
pub(crate) fn seeded_this_boot() -> bool {
    runs::snapshot().seeded()
}
