use core::fmt::Arguments;
use core::fmt::write;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::channel::Channel;
use heapless::String;

const LOG_MESSAGE_CAPACITY: usize = 96;
const LOG_QUEUE_DEPTH: usize = 16;

pub(crate) type DebugMessage = String<LOG_MESSAGE_CAPACITY>;

pub static LOG_CHANNEL: Channel<CriticalSectionRawMutex, DebugMessage, LOG_QUEUE_DEPTH> =
    Channel::new();

pub(crate) struct DebugLogger;

impl DebugLogger {
    pub fn log(args: Arguments<'_>) {
        let mut log_message = DebugMessage::new();

        let _ = write(&mut log_message, args);
        while log_message.len() > LOG_MESSAGE_CAPACITY - 2 {
            let _ = log_message.pop();
        }
        let _ = log_message.push_str("\r\n");

        // Field logging must never delay USB, networking, or flash operations.
        let _ = LOG_CHANNEL.try_send(log_message);
    }
}

#[macro_export]
macro_rules! debug_log {
    ($($arg:tt)*) => {
        $crate::debug::DebugLogger::log(format_args!($($arg)*));
    };
}
