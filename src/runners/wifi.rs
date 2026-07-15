use cyw43::PowerManagementMode::Performance;
use cyw43::{A4, Aligned, Control, Runner as Cyw43Runner, State, aligned_bytes};
use cyw43_pio::PioSpi;
use defmt::{error, info};
use embassy_executor::Spawner;
use embassy_net::Stack;
use embassy_rp::gpio::Output;
use embassy_rp::peripherals::PIO0;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::mutex::Mutex;
use leasehund::DhcpServer;
use static_cell::StaticCell;

use crate::net::{AppRouter, init_wifi_dhcp, init_wifi_network};
use crate::status::{self as status_led, Fault, LED_SIGNAL, Stage};
use crate::storage::StorageManager;

use super::http::portal_http_task;

static FW_BUF: &Aligned<A4, [u8]> = aligned_bytes!("../../firmware/43439A0.bin");
static CLM_BUF: &Aligned<A4, [u8]> = aligned_bytes!("../../firmware/43439A0_clm.bin");
static NVRAM_BUF: &Aligned<A4, [u8]> = aligned_bytes!("../../firmware/nvram_rp2040.bin");

static STATE_STATIC: StaticCell<State> = StaticCell::new();

static CONTROL_MUTEX: StaticCell<Mutex<CriticalSectionRawMutex, Control<'static>>> =
    StaticCell::new();

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
async fn led_task(control_mutex: &'static Mutex<CriticalSectionRawMutex, Control<'static>>) {
    loop {
        let led_on = LED_SIGNAL.wait().await;

        let mut control = control_mutex.lock().await;
        control.gpio_set(0, led_on).await;
    }
}

/// Brings up the CYW43 AP, Wi-Fi DHCP, and portal HTTP worker.
#[embassy_executor::task]
pub async fn wifi_task(
    spi: PioSpi<'static, PIO0, 0>,
    pwr: Output<'static>,
    spawner: Spawner,
    router: &'static AppRouter,
    storage: &'static Mutex<CriticalSectionRawMutex, StorageManager>,
    seed: u64,
) {
    status_led::show(Stage::SetupEntered);
    status_led::show(Stage::SetupApStarting);
    let state = STATE_STATIC.init(cyw43::State::new());
    let (wifi_device, mut control, wifi_runner) =
        cyw43::new(state, pwr, spi, FW_BUF, NVRAM_BUF).await;

    if spawner.spawn(raw_wifi_runner(wifi_runner)).is_err() {
        status_led::error(Fault::SetupApFailed);
        error!("Failed to spawn CYW43 runner.");
        return;
    }

    control.init(CLM_BUF).await;
    control.set_power_management(Performance).await;

    let control_mutex = CONTROL_MUTEX.init(Mutex::new(control));

    if spawner.spawn(led_task(control_mutex)).is_err() {
        error!("Failed to spawn LED task.");
        return;
    };

    let (wifi_net_stack, wifi_net_runner) = {
        let mut control_guard = control_mutex.lock().await;

        init_wifi_network(&mut control_guard, wifi_device, seed).await
    };
    let wifi_dhcp = init_wifi_dhcp();
    status_led::show(Stage::SetupApReady);

    info!("Starting network loops...");

    if spawner.spawn(wifi_net_task(wifi_net_runner)).is_err() {
        status_led::error(Fault::SetupApFailed);
        error!("Failed to spawn Wi-Fi network task.");
        return;
    }
    if spawner
        .spawn(wifi_dhcp_task(wifi_dhcp, wifi_net_stack))
        .is_err()
    {
        status_led::error(Fault::SetupServerFailed);
        error!("Failed to spawn Wi-Fi DHCP task.");
        return;
    }
    if spawner
        .spawn(portal_http_task(wifi_net_stack, router, storage))
        .is_err()
    {
        status_led::error(Fault::SetupServerFailed);
        error!("Failed to spawn Wi-Fi HTTP task.");
        return;
    }
    status_led::show(Stage::SetupServerReady);
}
