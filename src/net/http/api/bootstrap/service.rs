use crate::storage::{
    GLOBAL_STORAGE, LISTED_FILE_NAME_MAX, LISTED_FILE_PATH_MAX, ListedFile, SharedStorage,
};
use core::sync::atomic::Ordering;
use serde::ser::{SerializeSeq, SerializeStruct};
use serde::{Serialize, Serializer};

const MAX_BOOTSTRAP_FILES: usize = 16;
const MAX_BOOTSTRAP_PAYLOAD_BYTES: usize = 2048;
const MAX_ARMORY_UPLOAD_BYTES: usize = 500 * 1024;

#[derive(Serialize)]
pub(super) struct SelectOption {
    code: &'static str,
    label: &'static str,
}

pub(super) struct NcmLinkState {
    active: bool,
    address: &'static str,
    available: bool,
    filename: [u8; LISTED_FILE_NAME_MAX],
    filename_len: usize,
    gateway: &'static str,
    has_binary: bool,
    interface: &'static str,
    message: &'static str,
    root_url: &'static str,
    state: &'static str,
    transport: &'static str,
}

#[derive(Serialize)]
pub(super) struct HostHidState {
    active: bool,
    available: bool,
    message: &'static str,
    state: &'static str,
}

impl NcmLinkState {
    fn from_files(files: &FileList) -> Self {
        let mut filename = [0u8; LISTED_FILE_NAME_MAX];
        let filename_len = files
            .first_asset_name()
            .map(|name| copy_str(name, &mut filename))
            .unwrap_or(0);

        Self {
            active: true,
            address: "192.168.7.1",
            available: true,
            filename,
            filename_len,
            gateway: "192.168.7.1",
            has_binary: files.has_binary(),
            interface: "usb-ncm",
            message: "NCM link is available.",
            root_url: "http://192.168.7.1",
            state: "active",
            transport: "ncm",
        }
    }

    fn filename(&self) -> &str {
        core::str::from_utf8(&self.filename[..self.filename_len]).unwrap_or("")
    }
}

impl Serialize for NcmLinkState {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let mut state = serializer.serialize_struct("NcmLinkState", 11)?;
        state.serialize_field("active", &self.active)?;
        state.serialize_field("address", self.address)?;
        state.serialize_field("available", &self.available)?;
        state.serialize_field("filename", self.filename())?;
        state.serialize_field("gateway", self.gateway)?;
        state.serialize_field("has_binary", &self.has_binary)?;
        state.serialize_field("interface", self.interface)?;
        state.serialize_field("message", self.message)?;
        state.serialize_field("root_url", self.root_url)?;
        state.serialize_field("state", self.state)?;
        state.serialize_field("transport", self.transport)?;
        state.end()
    }
}

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

impl Serialize for FileEntry {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let mut state = serializer.serialize_struct("FileEntry", 4)?;
        state.serialize_field("name", self.name())?;
        state.serialize_field("path", self.path())?;
        state.serialize_field("size", &self.size)?;
        state.serialize_field("kind", self.kind)?;
        state.end()
    }
}

#[derive(Clone, Copy)]
pub(super) struct FileList {
    entries: [FileEntry; MAX_BOOTSTRAP_FILES],
    len: usize,
}

impl FileList {
    fn empty() -> Self {
        Self {
            entries: [FileEntry::empty(); MAX_BOOTSTRAP_FILES],
            len: 0,
        }
    }

    fn from_listed(files: &[ListedFile]) -> Self {
        let mut list = Self::empty();
        let mut index = 0;

        while index < files.len() && index < MAX_BOOTSTRAP_FILES {
            list.entries[index] = FileEntry::from_listed(&files[index]);
            index += 1;
        }

        list.len = index;
        list
    }

    fn has_binary(&self) -> bool {
        self.entries[..self.len]
            .iter()
            .any(|file| file.kind == "asset")
    }

    fn first_asset_name(&self) -> Option<&str> {
        self.entries[..self.len]
            .iter()
            .find(|file| file.kind == "asset")
            .map(FileEntry::name)
    }
}

impl Serialize for FileList {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let mut seq = serializer.serialize_seq(Some(self.len))?;
        for entry in &self.entries[..self.len] {
            seq.serialize_element(entry)?;
        }
        seq.end()
    }
}

#[derive(Serialize)]
pub(super) struct RunHistoryItem {
    message: &'static str,
    notice: &'static str,
    preview: &'static str,
    sequence: usize,
    source: &'static str,
}

#[derive(Serialize)]
pub(super) struct ValidationState {
    badge_label: &'static str,
    badge_tone: &'static str,
    blocking: bool,
    can_run: bool,
    can_save: bool,
    diagnostics: &'static [&'static str],
    error_count: usize,
    line_count: usize,
    notice: &'static str,
    summary: &'static str,
    warning_count: usize,
}

pub(super) struct PayloadText {
    bytes: [u8; MAX_BOOTSTRAP_PAYLOAD_BYTES],
    len: usize,
}

