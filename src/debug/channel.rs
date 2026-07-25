use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::channel::Channel;
use heapless::String;

pub static LOG_CHANNEL: Channel<CriticalSectionRawMutex, String<64>, 16> = Channel::new();
