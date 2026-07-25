use defmt::error;
use embassy_rp::uart::{Async, UartTx};

pub struct DebugManager {
    uart_tx: UartTx<'static, Async>,
}

impl DebugManager {
    pub fn new(uart_tx: UartTx<'static, Async>) -> Self {
        Self { uart_tx }
    }

    pub async fn log(&mut self, data: &[u8]) {
        let written = self.uart_tx.write(data).await;
        match written {
            Ok(_) => {}
            Err(e) => error!("Failed to write: {}", e),
        }
    }
}
