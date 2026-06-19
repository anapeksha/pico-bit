use cyw43::PowerManagementMode::Performance;
use cyw43::{A4, Aligned, Runner as Cyw43Runner, State, aligned_bytes};
use cyw43_pio::PioSpi;
use embassy_net::tcp::TcpSocket;
use embassy_net::{Runner as NetRunner, Stack};
use embassy_rp::gpio::Output;
use embassy_rp::peripherals::{PIO0, USB};
use embassy_rp::usb::Driver;
use embassy_usb::UsbDevice;
use embassy_usb::class::cdc_ncm::embassy_net::{Device, Runner as NcmRunner};
use embassy_usb::class::hid::HidWriter;
use leasehund::DhcpServer;
use picoserve::{Config, DisconnectionInfo, Server, Timeouts};

use defmt::{error, info, warn};
use embassy_executor::Spawner;
use static_cell::StaticCell;

use crate::net::{AppRouter, init_wifi_dhcp, init_wifi_network};

const MTU: usize = 1514;

static FW_BUF: &Aligned<A4, [u8]> = aligned_bytes!("../firmware/43439A0.bin");
static CLM_BUF: &Aligned<A4, [u8]> = aligned_bytes!("../firmware/43439A0_clm.bin");
static NVRAM_BUF: &Aligned<A4, [u8]> = aligned_bytes!("../firmware/nvram_rp2040.bin");

static STATE_STATIC: StaticCell<State> = StaticCell::new();
static ROUTER: StaticCell<AppRouter> = StaticCell::new();

#[embassy_executor::task]
pub async fn usb_task(mut usb: UsbDevice<'static, Driver<'static, USB>>) {
    usb.run().await;
}

#[embassy_executor::task]
pub async fn ncm_task(runner: NcmRunner<'static, Driver<'static, USB>, MTU>) {
    runner.run().await;
}

#[embassy_executor::task]
pub async fn net_task(mut runner: NetRunner<'static, Device<'static, MTU>>) {
    runner.run().await;
}

#[embassy_executor::task]
pub async fn hid_task(mut hid: HidWriter<'static, Driver<'static, USB>, 8>) {
    hid.ready().await;
}

#[embassy_executor::task]
pub async fn dhcp_task(mut server: DhcpServer<32, 4>, stack: &'static Stack<'static>) {
    server.run(*stack).await;
}

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

#[embassy_executor::task(pool_size = 3)]
async fn server_task(stack: &'static Stack<'static>, task_id: usize, router: &'static AppRouter) {
    let config = Config::new(Timeouts::default());

    let router = router.build();

    let mut rx_buffer = [0u8; 512];
    let mut tx_buffer = [0u8; 1024];
    let mut picoserve_buffer = [0u8; 512];

    info!("HTTP worker {} initialised...", task_id);

    loop {
        let mut socket = TcpSocket::new(*stack, &mut rx_buffer, &mut tx_buffer);

        if let Err(e) = socket.accept(80).await {
            warn!("[Worker {}] Accept failed: {:?}", task_id, e);
            continue;
        }

        let remote_address = socket.remote_endpoint();
        info!("[Worker {}] Connected to {}", task_id, remote_address);

        match Server::new(&router, &config, &mut picoserve_buffer)
            .serve(socket)
            .await
        {
            Ok(DisconnectionInfo {
                handled_requests_count,
                ..
            }) => {
                info!(
                    "Successfully handled {} requests before closing.",
                    handled_requests_count
                );
            }
            Err(err) => {
                error!("Picoserve engine processing error: {:?}", err);
            }
        }
    }
}

#[embassy_executor::task]
pub async fn wifi_task(spi: PioSpi<'static, PIO0, 0>, pwr: Output<'static>, spawner: Spawner) {
    let state = STATE_STATIC.init(cyw43::State::new());
    let (wifi_device, mut control, wifi_runner) =
        cyw43::new(state, pwr, spi, &FW_BUF, &NVRAM_BUF).await;

    spawner.spawn(raw_wifi_runner(wifi_runner)).unwrap();

    let router = ROUTER.init(AppRouter);

    // 4. Load the configuration blocks
    control.init(&CLM_BUF).await;
    control.set_power_management(Performance).await;

    // 5. Initialize the access point stack
    let (wifi_net_stack, wifi_net_runner) = init_wifi_network(control, wifi_device, 5678).await;
    let wifi_dhcp = init_wifi_dhcp();

    info!("Starting network loops...");

    // 6. Spawn the distinct runtime loops into their own execution slots
    spawner.spawn(wifi_net_task(wifi_net_runner)).unwrap();
    spawner
        .spawn(wifi_dhcp_task(wifi_dhcp, wifi_net_stack))
        .unwrap();
    for id in 0..3 {
        spawner
            .spawn(server_task(wifi_net_stack, id, router))
            .unwrap();
    }
}
