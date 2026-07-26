use embassy_rp::uart::{Async, UartTx};

use crate::debug::{DebugManager, LOG_CHANNEL};

#[embassy_executor::task]
pub async fn debug_task(uart_tx: UartTx<'static, Async>) {
    let mut debug_manager = DebugManager::new(uart_tx);

    loop {
        let message = LOG_CHANNEL.receive().await;

        debug_manager.log(message).await;
    }
}
