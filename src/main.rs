#![no_std]
#![no_main]
#![recursion_limit = "256"]

mod debug;
mod ducky;
mod net;
mod pio;
mod runners;
mod status;
mod storage;
mod usb;

use core::sync::atomic::Ordering;
use defmt::info;
use embassy_executor::Spawner;
use embassy_rp::binary_info::{
    EntryAddr, rp_cargo_version, rp_program_build_attribute, rp_program_description,
    rp_program_name,
};
use embassy_rp::bind_interrupts;
use embassy_rp::block::ImageDef;
use embassy_rp::clocks::RoscRng;
use embassy_rp::dma::InterruptHandler as DmaInterruptHandler;
use embassy_rp::flash::Flash;
use embassy_rp::peripherals::{DMA_CH0, DMA_CH1, DMA_CH2, PIO0, USB};
use embassy_rp::pio::InterruptHandler as PioInterruptHandler;
use embassy_rp::spi::{Config, Spi};
use embassy_rp::usb::InterruptHandler as UsbInterruptHandler;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::mutex::Mutex;
use littlefs2::fs::Allocation;

// Panic Handler
use panic_probe as _;
// Defmt Logging
use defmt_rtt as _;

use net::{
    AppRouter, active_keyboard_target_codes, init_usb_dhcp, init_usb_network,
    restore_keyboard_target,
};
use pio::PioManager;
use runners::{
    debug_task, dhcp_task, hid_task, ncm_http_task, ncm_task, net_task, usb_task, wifi_task,
};
use static_cell::StaticCell;
use storage::{FlashDriver, StorageManager};
use usb::UsbManager;

bind_interrupts!(struct Irqs {
    USBCTRL_IRQ => UsbInterruptHandler<USB>;
    PIO0_IRQ_0 => PioInterruptHandler<PIO0>;
    DMA_IRQ_0 => DmaInterruptHandler<DMA_CH0>, DmaInterruptHandler<DMA_CH1>, DmaInterruptHandler<DMA_CH2>;
});

/// Tell the Boot ROM about our application
#[unsafe(link_section = ".start_block")]
#[used]
pub static IMAGE_DEF: ImageDef = embassy_rp::block::ImageDef::secure_exe();

static LFS_ALLOCATION: StaticCell<Allocation<FlashDriver>> = StaticCell::new();
static LFS_DRIVER: StaticCell<FlashDriver> = StaticCell::new();
static STORAGE_MANAGER: StaticCell<Mutex<CriticalSectionRawMutex, StorageManager>> =
    StaticCell::new();
static APP_ROUTER: StaticCell<AppRouter> = StaticCell::new();

/// # Safety
///
/// `dest` and `src` must be valid non-null C string pointers. `dest` must point
/// to writable memory large enough to hold `src` including the trailing NUL.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn strcpy(dest: *mut u8, src: *const u8) -> *mut u8 {
    let mut offset = 0;

    loop {
        let byte = unsafe { src.add(offset).read() };
        unsafe {
            dest.add(offset).write(byte);
        }

        if byte == 0 {
            break;
        }

        offset += 1;
    }

    dest
}

#[embassy_executor::main]
async fn main(spawner: Spawner) {
    let p = embassy_rp::init(Default::default());

    let mut rng = RoscRng;
    let usb_seed = rng.next_u64();
    let wifi_seed = rng.next_u64();

    // USB Driver
    let usb_driver = embassy_rp::usb::Driver::new(p.USB, Irqs);
    let usb_manager = UsbManager::new(usb_driver);
    let (usb_net_stack, usb_net_runner) = init_usb_network(usb_manager.net_device, usb_seed);
    let usb_dhcp_server = init_usb_dhcp();

    // SPI config
    let mut spi_config = Config::default();
    spi_config.frequency = 31_250_000;
    let spi_tx = Spi::new_txonly(p.SPI0, p.PIN_2, p.PIN_3, p.DMA_CH2, Irqs, spi_config);

    // PIO Driver
    let pio_driver = embassy_rp::pio::Pio::new(p.PIO0, Irqs);
    let pio_manager = PioManager::new(
        pio_driver, p.PIN_23, p.PIN_24, p.PIN_25, p.PIN_29, p.DMA_CH0, Irqs,
    );

    // LFS Driver
    let flash = Flash::new(p.FLASH, p.DMA_CH1, Irqs);

    let lfs_alloc = LFS_ALLOCATION.init(Allocation::new());
    let lfs_driver = LFS_DRIVER.init(FlashDriver { flash });
    let storage_manager =
        STORAGE_MANAGER.init(Mutex::new(StorageManager::new(lfs_driver, lfs_alloc)));
    let app_router = APP_ROUTER.init(AppRouter);

    storage::GLOBAL_STORAGE.store(storage_manager as *mut _, Ordering::Release);
    restore_keyboard_target().await;

    info!("Spawning services...");

    spawner.spawn(status::task()).unwrap();
    status::show(status::Stage::Boot);

    spawner.spawn(debug_task(spi_tx)).unwrap();
    debug_log!("[BOOT] Pico Bit v{} starting", env!("CARGO_PKG_VERSION"));
    let (keyboard_os, keyboard_layout) = active_keyboard_target_codes();
    debug_log!(
        "[STORAGE] LittleFS ready; keyboard={}/{}",
        keyboard_os,
        keyboard_layout
    );
    spawner
        .spawn(wifi_task(
            pio_manager.spi,
            pio_manager.pwr,
            spawner,
            app_router,
            storage_manager,
            wifi_seed,
        ))
        .unwrap();
    spawner.spawn(usb_task(usb_manager.device)).unwrap();
    spawner.spawn(ncm_task(usb_manager.net_runner)).unwrap();
    spawner.spawn(net_task(usb_net_runner)).unwrap();
    spawner
        .spawn(ncm_http_task(usb_net_stack, storage_manager))
        .unwrap();
    spawner
        .spawn(hid_task(usb_manager.hid, storage_manager))
        .unwrap();
    spawner
        .spawn(dhcp_task(usb_dhcp_server, usb_net_stack))
        .unwrap();

    debug_log!("[BOOT] firmware tasks spawned");
}

// PICOTOOL entries
#[unsafe(link_section = ".bi_entries")]
#[used]
pub static PICOTOOL_ENTRIES: [EntryAddr; 4] = [
    rp_program_name!(c"Pico Bit"),
    rp_program_description!(c"Composite HID-NCM Payload Device"),
    rp_cargo_version!(),
    rp_program_build_attribute!(),
];
