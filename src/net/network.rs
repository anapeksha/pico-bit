use cyw43::Control;
use embassy_net::driver::Driver;
use embassy_net::{Config, Ipv4Address, Ipv4Cidr, Runner, Stack, StackResources, StaticConfigV4};
use heapless::Vec;
use static_cell::StaticCell;

static USB_NET_STACK: StaticCell<Stack> = StaticCell::new();
static WIFI_NET_STACK: StaticCell<Stack> = StaticCell::new();
static USB_NET_RESOURCES: StaticCell<StackResources<8>> = StaticCell::new();
static WIFI_NET_RESOURCES: StaticCell<StackResources<8>> = StaticCell::new();

pub fn wifi_ap_ssid() -> &'static str {
    option_env!("AP_SSID").unwrap_or("PicoBit")
}

pub fn wifi_ap_password() -> &'static str {
    option_env!("AP_PASSWORD").unwrap_or("PicoBit24Net")
}

pub fn init_usb_network<D: Driver + 'static>(
    device: D,
    seed: u64,
) -> (&'static Stack<'static>, Runner<'static, D>) {
    let config = Config::ipv4_static(StaticConfigV4 {
        address: Ipv4Cidr::new(Ipv4Address::new(192, 168, 137, 1), 24),
        dns_servers: Vec::new(),
        gateway: Some(Ipv4Address::new(0, 0, 0, 0)),
    });

    let (stack, runner) = embassy_net::new(
        device,
        config,
        USB_NET_RESOURCES.init(StackResources::<8>::new()),
        seed,
    );

    (USB_NET_STACK.init(stack), runner)
}

pub async fn init_wifi_network<D: Driver + 'static>(
    mut control: Control<'static>,
    device: D,
    seed: u64,
) -> (&'static Stack<'static>, Runner<'static, D>) {
    control
        .start_ap_wpa2(wifi_ap_ssid(), wifi_ap_password(), 6)
        .await;

    let config = Config::ipv4_static(StaticConfigV4 {
        address: Ipv4Cidr::new(Ipv4Address::new(192, 168, 4, 1), 24),
        dns_servers: Vec::new(),
        gateway: Some(Ipv4Address::new(0, 0, 0, 0)),
    });

    let (stack, runner) = embassy_net::new(
        device,
        config,
        WIFI_NET_RESOURCES.init(StackResources::<8>::new()),
        seed,
    );

    (WIFI_NET_STACK.init(stack), runner)
}
