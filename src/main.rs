#![no_std]
#![no_main]

mod net;
mod pio;
mod runners;
mod usb;

use defmt::info;
use embassy_executor::Spawner;
use embassy_rp::block::ImageDef;
use embassy_rp::dma::InterruptHandler as DmaInterruptHandler;
use embassy_rp::peripherals::{DMA_CH0, PIO0, USB};
use embassy_rp::pio::InterruptHandler as PioInterruptHandler;
use embassy_rp::usb::InterruptHandler as UsbInterruptHandler;
use embassy_rp::{self as hal, bind_interrupts};

// Panic Handler
use panic_probe as _;
// Defmt Logging
use defmt_rtt as _;
use net::{init_usb_dhcp, init_usb_network};
use pio::PioManager;
use runners::{dhcp_task, hid_task, ncm_task, net_task, usb_task, wifi_task};
use usb::UsbManager;

bind_interrupts!(struct Irqs {
    USBCTRL_IRQ => UsbInterruptHandler<USB>;
    PIO0_IRQ_0 => PioInterruptHandler<PIO0>;
    DMA_IRQ_0 => DmaInterruptHandler<DMA_CH0>;
});

/// Tell the Boot ROM about our application
#[unsafe(link_section = ".start_block")]
#[used]
pub static IMAGE_DEF: ImageDef = hal::block::ImageDef::secure_exe();

#[embassy_executor::main]
async fn main(spawner: Spawner) {
    let p = embassy_rp::init(Default::default());

    // USB Driver
    let usb_driver = embassy_rp::usb::Driver::new(p.USB, Irqs);
    let usb_manager = UsbManager::new(usb_driver);
    let (usb_net_stack, usb_net_runner) = init_usb_network(usb_manager.net_device, 1234);
    let usb_dhcp_server = init_usb_dhcp();

    // PIO Driver
    let pio_driver = embassy_rp::pio::Pio::new(p.PIO0, Irqs);
    let pio_manager = PioManager::new(
        pio_driver, p.PIN_23, p.PIN_24, p.PIN_25, p.PIN_29, p.DMA_CH0, Irqs,
    );

    info!("Spawning services...");

    spawner
        .spawn(wifi_task(pio_manager.spi, pio_manager.pwr, spawner))
        .unwrap();
    spawner.spawn(usb_task(usb_manager.device)).unwrap();
    spawner.spawn(ncm_task(usb_manager.net_runner)).unwrap();
    spawner.spawn(net_task(usb_net_runner)).unwrap();
    spawner.spawn(hid_task(usb_manager.hid)).unwrap();
    spawner
        .spawn(dhcp_task(usb_dhcp_server, usb_net_stack))
        .unwrap();
}
