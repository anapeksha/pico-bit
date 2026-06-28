mod dhcp;
mod http;
mod network;

pub use dhcp::{init_usb_dhcp, init_wifi_dhcp};
pub use http::AppRouter;
pub(crate) use http::{
    active_keyboard_layout, active_keyboard_target_codes, compressed_index_html,
    update_keyboard_target_codes,
};
pub use network::{init_usb_network, init_wifi_network};
