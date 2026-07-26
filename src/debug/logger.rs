use core::fmt::Arguments;
use core::fmt::write;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::channel::Channel;
use heapless::String;

pub static LOG_CHANNEL: Channel<CriticalSectionRawMutex, String<64>, 16> = Channel::new();

pub(crate) struct DebugLogger;

impl DebugLogger {
    pub async fn log(args: Arguments<'_>) {
        let mut log_message = String::<64>::new();

        write(&mut log_message, args).ok();
        log_message.push_str("\r\n").ok();

        LOG_CHANNEL.send(log_message).await;
    }
}

#[macro_export]
macro_rules! debug_log {
    ($($arg:tt)*) => {
        $crate::debug::DebugLogger::log(format_args!($($arg)*)).await;
    };
}
