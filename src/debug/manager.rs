use crate::debug::DebugMessage;
use defmt::error;
use embassy_rp::peripherals::SPI0;
use embassy_rp::spi::{Async, Spi};

pub struct DebugManager {
    spi_tx: Spi<'static, SPI0, Async>,
}

impl DebugManager {
    pub fn new(spi_tx: Spi<'static, SPI0, Async>) -> Self {
        Self { spi_tx }
    }

    pub async fn log(&mut self, data: DebugMessage) {
        let written = self.spi_tx.write(data.as_bytes()).await;
        match written {
            Ok(_) => {}
            Err(e) => error!("Failed to write: {}", e),
        }
    }
}
