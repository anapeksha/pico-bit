use defmt::{error, info, warn};
use embassy_net::{Runner as NetRunner, Stack};
use embassy_rp::peripherals::USB;
use embassy_rp::usb::Driver;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::mutex::Mutex;
use embassy_time::{Duration, Timer, with_timeout};
use embassy_usb::UsbDevice;
use embassy_usb::class::cdc_ncm::embassy_net::{Device, Runner as NcmRunner};
use embassy_usb::class::hid::HidWriter;
use leasehund::DhcpServer;
use littlefs2::io::Error;
use usbd_hid::descriptor::KeyboardReport;

use crate::ducky::{DuckyError, DuckyExecutor, DuckyParser, StatefulWriter};
use crate::storage::StorageManager;

use super::MTU;

/// Runs the composite USB device.
#[embassy_executor::task]
pub async fn usb_task(mut usb: UsbDevice<'static, Driver<'static, USB>>) {
    usb.run().await;
}

/// Runs the CDC-NCM USB class and marks the NCM link active.
#[embassy_executor::task]
pub async fn ncm_task(runner: NcmRunner<'static, Driver<'static, USB>, MTU>) {
    crate::net::set_ncm_active(true);
    crate::status::show(crate::status::Stage::UsbAgentMounted);
    runner.run().await;
}

/// Runs the Embassy network stack for USB NCM.
#[embassy_executor::task]
pub async fn net_task(mut runner: NetRunner<'static, Device<'static, MTU>>) {
    runner.run().await;
}

/// Owns HID readiness and executes `payload.dd` at boot and on manual triggers.
#[embassy_executor::task]
pub async fn hid_task(
    mut hid: HidWriter<'static, Driver<'static, USB>, 8>,
    storage: &'static Mutex<CriticalSectionRawMutex, StorageManager>,
) {
    info!("Waiting for USB HID execution layer readiness...");
    crate::status::show(crate::status::Stage::HidConstructed);
    if with_timeout(Duration::from_secs(30), hid.ready())
        .await
        .is_err()
    {
        crate::status::error(crate::status::Fault::UsbEnumTimeout);
        hid.ready().await;
    }
    crate::net::set_host_hid_active(true);
    crate::status::show(crate::status::Stage::UsbEnumerated);
    info!("USB HID Connected! Initializing runner loop...");

    let mut content_buffer = [0u8; 2048];
    let mut hardware_writer = EmbassyUsbWriter { writer: &mut hid };

    record_execution_result(
        crate::net::RunSource::Boot,
        run_script_payload(&mut hardware_writer, storage, &mut content_buffer).await,
    );

    loop {
        if crate::net::consume_payload_run_trigger() {
            record_execution_result(
                crate::net::RunSource::Manual,
                run_script_payload(&mut hardware_writer, storage, &mut content_buffer).await,
            );
        }

        Timer::after_millis(100).await;
    }
}

/// Runs a DHCP server for a prepared network stack.
#[embassy_executor::task]
pub async fn dhcp_task(mut server: DhcpServer<32, 4>, stack: &'static Stack<'static>) {
    server.run(*stack).await;
}

struct EmbassyUsbWriter<'a> {
    writer: &'a mut HidWriter<'static, Driver<'static, USB>, 8>,
}

struct PayloadExecution {
    has_content: bool,
    ok: bool,
    preview: PayloadPreview,
}

struct PayloadPreview {
    bytes: [u8; 64],
    len: usize,
}

impl PayloadPreview {
    fn fallback() -> Self {
        Self::from_str("payload.dd")
    }

    fn from_script(script: &str) -> Self {
        for line in script.lines() {
            let line = line.trim();
            if !line.is_empty() {
                return Self::from_str(line);
            }
        }

        Self::fallback()
    }

    fn from_str(value: &str) -> Self {
        let mut preview = Self {
            bytes: [0u8; 64],
            len: 0,
        };
        let bytes = value.as_bytes();
        preview.len = bytes.len().min(preview.bytes.len());
        preview.bytes[..preview.len].copy_from_slice(&bytes[..preview.len]);
        preview
    }

    fn as_str(&self) -> &str {
        core::str::from_utf8(&self.bytes[..self.len]).unwrap_or("payload.dd")
    }
}

fn record_execution_result(
    source: crate::net::RunSource,
    result: Result<PayloadExecution, crate::ducky::DuckyError>,
) {
    match result {
        Ok(execution) => {
            if matches!(source, crate::net::RunSource::Boot) && !execution.has_content {
                return;
            }

            crate::net::record_payload_run(source, execution.ok, execution.preview.as_str());
        }
        Err(error) => {
            error!("Script execution failed: {:?}", error);
            crate::status::error(crate::status::Fault::ScriptError);
            crate::net::record_payload_run(source, false, "payload.dd");
        }
    }
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

async fn run_script_payload(
    writer: &mut EmbassyUsbWriter<'_>,
    storage: &'static Mutex<CriticalSectionRawMutex, StorageManager>,
    content_buffer: &mut [u8; 2048],
) -> Result<PayloadExecution, crate::ducky::DuckyError> {
    let mut executor = DuckyExecutor::new();
    executor.set_keyboard_layout(crate::net::active_keyboard_layout());

    let bytes_written_len = {
        let storage_guard = storage.lock().await;
        match storage_guard.read("payload.dd", content_buffer) {
            Ok(bytes) => bytes.len(),
            Err(Error::NO_SUCH_ENTRY) => {
                warn!("payload.dd not found in storage. Executing fallback...");
                crate::status::error(crate::status::Fault::PayloadMissing);
                let fallback = b"REM Stateless Fallback\nDELAY 500\n";
                content_buffer[..fallback.len()].copy_from_slice(fallback);
                fallback.len()
            }
            Err(_) => {
                error!("Storage read failed due to an unexpected driver error.");
                crate::status::error(crate::status::Fault::PayloadReadFailed);
                return Err(crate::ducky::DuckyError::UnknownCommand);
            }
        }
    };

    let script_text = core::str::from_utf8(&content_buffer[..bytes_written_len])
        .map_err(|_| DuckyError::InvalidKey)?;
    let preview = PayloadPreview::from_script(script_text);
    let has_content = script_text.lines().any(|line| !line.trim().is_empty());
    let mut ok = true;

    crate::status::show(crate::status::Stage::PayloadEntered);
    crate::status::show(crate::status::Stage::PayloadReady);
    crate::status::show(crate::status::Stage::PayloadRunning);

    let mut current_line_idx = 1;
    for raw_line in script_text.lines() {
        let trimmed = raw_line.trim();
        if trimmed.is_empty() {
            continue;
        }

        if let Ok(command) =
            DuckyParser::parse_line_for_os(trimmed, crate::net::active_keyboard_os())
        {
            match executor
                .execute_command(command, current_line_idx, writer)
                .await
            {
                Ok(Some(custom_delay)) => Timer::after_millis(custom_delay as u64).await,
                Ok(None) => {}
                Err(e) => {
                    ok = false;
                    crate::status::error(crate::status::Fault::ScriptError);
                    error!("Line {} Exec Error: {:?}", current_line_idx, e);
                }
            }
        } else {
            ok = false;
            crate::status::error(crate::status::Fault::ScriptError);
            error!("Line {} Parse Error", current_line_idx);
        }
        current_line_idx += 1;
    }

    info!("Payload execution loop completed.");
    if ok {
        crate::status::show(crate::status::Stage::PayloadComplete);
    }
    Ok(PayloadExecution {
        has_content,
        ok,
        preview,
    })
}
