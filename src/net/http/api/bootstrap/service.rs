use crate::storage::{
    GLOBAL_STORAGE, LISTED_FILE_NAME_MAX, LISTED_FILE_PATH_MAX, ListedFile, SharedStorage,
};
use crate::utils::json_chunks;
use core::cell::RefCell;
use core::sync::atomic::Ordering;
use embassy_sync::blocking_mutex::Mutex;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::mutex::Mutex as AsyncMutex;
use picoserve::io::Write;
use picoserve::response::chunked::{ChunkWriter, Chunks, ChunksWritten};

const MAX_BOOTSTRAP_FILES: usize = 16;
const MAX_BOOTSTRAP_PAYLOAD_BYTES: usize = 2048;
const MAX_ARMORY_UPLOAD_BYTES: usize = 500 * 1024;

#[derive(Clone, Copy)]
pub(super) struct FileEntry {
    name: [u8; LISTED_FILE_NAME_MAX],
    name_len: usize,
    path: [u8; LISTED_FILE_PATH_MAX],
    path_len: usize,
    size: usize,
    kind: &'static str,
}

impl FileEntry {
    const fn empty() -> Self {
        Self {
            name: [0u8; LISTED_FILE_NAME_MAX],
            name_len: 0,
            path: [0u8; LISTED_FILE_PATH_MAX],
            path_len: 0,
            size: 0,
            kind: "asset",
        }
    }

    fn from_listed(file: &ListedFile) -> Self {
        let mut entry = Self::empty();
        entry.name_len = copy_str(file.name(), &mut entry.name);
        entry.path_len = copy_str(file.path(), &mut entry.path);
        entry.size = file.size();
        entry.kind = file_kind(entry.name(), entry.path());
        entry
    }

    fn name(&self) -> &str {
        core::str::from_utf8(&self.name[..self.name_len]).unwrap_or("")
    }

    fn path(&self) -> &str {
        core::str::from_utf8(&self.path[..self.path_len]).unwrap_or("")
    }
}

#[derive(Clone, Copy)]
pub(super) struct FileList {
    entries: [FileEntry; MAX_BOOTSTRAP_FILES],
    len: usize,
}

impl FileList {
    const fn empty() -> Self {
        Self {
            entries: [FileEntry::empty(); MAX_BOOTSTRAP_FILES],
            len: 0,
        }
    }

    fn replace_from_listed(&mut self, files: &[ListedFile]) {
        *self = Self::empty();
        let mut index = 0;

        while index < files.len() && index < MAX_BOOTSTRAP_FILES {
            self.entries[index] = FileEntry::from_listed(&files[index]);
            index += 1;
        }

        self.len = index;
    }

    fn has_binary(&self) -> bool {
        self.entries[..self.len]
            .iter()
            .any(|file| file.kind == "asset")
    }

    fn first_asset_name(&self) -> &str {
        self.entries[..self.len]
            .iter()
            .find(|file| file.kind == "asset")
            .map(FileEntry::name)
            .unwrap_or("")
    }
}

struct SnapshotFacts {
    has_binary: bool,
    first_asset_name: [u8; LISTED_FILE_NAME_MAX],
    first_asset_name_len: usize,
}

impl SnapshotFacts {
    const fn empty() -> Self {
        Self {
            has_binary: false,
            first_asset_name: [0u8; LISTED_FILE_NAME_MAX],
            first_asset_name_len: 0,
        }
    }

    fn first_asset_name(&self) -> &str {
        core::str::from_utf8(&self.first_asset_name[..self.first_asset_name_len]).unwrap_or("")
    }
}

#[derive(Clone, Copy)]
pub(super) struct PayloadText {
    bytes: [u8; MAX_BOOTSTRAP_PAYLOAD_BYTES],
    len: usize,
}

impl PayloadText {
    const fn empty() -> Self {
        Self {
            bytes: [0u8; MAX_BOOTSTRAP_PAYLOAD_BYTES],
            len: 0,
        }
    }
}

static SNAPSHOT_FILES: Mutex<CriticalSectionRawMutex, RefCell<FileList>> =
    Mutex::new(RefCell::new(FileList::empty()));
