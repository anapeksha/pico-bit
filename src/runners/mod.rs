mod debug;
mod http;
mod usb;
mod wifi;

pub use debug::debug_task;
pub use http::ncm_http_task;
pub use usb::{dhcp_task, hid_task, ncm_task, net_task, usb_task};
pub use wifi::wifi_task;

pub(super) const MTU: usize = 1514;
