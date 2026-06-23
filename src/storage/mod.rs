mod driver;
mod manager;

pub use driver::FlashDriver;
pub use manager::StorageManager;
pub use manager::{GLOBAL_STORAGE, SharedStorage};