static SNAPSHOT_PAYLOAD: Mutex<CriticalSectionRawMutex, RefCell<PayloadText>> =
    Mutex::new(RefCell::new(PayloadText::empty()));
static LISTED_SCRATCH: AsyncMutex<CriticalSectionRawMutex, [ListedFile; MAX_BOOTSTRAP_FILES]> =
    AsyncMutex::new([ListedFile::empty(); MAX_BOOTSTRAP_FILES]);
static PAYLOAD_SCRATCH: AsyncMutex<CriticalSectionRawMutex, [u8; MAX_BOOTSTRAP_PAYLOAD_BYTES]> =
    AsyncMutex::new([0u8; MAX_BOOTSTRAP_PAYLOAD_BYTES]);

fn copy_str(value: &str, target: &mut [u8]) -> usize {
    let bytes = value.as_bytes();
    let len = bytes.len().min(target.len());
    target.fill(0);
    target[..len].copy_from_slice(&bytes[..len]);
    len
}

fn file_kind(name: &str, path: &str) -> &'static str {
    if name == "payload.dd" || path == "/payload.dd" {
        "ducky"
    } else {
        "asset"
    }
}

fn storage() -> Option<&'static SharedStorage> {
    let ptr = GLOBAL_STORAGE.load(Ordering::Acquire);
    if ptr.is_null() {
        None
    } else {
        Some(unsafe { &*ptr })
    }
}

fn clear_snapshot() {
    SNAPSHOT_FILES.lock(|cell| {
        *cell.borrow_mut() = FileList::empty();
    });
    SNAPSHOT_PAYLOAD.lock(|cell| {
        *cell.borrow_mut() = PayloadText::empty();
    });
}

async fn refresh_snapshot() -> SnapshotFacts {
    let Some(storage) = storage() else {
        clear_snapshot();
        return SnapshotFacts::empty();
    };

    let storage_guard = storage.lock().await;
    let mut facts = SnapshotFacts::empty();

    let mut listed = LISTED_SCRATCH.lock().await;
    let listed_count = storage_guard.list_files(&mut listed).ok();

    SNAPSHOT_FILES.lock(|snapshot_cell| {
        let mut files = snapshot_cell.borrow_mut();
        if let Some(count) = listed_count {
            files.replace_from_listed(&listed[..count]);
        } else {
            *files = FileList::empty();
        }
        facts.has_binary = files.has_binary();
        facts.first_asset_name_len =
            copy_str(files.first_asset_name(), &mut facts.first_asset_name);
    });
    drop(listed);

    let mut scratch = PAYLOAD_SCRATCH.lock().await;
    let payload_len = storage_guard
        .read("payload.dd", &mut scratch[..])
        .map(|bytes| bytes.len())
        .unwrap_or(0);

    SNAPSHOT_PAYLOAD.lock(|snapshot_cell| {
        let mut payload = snapshot_cell.borrow_mut();
        payload.bytes[..payload_len].copy_from_slice(&scratch[..payload_len]);
        payload.len = payload_len;
    });

    facts
}

#[derive(Clone, Copy)]
pub(super) struct BootstrapChunks;

