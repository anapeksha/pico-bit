use crate::net::{http::api::keyboard, wifi_ap_password, wifi_ap_ssid};
use serde::Serialize;

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

pub(super) fn snapshot() -> BootstrapResponse {
    let (keyboard_os, keyboard_layout) = keyboard::service::active_target_codes();

    BootstrapResponse {
        ap_password: wifi_ap_password(),
        ap_ssid: wifi_ap_ssid(),
        host_hid_active: true,
        keyboard_layout,
        keyboard_os,
        ncm_active: true,
        ncm_url: "http://192.168.7.1",
        seeded: false,
    }
}
