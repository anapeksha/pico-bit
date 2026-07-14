mod dhcp;
mod http;
mod network;

pub use dhcp::{init_usb_dhcp, init_wifi_dhcp};
pub use http::AppRouter;
pub(crate) use http::delivery::{
    NcmDelivery, NcmDeliveryRoute, STAGED_BINARY_NAME, STAGED_BINARY_PATH,
};
pub(crate) use http::{
    PayloadActionResult, RunSource, active_keyboard_layout, active_keyboard_os,
    active_keyboard_target_codes, compressed_index_html, consume_payload_run_trigger,
    host_hid_active, ncm_active, ncm_url, record_armory_upload_metrics, record_payload_run,
    restore_keyboard_target, runs_snapshot, runtime_metrics, save_payload_code, seeded_this_boot,
    set_host_hid_active, set_ncm_active, trigger_payload_run, update_keyboard_target_codes,
};
pub use network::{init_usb_network, init_wifi_network, wifi_ap_password, wifi_ap_ssid};
