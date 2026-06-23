// src/storage/driver.rs

use embassy_rp::flash::{Async, Flash};
use embassy_rp::peripherals::FLASH;
use littlefs2::consts::{U32, U512};
use littlefs2::driver::Storage;
use littlefs2::io::{Error, Result};

pub const FLASH_SIZE: usize = 4 * 1024 * 1024;
pub const FS_SIZE: usize = 1024 * 1024;
pub const FS_START: usize = FLASH_SIZE - FS_SIZE;

pub struct FlashDriver {
    // CHANGE: Use FLASH_SIZE here so the driver accepts addresses up to 4MB
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
