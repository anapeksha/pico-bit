use crate::debug::{DebugManager, LOG_CHANNEL};

#[embassy_executor::task]
pub async fn debug_task(mut debug_manager: DebugManager) {
    loop {
        let message = LOG_CHANNEL.receive().await;

        debug_manager.log(message.as_bytes()).await;
    }
}