impl PayloadText {
    fn empty() -> Self {
        Self {
            bytes: [0u8; MAX_BOOTSTRAP_PAYLOAD_BYTES],
            len: 0,
        }
    }

    fn from_bytes(bytes: &[u8]) -> Self {
        let mut payload = Self::empty();
        let len = bytes.len().min(payload.bytes.len());
        payload.bytes[..len].copy_from_slice(&bytes[..len]);
        payload.len = len;
        payload
    }

    fn as_str(&self) -> &str {
        core::str::from_utf8(&self.bytes[..self.len]).unwrap_or("")
    }

    fn line_count(&self) -> usize {
        let text = self.as_str();
        if text.is_empty() {
            0
        } else {
            text.lines().count()
        }
    }
}

impl Serialize for PayloadText {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str(self.as_str())
    }
}

#[derive(Serialize)]
pub(super) struct BootstrapResponse {
    ap_password: &'static str,
    ap_ssid: &'static str,
    auth_enabled: bool,
    files: FileList,
    has_binary: bool,
    host_hid: HostHidState,
    keyboard_layout: &'static str,
    keyboard_layout_hint: &'static str,
    keyboard_layout_label: &'static str,
    keyboard_layouts: &'static [SelectOption],
    keyboard_os: &'static str,
    keyboard_os_label: &'static str,
    keyboard_oses: &'static [SelectOption],
    keyboard_target_label: &'static str,
    max_upload_bytes: usize,
    message: &'static str,
    notice: &'static str,
    payload: PayloadText,
    payload_file: &'static str,
    run_history: &'static [RunHistoryItem],
    seeded: bool,
    ncm_link: NcmLinkState,
    validation: ValidationState,
}

static KEYBOARD_LAYOUTS: &[SelectOption] = &[SelectOption {
    code: "US",
    label: "English (US)",
}];

static KEYBOARD_OSES: &[SelectOption] = &[
    SelectOption {
        code: "WIN",
        label: "Windows",
    },
    SelectOption {
        code: "MAC",
        label: "macOS",
    },
    SelectOption {
        code: "LINUX",
        label: "Linux",
    },
];

static RUN_HISTORY: &[RunHistoryItem] = &[RunHistoryItem {
    message: "Bootstrap placeholder loaded.",
    notice: "success",
    preview: "REM Pico Bit startup placeholder",
    sequence: 1,
    source: "bootstrap",
}];

static EMPTY_DIAGNOSTICS: &[&str] = &[];

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

async fn littlefs_files() -> FileList {
    let Some(storage) = storage() else {
        return FileList::empty();
    };

    let storage_guard = storage.lock().await;
    let mut listed = [ListedFile::empty(); MAX_BOOTSTRAP_FILES];

    match storage_guard.list_files(&mut listed) {
        Ok(count) => FileList::from_listed(&listed[..count]),
        Err(_) => FileList::empty(),
    }
}

async fn current_payload() -> PayloadText {
    let Some(storage) = storage() else {
        return PayloadText::empty();
    };

    let storage_guard = storage.lock().await;
    let mut buffer = [0u8; MAX_BOOTSTRAP_PAYLOAD_BYTES];

    match storage_guard.read("payload.dd", &mut buffer) {
        Ok(bytes) => PayloadText::from_bytes(bytes),
        Err(_) => PayloadText::empty(),
    }
}

pub(super) async fn snapshot() -> BootstrapResponse {
    let files = littlefs_files().await;
    let payload = current_payload().await;
    let line_count = payload.line_count();
    let has_binary = files.has_binary();

    BootstrapResponse {
        ap_password: "PicoBit24Net",
        ap_ssid: "PicoBit",
        auth_enabled: false,
        files,
        has_binary,
        host_hid: HostHidState {
            active: true,
            available: true,
            message: "Host HID interface is available.",
            state: "active",
        },
        keyboard_layout: "US",
        keyboard_layout_hint: "Used for typed text and remembered on the device.",
        keyboard_layout_label: "English (US)",
        keyboard_layouts: KEYBOARD_LAYOUTS,
        keyboard_os: "WIN",
        keyboard_os_label: "Windows",
        keyboard_oses: KEYBOARD_OSES,
        keyboard_target_label: "Windows - English (US)",
        max_upload_bytes: MAX_ARMORY_UPLOAD_BYTES,
        message: "Bootstrap loaded from littlefs2.",
        notice: "success",
        payload,
        payload_file: "payload.dd",
        run_history: RUN_HISTORY,
        seeded: false,
        ncm_link: NcmLinkState::from_files(&files),
        validation: ValidationState {
            badge_label: "Ready",
            badge_tone: "success",
            blocking: false,
            can_run: true,
            can_save: true,
            diagnostics: EMPTY_DIAGNOSTICS,
            error_count: 0,
            line_count,
            notice: "success",
            summary: "Payload loaded from flash.",
            warning_count: 0,
        },
    }
}