impl Chunks for BootstrapChunks {
    fn content_type(&self) -> &'static str {
        "application/json"
    }

    async fn write_chunks<W: Write>(
        self,
        mut writer: ChunkWriter<W>,
    ) -> Result<ChunksWritten, W::Error> {
        let facts = refresh_snapshot().await;

        json_chunks::raw(
            &mut writer,
            b"{\"ap_password\":\"PicoBit24Net\",\"ap_ssid\":\"PicoBit\",\"files\":",
        )
        .await?;
        write_files(&mut writer).await?;
        json_chunks::raw(&mut writer, b",\"has_binary\":").await?;
        json_chunks::bool_value(&mut writer, facts.has_binary).await?;
        json_chunks::raw(
            &mut writer,
            b",\"host_hid\":{\"active\":true,\"available\":true,\"message\":\"Host HID interface is available.\",\"state\":\"active\"},\"keyboard_layout\":\"US\",\"keyboard_layout_hint\":\"Used for typed text and remembered on the device.\",\"keyboard_layout_label\":\"English (US)\",\"keyboard_layouts\":[{\"code\":\"US\",\"label\":\"English (US)\"}],\"keyboard_os\":\"WIN\",\"keyboard_os_label\":\"Windows\",\"keyboard_oses\":[{\"code\":\"WIN\",\"label\":\"Windows\"},{\"code\":\"MAC\",\"label\":\"macOS\"},{\"code\":\"LINUX\",\"label\":\"Linux\"}],\"keyboard_target_label\":\"Windows - English (US)\",\"max_upload_bytes\":",
        )
        .await?;
        json_chunks::usize_value(&mut writer, MAX_ARMORY_UPLOAD_BYTES).await?;
        json_chunks::raw(
            &mut writer,
            b",\"message\":\"Bootstrap loaded from littlefs2.\",\"notice\":\"success\",\"payload\":",
        )
        .await?;
        write_payload(&mut writer).await?;
        json_chunks::raw(
            &mut writer,
            b",\"payload_file\":\"payload.dd\",\"run_history\":[{\"message\":\"Bootstrap placeholder loaded.\",\"notice\":\"success\",\"preview\":\"REM Pico Bit startup placeholder\",\"sequence\":1,\"source\":\"bootstrap\"}],\"seeded\":false,\"ncm_link\":{\"active\":true,\"address\":\"192.168.7.1\",\"available\":true,\"filename\":",
        )
        .await?;
        json_chunks::string(&mut writer, facts.first_asset_name()).await?;
        json_chunks::raw(&mut writer, b",\"gateway\":\"192.168.7.1\",\"has_binary\":").await?;
        json_chunks::bool_value(&mut writer, facts.has_binary).await?;
        json_chunks::raw(
            &mut writer,
            b",\"interface\":\"usb-ncm\",\"message\":\"NCM link is available.\",\"root_url\":\"http://192.168.7.1\",\"state\":\"active\",\"transport\":\"ncm\"}}",
        )
        .await?;

        writer.finalize().await
    }
}

async fn write_files<W: Write>(writer: &mut ChunkWriter<W>) -> Result<(), W::Error> {
    json_chunks::raw(writer, b"[").await?;

    let len = SNAPSHOT_FILES.lock(|cell| cell.borrow().len);
    let mut index = 0;

    while index < len {
        if index > 0 {
            json_chunks::raw(writer, b",").await?;
        }

        if let Some(file) = SNAPSHOT_FILES.lock(|cell| cell.borrow().entries.get(index).copied()) {
            write_file_entry(writer, &file).await?;
        }

        index += 1;
    }

    json_chunks::raw(writer, b"]").await
}

async fn write_file_entry<W: Write>(
    writer: &mut ChunkWriter<W>,
    file: &FileEntry,
) -> Result<(), W::Error> {
    json_chunks::raw(writer, b"{\"name\":").await?;
    json_chunks::string(writer, file.name()).await?;
    json_chunks::raw(writer, b",\"path\":").await?;
    json_chunks::string(writer, file.path()).await?;
    json_chunks::raw(writer, b",\"size\":").await?;
    json_chunks::usize_value(writer, file.size).await?;
    json_chunks::raw(writer, b",\"kind\":").await?;
    json_chunks::string(writer, file.kind).await?;
    json_chunks::raw(writer, b"}").await
}

async fn write_payload<W: Write>(writer: &mut ChunkWriter<W>) -> Result<(), W::Error> {
    let len = SNAPSHOT_PAYLOAD.lock(|cell| cell.borrow().len);
    let mut offset = 0;
    let mut buffer = [0u8; 96];

    json_chunks::string_start(writer).await?;

    while offset < len {
        let copied = SNAPSHOT_PAYLOAD.lock(|cell| {
            let payload = cell.borrow();
            let count = (len - offset).min(buffer.len());
            buffer[..count].copy_from_slice(&payload.bytes[offset..offset + count]);
            count
        });

        json_chunks::string_bytes(writer, &buffer[..copied]).await?;
        offset += copied;
    }

    json_chunks::string_end(writer).await
}
