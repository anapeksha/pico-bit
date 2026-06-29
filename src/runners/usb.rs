use defmt::{error, info, warn};
use embassy_net::{Runner as NetRunner, Stack};
use embassy_rp::peripherals::USB;
use embassy_rp::usb::Driver;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::mutex::Mutex;
use embassy_time::Timer;
use embassy_usb::UsbDevice;
use embassy_usb::class::cdc_ncm::embassy_net::{Device, Runner as NcmRunner};
use embassy_usb::class::hid::HidWriter;
use leasehund::DhcpServer;
use littlefs2::io::Error;
use usbd_hid::descriptor::KeyboardReport;

use crate::ducky::{DuckyError, DuckyExecutor, DuckyParser, StatefulWriter};
use crate::storage::StorageManager;

use super::MTU;

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
pub async fn hid_task(
    mut hid: HidWriter<'static, Driver<'static, USB>, 8>,
    storage: &'static Mutex<CriticalSectionRawMutex, StorageManager>,
) {
    info!("Waiting for USB HID execution layer readiness...");
    hid.ready().await;
    info!("USB HID Connected! Initializing runner loop...");

    let mut content_buffer = [0u8; 2048];
    let mut hardware_writer = EmbassyUsbWriter { writer: &mut hid };
    let mut executor = DuckyExecutor::new();
    executor.set_keyboard_layout(crate::net::active_keyboard_layout());

    if let Err(e) = run_script_payload(
        &mut hardware_writer,
        &mut executor,
        storage,
        &mut content_buffer,
    )
    .await
    {
        error!("Script execution failed: {:?}", e);
    }

    loop {
        Timer::after_secs(1).await;
    }
}

#[embassy_executor::task]
pub async fn dhcp_task(mut server: DhcpServer<32, 4>, stack: &'static Stack<'static>) {
    server.run(*stack).await;
}

struct EmbassyUsbWriter<'a> {
    writer: &'a mut HidWriter<'static, Driver<'static, USB>, 8>,
}

impl<'a> StatefulWriter for EmbassyUsbWriter<'a> {
    async fn write_report(&mut self, report: &KeyboardReport) {
        let bytes: [u8; 8] = unsafe { core::mem::transmute_copy(report) };
        let _ = self.writer.write(&bytes).await;
    }

    async fn clear_report(&mut self) {
        let blank = [0u8; 8];
        let _ = self.writer.write(&blank).await;
    }

    async fn delay_ms(&mut self, ms: u32) {
        Timer::after_millis(ms as u64).await;
    }
}

async fn run_script_payload<'buf>(
    writer: &mut EmbassyUsbWriter<'_>,
    executor: &mut DuckyExecutor<'buf>,
    storage: &'static Mutex<CriticalSectionRawMutex, StorageManager>,
    content_buffer: &'buf mut [u8; 2048],
) -> Result<(), crate::ducky::DuckyError> {
    let bytes_written_len = {
        let storage_guard = storage.lock().await;
        match storage_guard.read("payload.dd", content_buffer) {
            Ok(bytes) => bytes.len(),
            Err(Error::NO_SUCH_ENTRY) => {
                warn!("payload.dd not found in storage. Executing fallback...");
                let fallback = b"REM Stateless Fallback\nDELAY 500\n";
                content_buffer[..fallback.len()].copy_from_slice(fallback);
                fallback.len()
            }
            Err(_) => {
                error!("Storage read failed due to an unexpected driver error.");
                return Err(crate::ducky::DuckyError::UnknownCommand);
            }
        }
    };

    let script_text = core::str::from_utf8(&content_buffer[..bytes_written_len])
        .map_err(|_| DuckyError::InvalidKey)?;

    let mut current_line_idx = 1;
    for raw_line in script_text.lines() {
        let trimmed = raw_line.trim();
        if trimmed.is_empty() {
            continue;
        }

        if let Ok(command) = DuckyParser::parse_line(trimmed) {
            match executor
                .execute_command(command, current_line_idx, writer)
                .await
            {
                Ok(Some(custom_delay)) => Timer::after_millis(custom_delay as u64).await,
                Ok(None) => {}
                Err(e) => error!("Line {} Exec Error: {:?}", current_line_idx, e),
            }
        } else {
            error!("Line {} Parse Error", current_line_idx);
        }
        current_line_idx += 1;
    }

    info!("Payload execution loop completed.");
    Ok(())
}
