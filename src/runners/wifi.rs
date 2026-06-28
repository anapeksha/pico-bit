use cyw43::PowerManagementMode::Performance;
use cyw43::{A4, Aligned, Runner as Cyw43Runner, State, aligned_bytes};
use cyw43_pio::PioSpi;
use defmt::info;
use embassy_executor::Spawner;
use embassy_net::Stack;
use embassy_rp::gpio::Output;
use embassy_rp::peripherals::PIO0;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::mutex::Mutex;
use leasehund::DhcpServer;
use static_cell::StaticCell;

use crate::net::{AppRouter, init_wifi_dhcp, init_wifi_network};
use crate::storage::StorageManager;

use super::http::server_task;

static FW_BUF: &Aligned<A4, [u8]> = aligned_bytes!("../../firmware/43439A0.bin");
static CLM_BUF: &Aligned<A4, [u8]> = aligned_bytes!("../../firmware/43439A0_clm.bin");
static NVRAM_BUF: &Aligned<A4, [u8]> = aligned_bytes!("../../firmware/nvram_rp2040.bin");

static STATE_STATIC: StaticCell<State> = StaticCell::new();
static ROUTER: StaticCell<AppRouter> = StaticCell::new();

#[embassy_executor::task]
async fn raw_wifi_runner(
    runner: Cyw43Runner<'static, cyw43::SpiBus<Output<'static>, PioSpi<'static, PIO0, 0>>>,
) {
    runner.run().await;
}

#[embassy_executor::task]
async fn wifi_net_task(mut runner: embassy_net::Runner<'static, cyw43::NetDriver<'static>>) {
    runner.run().await;
}

#[embassy_executor::task]
async fn wifi_dhcp_task(mut server: DhcpServer<32, 4>, stack: &'static Stack<'static>) {
    server.run(*stack).await;
}

#[embassy_executor::task]
pub async fn wifi_task(
    spi: PioSpi<'static, PIO0, 0>,
    pwr: Output<'static>,
    spawner: Spawner,
    storage: &'static Mutex<CriticalSectionRawMutex, StorageManager>,
) {
    let state = STATE_STATIC.init(cyw43::State::new());
    let (wifi_device, mut control, wifi_runner) =
        cyw43::new(state, pwr, spi, FW_BUF, NVRAM_BUF).await;

    spawner.spawn(raw_wifi_runner(wifi_runner)).unwrap();

    let router = ROUTER.init(AppRouter);

    control.init(CLM_BUF).await;
    control.set_power_management(Performance).await;

    let (wifi_net_stack, wifi_net_runner) = init_wifi_network(control, wifi_device, 5678).await;
    let wifi_dhcp = init_wifi_dhcp();

    info!("Starting network loops...");

    spawner.spawn(wifi_net_task(wifi_net_runner)).unwrap();
    spawner
        .spawn(wifi_dhcp_task(wifi_dhcp, wifi_net_stack))
        .unwrap();
    spawner
        .spawn(server_task(wifi_net_stack, router, storage))
        .unwrap();
}
