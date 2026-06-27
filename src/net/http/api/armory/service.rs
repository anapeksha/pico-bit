use crate::storage::{
    GLOBAL_STORAGE, LISTED_FILE_NAME_MAX, LISTED_FILE_PATH_MAX, ListedFile, SharedStorage,
};
use core::sync::atomic::Ordering;
use serde::ser::{SerializeSeq, SerializeStruct};
use serde::{Serialize, Serializer};

pub(super) const MAX_ARMORY_UPLOAD_BYTES: usize = 500 * 1024;

const ARMORY_DIR: &str = "/armory";
const ARMORY_PREFIX: &str = "/armory/";
const MAX_ARMORY_FILES: usize = 16;

#[derive(Clone, Copy)]
pub(super) struct ArmoryFile {
    name: [u8; LISTED_FILE_NAME_MAX],
    name_len: usize,
    path: [u8; LISTED_FILE_PATH_MAX],
    path_len: usize,
    size: usize,
    kind: &'static str,
}

impl ArmoryFile {
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

impl Serialize for ArmoryFile {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let mut state = serializer.serialize_struct("ArmoryFile", 5)?;
        state.serialize_field("kind", self.kind)?;
        state.serialize_field("name", self.name())?;
        state.serialize_field("path", self.path())?;
        state.serialize_field("size", &self.size)?;
        state.serialize_field("url", self.path())?;
        state.end()
    }
}

#[derive(Clone, Copy)]
pub(super) struct ArmoryFileList {
    entries: [ArmoryFile; MAX_ARMORY_FILES],
    len: usize,
}

impl ArmoryFileList {
    fn empty() -> Self {
        Self {
            entries: [ArmoryFile::empty(); MAX_ARMORY_FILES],
            len: 0,
        }
    }

    fn from_listed(files: &[ListedFile]) -> Self {
        let mut list = Self::empty();
        let mut index = 0;

        while index < files.len() && index < MAX_ARMORY_FILES {
            list.entries[index] = ArmoryFile::from_listed(&files[index]);
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
}

impl Serialize for ArmoryFileList {
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
pub(super) struct ArmoryListResponse {
    files: ArmoryFileList,
    has_binary: bool,
    max_upload_bytes: usize,
    message: &'static str,
    notice: &'static str,
}

pub(super) struct ArmoryMutationResponse {
    filename: [u8; LISTED_FILE_NAME_MAX],
    filename_len: usize,
    has_binary: bool,
    max_upload_bytes: usize,
    message: &'static str,
    notice: &'static str,
}

impl ArmoryMutationResponse {
    fn new(filename: &str, has_binary: bool, message: &'static str, notice: &'static str) -> Self {
        let mut response = Self {
            filename: [0u8; LISTED_FILE_NAME_MAX],
            filename_len: 0,
            has_binary,
            max_upload_bytes: MAX_ARMORY_UPLOAD_BYTES,
            message,
            notice,
        };
        response.filename_len = copy_str(filename, &mut response.filename);
        response
    }

    fn filename(&self) -> &str {
        core::str::from_utf8(&self.filename[..self.filename_len]).unwrap_or("")
    }

    pub(super) fn is_error(&self) -> bool {
        self.notice == "error"
    }
}

impl Serialize for ArmoryMutationResponse {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let mut state = serializer.serialize_struct("ArmoryMutationResponse", 5)?;
        state.serialize_field("filename", self.filename())?;
        state.serialize_field("has_binary", &self.has_binary)?;
        state.serialize_field("max_upload_bytes", &self.max_upload_bytes)?;
        state.serialize_field("message", self.message)?;
        state.serialize_field("notice", self.notice)?;
        state.end()
    }
}

#[derive(Clone, Copy, PartialEq)]
pub(super) enum ArmoryError {
    InvalidFilename,
    ProtectedPayload,
    Storage,
    StorageUnavailable,
    TooLarge,
}

impl ArmoryError {
    fn message(self) -> &'static str {
        match self {
            Self::InvalidFilename => "Invalid filename.",
            Self::ProtectedPayload => "payload.dd is managed by the editor and cannot be deleted.",
            Self::Storage => "littlefs2 storage operation failed.",
            Self::StorageUnavailable => "littlefs2 storage is not initialized.",
            Self::TooLarge => "Upload exceeds 500 KB capacity limit.",
        }
    }
}

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

fn validate_filename(filename: &str) -> Result<(), ArmoryError> {
    if filename.is_empty()
        || filename == "."
        || filename == ".."
        || filename == "payload.dd"
        || filename.as_bytes().len() > LISTED_FILE_NAME_MAX
    {
        return Err(ArmoryError::InvalidFilename);
    }

    for byte in filename.as_bytes() {
        if *byte == b'/' || *byte == b'\\' || *byte == 0 {
            return Err(ArmoryError::InvalidFilename);
        }
    }

    Ok(())
}

fn armory_path<'a>(
    filename: &str,
    path_buffer: &'a mut [u8; LISTED_FILE_PATH_MAX],
) -> Result<&'a str, ArmoryError> {
    validate_filename(filename)?;

    let prefix = ARMORY_PREFIX.as_bytes();
    let name = filename.as_bytes();
    let total_len = prefix.len() + name.len();

    if total_len > path_buffer.len() {
        return Err(ArmoryError::InvalidFilename);
    }

    path_buffer.fill(0);
    path_buffer[..prefix.len()].copy_from_slice(prefix);
    path_buffer[prefix.len()..total_len].copy_from_slice(name);

    core::str::from_utf8(&path_buffer[..total_len]).map_err(|_| ArmoryError::InvalidFilename)
}

