// src/storage/driver.rs

use embassy_rp::flash::{Async, Flash};
use embassy_rp::peripherals::FLASH;
use littlefs2::consts::{U32, U512};
use littlefs2::driver::Storage;
use littlefs2::io::{Error, Result};

/// Total onboard flash bytes on the target Pico 2 W.
pub const FLASH_SIZE: usize = 4 * 1024 * 1024;
/// Bytes reserved for LittleFS at the end of flash.
pub const FS_SIZE: usize = 1024 * 1024;
/// LittleFS partition start address inside onboard flash.
pub const FS_START: usize = FLASH_SIZE - FS_SIZE;

/// `littlefs2` storage driver backed by the RP flash peripheral.
pub struct FlashDriver {
    /// Full flash peripheral; the driver offsets operations into the FS region.
    pub flash: Flash<'static, FLASH, Async, FLASH_SIZE>,
}

impl Storage for FlashDriver {
    const READ_SIZE: usize = 16;
    const WRITE_SIZE: usize = 16;
    const BLOCK_SIZE: usize = 4096;
    const BLOCK_COUNT: usize = FS_SIZE / 4096;

    type CACHE_SIZE = U512;
    type LOOKAHEAD_SIZE = U32;

    fn read(&mut self, off: usize, buf: &mut [u8]) -> Result<usize> {
        let physical_address = (FS_START + off) as u32;

        self.flash
            .blocking_read(physical_address, buf)
            .map_err(|_| Error::IO)?;
        Ok(buf.len())
    }

    fn write(&mut self, off: usize, data: &[u8]) -> Result<usize> {
        let physical_address = (FS_START + off) as u32;

        self.flash
            .blocking_write(physical_address, data)
            .map_err(|_| Error::IO)?;
        Ok(data.len())
    }

    fn erase(&mut self, off: usize, len: usize) -> Result<usize> {
        let physical_start = (FS_START + off) as u32;
        let physical_end = (FS_START + off + len) as u32;

        self.flash
            .blocking_erase(physical_start, physical_end)
            .map_err(|_| Error::IO)?;
        Ok(len)
    }
}
