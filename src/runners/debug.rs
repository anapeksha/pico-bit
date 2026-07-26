use embassy_rp::{
    peripherals::SPI0,
    spi::{Async, Spi},
};

use crate::debug::{DebugManager, LOG_CHANNEL};

#[embassy_executor::task]
pub async fn debug_task(spi_tx: Spi<'static, SPI0, Async>) {
    let mut debug_manager = DebugManager::new(spi_tx);

    loop {
        let message = LOG_CHANNEL.receive().await;

        debug_manager.log(message).await;
    }
}