async fn list_files() -> ArmoryFileList {
    let Some(storage) = storage() else {
        return ArmoryFileList::empty();
    };

    let storage_guard = storage.lock().await;
    let mut listed = [ListedFile::empty(); MAX_ARMORY_FILES];

    match storage_guard.list_files(&mut listed) {
        Ok(count) => ArmoryFileList::from_listed(&listed[..count]),
        Err(_) => ArmoryFileList::empty(),
    }
}

pub(super) async fn list() -> ArmoryListResponse {
    let files = list_files().await;
    ArmoryListResponse {
        files,
        has_binary: files.has_binary(),
        max_upload_bytes: MAX_ARMORY_UPLOAD_BYTES,
        message: "Armory files loaded from littlefs2.",
        notice: "success",
    }
}

pub(super) fn upload_too_large(filename: &str) -> ArmoryMutationResponse {
    ArmoryMutationResponse::new(filename, false, ArmoryError::TooLarge.message(), "error")
}

pub(super) async fn begin_upload_result(filename: &str) -> Result<(), ArmoryError> {
    let Some(storage) = storage() else {
        return Err(ArmoryError::StorageUnavailable);
    };

    let mut path_buffer = [0u8; LISTED_FILE_PATH_MAX];
    let path = armory_path(filename, &mut path_buffer)?;
    let storage_guard = storage.lock().await;
    storage_guard
        .ensure_dir(ARMORY_DIR)
        .map_err(|_| ArmoryError::Storage)?;
    storage_guard
        .truncate(path)
        .map_err(|_| ArmoryError::Storage)
}

pub(super) async fn append_upload_chunk(filename: &str, chunk: &[u8]) -> Result<(), ArmoryError> {
    let Some(storage) = storage() else {
        return Err(ArmoryError::StorageUnavailable);
    };

    let mut path_buffer = [0u8; LISTED_FILE_PATH_MAX];
    let path = armory_path(filename, &mut path_buffer)?;
    let storage_guard = storage.lock().await;
    storage_guard
        .append(path, chunk)
        .map_err(|_| ArmoryError::Storage)
}

pub(super) async fn finish_upload(filename: &str) -> ArmoryMutationResponse {
    let files = list_files().await;
    ArmoryMutationResponse::new(
        filename,
        files.has_binary(),
        "Upload committed to flash.",
        "success",
    )
}

pub(super) async fn fail_upload(filename: &str, error: ArmoryError) -> ArmoryMutationResponse {
    let _ = delete_file_result(filename).await;
    ArmoryMutationResponse::new(filename, false, error.message(), "error")
}

pub(super) async fn delete_file(filename: &str) -> ArmoryMutationResponse {
    match delete_file_result(filename).await {
        Ok(()) => {
            let files = list_files().await;
            ArmoryMutationResponse::new(
                filename,
                files.has_binary(),
                "File removed from flash.",
                "success",
            )
        }
        Err(error) => ArmoryMutationResponse::new(filename, false, error.message(), "error"),
    }
}

async fn delete_file_result(filename: &str) -> Result<(), ArmoryError> {
    if filename == "payload.dd" {
        return Err(ArmoryError::ProtectedPayload);
    }

    let Some(storage) = storage() else {
        return Err(ArmoryError::StorageUnavailable);
    };

    let mut path_buffer = [0u8; LISTED_FILE_PATH_MAX];
    let path = armory_path(filename, &mut path_buffer)?;
    let storage_guard = storage.lock().await;
    storage_guard.erase(path).map_err(|_| ArmoryError::Storage)
}
