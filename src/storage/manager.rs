// src/storage/manager.rs

use crate::storage::FlashDriver;
use core::sync::atomic::AtomicPtr;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::mutex::Mutex;
use littlefs2::fs::{Allocation, Filesystem};
use littlefs2::io::Result;
use littlefs2::path::Path;

pub struct StorageManager {
    fs: Filesystem<'static, FlashDriver>,
}

impl StorageManager {
    pub fn new(
        driver: &'static mut FlashDriver,
        alloc: &'static mut Allocation<FlashDriver>,
    ) -> Self {
        let mount_successful = Filesystem::mount(alloc, driver).is_ok();

        if !mount_successful {
            Filesystem::format(driver).unwrap();
        }

        let fs = Filesystem::mount(alloc, driver).unwrap();

        Self { fs }
    }

    fn with_path<F, T>(&self, path: &str, f: F) -> Result<T>
    where
        F: FnOnce(&Path) -> Result<T>,
    {
        let mut path_buf = [0u8; 64];
        let bytes = path.as_bytes();

        if bytes.len() >= path_buf.len() {
            return Err(littlefs2::io::Error::FILENAME_TOO_LONG);
        }

        path_buf[..bytes.len()].copy_from_slice(bytes);
        path_buf[bytes.len()] = b'\0'; // Explicitly inject the null terminator

        let p = Path::from_str_with_nul(core::str::from_utf8(&path_buf[..=bytes.len()]).unwrap())
            .unwrap();

        f(p)
    }

    pub fn read<'a>(&self, path: &str, buffer: &'a mut [u8]) -> Result<&'a [u8]> {
        self.with_path(path, |p| {
            self.fs.open_file_and_then(p, |file| {
                let bytes_read = file.read(buffer)?;
                Ok(&buffer[..bytes_read])
            })
        })
    }

    pub fn write(&self, path: &str, data: &mut [u8]) -> Result<()> {
        self.with_path(path, |p| {
            self.fs.open_file_and_then(p, |file| {
                file.write(data)?;
                Ok(())
            })
        })
    }

    #[allow(dead_code)]
    pub fn erase(&self, path: &str) -> Result<()> {
        self.with_path(path, |p| self.fs.remove(p))
    }
}

pub type SharedStorage = Mutex<CriticalSectionRawMutex, StorageManager>;

pub static GLOBAL_STORAGE: AtomicPtr<SharedStorage> = AtomicPtr::new(core::ptr::null_mut());
