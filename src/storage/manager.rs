// src/storage/manager.rs

use crate::storage::FlashDriver;
use core::sync::atomic::AtomicPtr;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::mutex::Mutex;
use littlefs2::fs::{Allocation, Filesystem};
use littlefs2::io::{Error, Result, SeekFrom};
use littlefs2::path::Path;

pub const LISTED_FILE_NAME_MAX: usize = 64;
pub const LISTED_FILE_PATH_MAX: usize = 128;

#[derive(Clone, Copy)]
pub struct ListedFile {
    name: [u8; LISTED_FILE_NAME_MAX],
    name_len: usize,
    path: [u8; LISTED_FILE_PATH_MAX],
    path_len: usize,
    size: usize,
}

impl ListedFile {
    pub const fn empty() -> Self {
        Self {
            name: [0u8; LISTED_FILE_NAME_MAX],
            name_len: 0,
            path: [0u8; LISTED_FILE_PATH_MAX],
            path_len: 0,
            size: 0,
        }
    }

    fn set(&mut self, name: &str, path: &str, size: usize) -> Result<()> {
        self.name_len = copy_str(name, &mut self.name)?;
        self.path_len = copy_str(path, &mut self.path)?;
        self.size = size;
        Ok(())
    }

    pub fn name(&self) -> &str {
        core::str::from_utf8(&self.name[..self.name_len]).unwrap_or("")
    }

    pub fn path(&self) -> &str {
        core::str::from_utf8(&self.path[..self.path_len]).unwrap_or("")
    }

    pub fn size(&self) -> usize {
        self.size
    }
}

fn copy_str(value: &str, target: &mut [u8]) -> Result<usize> {
    let bytes = value.as_bytes();
    if bytes.len() > target.len() {
        return Err(Error::FILENAME_TOO_LONG);
    }

    target.fill(0);
    target[..bytes.len()].copy_from_slice(bytes);
    Ok(bytes.len())
}

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

        let manager = Self { fs };
        let _ = manager.ensure_dir("/armory");
        let _ = manager.ensure_payload_file();

        manager
    }

    fn with_path<F, T>(&self, path: &str, f: F) -> Result<T>
    where
        F: FnOnce(&Path) -> Result<T>,
    {
        let mut path_buf = [0u8; LISTED_FILE_PATH_MAX];
        let bytes = path.as_bytes();

        if bytes.len() >= path_buf.len() {
            return Err(Error::FILENAME_TOO_LONG);
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

    pub fn read_at(&self, path: &str, offset: usize, buffer: &mut [u8]) -> Result<usize> {
        self.with_path(path, |p| {
            self.fs.open_file_and_then(p, |file| {
                file.seek(SeekFrom::Start(offset as u32))?;
                file.read(buffer)
            })
        })
    }

    pub fn write(&self, path: &str, data: &[u8]) -> Result<()> {
        self.with_path(path, |p| {
            self.fs.open_file_with_options_and_then(
                |options| options.write(true).create(true).truncate(true),
                p,
                |file| {
                    if !data.is_empty() {
                        file.write(data)?;
                    }
                    Ok(())
                },
            )
        })
    }

    pub fn append(&self, path: &str, data: &[u8]) -> Result<()> {
        self.with_path(path, |p| {
            self.fs.open_file_with_options_and_then(
                |options| options.write(true).create(true).append(true),
                p,
                |file| {
                    if !data.is_empty() {
                        file.write(data)?;
                    }
                    Ok(())
                },
            )
        })
    }

    pub fn ensure_dir(&self, path: &str) -> Result<()> {
        self.with_path(path, |p| self.fs.create_dir_all(p))
    }

    fn ensure_payload_file(&self) -> Result<()> {
        let mut scratch = [0u8; 1];
        match self.read("payload.dd", &mut scratch) {
            Ok(_) => Ok(()),
            Err(Error::NO_SUCH_ENTRY) => self.write("payload.dd", &[]),
            Err(error) => Err(error),
        }
    }

    pub fn truncate(&self, path: &str) -> Result<()> {
        self.with_path(path, |p| {
            self.fs.open_file_with_options_and_then(
                |options| options.write(true).create(true).truncate(true),
                p,
                |_| Ok(()),
            )
        })
    }

    #[allow(dead_code)]
    pub fn erase(&self, path: &str) -> Result<()> {
        self.with_path(path, |p| self.fs.remove(p))
    }

    pub fn list_files<const N: usize>(&self, entries: &mut [ListedFile; N]) -> Result<usize> {
        let mut count = 0;

        self.list_directory("/", entries, &mut count)?;

        match self.list_directory("/armory", entries, &mut count) {
            Ok(()) | Err(Error::NO_SUCH_ENTRY) => {}
            Err(error) => return Err(error),
        }

        Ok(count)
    }

    fn list_directory<const N: usize>(
        &self,
        path: &str,
        entries: &mut [ListedFile; N],
        count: &mut usize,
    ) -> Result<()> {
        self.with_path(path, |p| {
            self.fs.read_dir_and_then(p, |dir| {
                for entry in dir {
                    if *count >= N {
                        break;
                    }

                    let entry = entry?;
                    let name = entry.file_name().as_str();

                    if name == "." || name == ".." || !entry.file_type().is_file() {
                        continue;
                    }

                    if entries[*count]
                        .set(name, entry.path().as_str(), entry.metadata().len())
                        .is_ok()
                    {
                        *count += 1;
                    }
                }

                Ok(())
            })
        })
    }
}

pub type SharedStorage = Mutex<CriticalSectionRawMutex, StorageManager>;

pub static GLOBAL_STORAGE: AtomicPtr<SharedStorage> = AtomicPtr::new(core::ptr::null_mut());
