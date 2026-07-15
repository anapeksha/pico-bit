use core::cell::RefCell;
use core::sync::atomic::Ordering;
use embassy_sync::blocking_mutex::Mutex;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use embassy_sync::mutex::Mutex as AsyncMutex;
use embassy_time::Instant;
use heapless::String;
use picoserve::ResponseSent;
use picoserve::io::{Read, Write};
use picoserve::request::Request;
use picoserve::response::chunked::{ChunkWriter, ChunkedResponse, Chunks, ChunksWritten};
use picoserve::response::{IntoResponse, Json, ResponseWriter, StatusCode};
use picoserve::routing::RequestHandlerService;
use serde::ser::SerializeStruct;
use serde::{Serialize, Serializer};

use crate::net::http::delivery::{STAGED_BINARY_NAME, STAGED_BINARY_PATH};
use crate::status::{self as status_led, Stage};
use crate::storage::{
    GLOBAL_STORAGE, LISTED_FILE_NAME_MAX, LISTED_FILE_PATH_MAX, ListedFile, SharedStorage,
    StorageManager,
};

use super::super::metrics;

pub(super) const MAX_ARMORY_UPLOAD_BYTES: usize = 750 * 1024;

const ARMORY_DIR: &str = "/armory";
const ARMORY_PREFIX: &str = "/armory/";
const MAX_ARMORY_FILES: usize = 16;
const UPLOAD_CHUNK_SIZE: usize = 1024;
pub(super) const DOWNLOAD_CHUNK_SIZE: usize = 1024;

#[derive(Clone, Copy)]
pub(super) struct ArmoryFile {
    name: [u8; LISTED_FILE_NAME_MAX],
    name_len: usize,
    size: usize,
    kind: &'static str,
}

impl ArmoryFile {
    const fn empty() -> Self {
        Self {
            name: [0u8; LISTED_FILE_NAME_MAX],
            name_len: 0,
            size: 0,
            kind: "asset",
        }
    }

    fn from_listed(file: &ListedFile) -> Self {
        let mut entry = Self::empty();
        entry.name_len = copy_str(file.name(), &mut entry.name);
        entry.size = file.size();
        entry.kind = file_kind(file.name(), file.path());
        entry
    }

    fn name(&self) -> &str {
        core::str::from_utf8(&self.name[..self.name_len]).unwrap_or("")
    }
}

#[derive(Clone, Copy)]
pub(super) struct ArmoryFileList {
    entries: [ArmoryFile; MAX_ARMORY_FILES],
    len: usize,
}

impl ArmoryFileList {
    const fn empty() -> Self {
        Self {
            entries: [ArmoryFile::empty(); MAX_ARMORY_FILES],
            len: 0,
        }
    }

    fn replace_from_listed(&mut self, files: &[ListedFile]) {
        *self = Self::empty();
        let mut index = 0;
        let mut has_asset = false;

        for file in files {
            if !is_public_armory_file(file.path()) {
                continue;
            }

            let kind = file_kind(file.name(), file.path());
            if kind == "asset" && has_asset {
                continue;
            }

            self.entries[index] = ArmoryFile::from_listed(file);
            has_asset |= kind == "asset";
            index += 1;

            if index >= MAX_ARMORY_FILES {
                break;
            }
        }

        self.len = index;
    }

    fn has_binary(&self) -> bool {
        self.entries[..self.len]
            .iter()
            .any(|file| file.kind == "asset")
    }
}

pub(super) struct ArmoryMutationResponse {
    code: &'static str,
    filename: [u8; LISTED_FILE_NAME_MAX],
    filename_len: usize,
    has_binary: bool,
    message: &'static str,
    notice: &'static str,
}

pub(super) struct ArmoryListChunks;

#[derive(Clone, Copy)]
pub(super) struct ArmoryDownloadChunks {
    filename: [u8; LISTED_FILE_NAME_MAX],
    filename_len: usize,
}

impl ArmoryDownloadChunks {
    pub(super) fn new(filename: &str) -> Self {
        let mut body = Self {
            filename: [0u8; LISTED_FILE_NAME_MAX],
            filename_len: 0,
        };
        body.filename_len = copy_str(filename, &mut body.filename);
        body
    }

    fn filename(&self) -> &str {
        core::str::from_utf8(&self.filename[..self.filename_len]).unwrap_or("")
    }
}

impl ArmoryMutationResponse {
    fn new(
        code: &'static str,
        filename: &str,
        has_binary: bool,
        message: &'static str,
        notice: &'static str,
    ) -> Self {
        let mut response = Self {
            code,
            filename: [0u8; LISTED_FILE_NAME_MAX],
            filename_len: 0,
            has_binary,
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

static ARMORY_FILES: Mutex<CriticalSectionRawMutex, RefCell<ArmoryFileList>> =
    Mutex::new(RefCell::new(ArmoryFileList::empty()));
static LISTED_SCRATCH: AsyncMutex<CriticalSectionRawMutex, [ListedFile; MAX_ARMORY_FILES]> =
    AsyncMutex::new([ListedFile::empty(); MAX_ARMORY_FILES]);

impl Serialize for ArmoryMutationResponse {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let mut state = serializer.serialize_struct("ArmoryMutationResponse", 5)?;
        state.serialize_field("code", self.code)?;
        state.serialize_field("filename", self.filename())?;
        state.serialize_field("has_binary", &self.has_binary)?;
        state.serialize_field("message", self.message)?;
        state.serialize_field("notice", self.notice)?;
        state.end()
    }
}

impl Chunks for ArmoryListChunks {
    fn content_type(&self) -> &'static str {
        "application/json"
    }

    async fn write_chunks<W: Write>(
        self,
        mut writer: ChunkWriter<W>,
    ) -> Result<ChunksWritten, W::Error> {
        let has_binary = refresh_armory_files();
        let len = ARMORY_FILES.lock(|cell| cell.borrow().len);

        writer.write_chunk(b"{\"files\":[").await?;

        for index in 0..len {
            let file = ARMORY_FILES.lock(|cell| cell.borrow().entries[index]);
            if index > 0 {
                writer.write_chunk(b",").await?;
            }

            writer.write_chunk(b"{\"kind\":\"").await?;
            writer.write_chunk(file.kind.as_bytes()).await?;
            writer.write_chunk(b"\",\"name\":").await?;
            write_json_string(&mut writer, file.name().as_bytes()).await?;
            writer.write_chunk(b",\"size\":").await?;
            writer.write_fmt(format_args!("{}", file.size)).await?;
            writer.write_chunk(b"}").await?;
        }

        writer.write_chunk(b"],\"has_binary\":").await?;
        writer
            .write_chunk(if has_binary { b"true" } else { b"false" })
            .await?;
        writer.write_chunk(b"}").await?;
        writer.finalize().await
    }
}

impl Chunks for ArmoryDownloadChunks {
    fn content_type(&self) -> &'static str {
        "application/octet-stream"
    }

    async fn write_chunks<W: Write>(
        self,
        mut writer: ChunkWriter<W>,
    ) -> Result<ChunksWritten, W::Error> {
        let mut offset = 0usize;
        let mut chunk = [0u8; DOWNLOAD_CHUNK_SIZE];

        loop {
            let read = read_file_chunk(self.filename(), offset, &mut chunk).await;
            if read == 0 {
                break;
            }

            writer.write_chunk(&chunk[..read]).await?;
            offset += read;
        }

        writer.finalize().await
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
    fn code(self) -> &'static str {
        match self {
            Self::InvalidFilename => "invalid_filename",
            Self::ProtectedPayload => "protected_payload",
            Self::Storage => "storage_error",
            Self::StorageUnavailable => "storage_unavailable",
            Self::TooLarge => "too_large",
        }
    }

    fn message(self) -> &'static str {
        match self {
            Self::InvalidFilename => "Invalid filename.",
            Self::ProtectedPayload => "payload.dd is managed by the editor and cannot be deleted.",
            Self::Storage => "littlefs2 storage operation failed.",
            Self::StorageUnavailable => "littlefs2 storage is not initialized.",
            Self::TooLarge => "Upload exceeds 750 KB capacity limit.",
        }
    }
}

pub(super) fn list_response() -> impl IntoResponse {
    ChunkedResponse::new(ArmoryListChunks)
}

pub(super) async fn delete_response(filename: String<64>) -> impl IntoResponse {
    let protected_payload = filename.as_str() == "payload.dd";
    let response = delete_file(filename.as_str()).await;
    let status = if response.is_error() {
        if protected_payload {
            StatusCode::FORBIDDEN
        } else {
            StatusCode::BAD_REQUEST
        }
    } else {
        StatusCode::OK
    };

    Json(response).into_response().with_status_code(status)
}

pub(super) fn download_response(filename: String<64>) -> impl IntoResponse {
    ChunkedResponse::new(ArmoryDownloadChunks::new(filename.as_str()))
        .into_response()
        .with_header("Cache-Control", "no-store")
}

pub(super) struct UploadArmory;

impl<State> RequestHandlerService<State, ()> for UploadArmory {
    async fn call_request_handler_service<R, W>(
        &self,
        _state: &State,
        _: (),
        mut request: Request<'_, R>,
        response_writer: W,
    ) -> Result<ResponseSent, W::Error>
    where
        R: Read,
        W: ResponseWriter<Error = R::Error>,
    {
        let content_length = request.body_connection.content_length();

        let (status, response) = if content_length > MAX_ARMORY_UPLOAD_BYTES {
            metrics::record_upload(0, 0);
            (
                StatusCode::PAYLOAD_TOO_LARGE,
                upload_too_large(STAGED_BINARY_NAME),
            )
        } else {
            upload_stream(&mut request).await?
        };

        Json(response)
            .into_response()
            .with_status_code(status)
            .write_to(request.body_connection.finalize().await?, response_writer)
            .await
    }
}

async fn upload_stream<R: Read>(
    request: &mut Request<'_, R>,
) -> Result<(StatusCode, ArmoryMutationResponse), R::Error> {
    let started = Instant::now();
    let Some(storage) = storage() else {
        let error = ArmoryError::StorageUnavailable;
        metrics::record_upload(0, started.elapsed().as_millis());
        return Ok((status_for_error(error), fail_upload(error).await));
    };

    status_led::show(Stage::BinaryInjecting);
    let storage_guard = storage.lock().await;

    if let Err(error) = begin_upload(&storage_guard) {
        drop(storage_guard);
        metrics::record_upload(0, started.elapsed().as_millis());
        return Ok((status_for_error(error), fail_upload(error).await));
    }

    let mut reader = request.body_connection.body().reader();
    let mut buffer = [0u8; UPLOAD_CHUNK_SIZE];
    let mut received = 0usize;
    let mut failure = None;

    loop {
        let read = reader.read(&mut buffer).await?;
        if read == 0 {
            break;
        }

        received += read;
        if received > MAX_ARMORY_UPLOAD_BYTES {
            failure = Some(ArmoryError::TooLarge);
            break;
        }

        if let Err(error) = append_upload_chunk(&storage_guard, &buffer[..read]) {
            failure = Some(error);
            break;
        }
    }

    let result = match failure {
        Some(error) => {
            let _ = storage_guard.erase(STAGED_BINARY_PATH);
            Err(error)
        }
        None => Ok(()),
    };

    drop(storage_guard);
    metrics::record_upload(received, started.elapsed().as_millis());

    Ok(match result {
        Ok(()) => (StatusCode::OK, finish_upload().await),
        Err(error) => (status_for_error(error), fail_upload(error).await),
    })
}

fn status_for_error(error: ArmoryError) -> StatusCode {
    match error {
        ArmoryError::InvalidFilename => StatusCode::BAD_REQUEST,
        ArmoryError::ProtectedPayload => StatusCode::FORBIDDEN,
        ArmoryError::Storage => StatusCode::INSUFFICIENT_STORAGE,
        ArmoryError::StorageUnavailable => StatusCode::SERVICE_UNAVAILABLE,
        ArmoryError::TooLarge => StatusCode::PAYLOAD_TOO_LARGE,
    }
}

async fn write_json_string<W: Write>(
    writer: &mut ChunkWriter<W>,
    bytes: &[u8],
) -> Result<(), W::Error> {
    writer.write_chunk(b"\"").await?;

    let mut start = 0usize;
    for (index, byte) in bytes.iter().copied().enumerate() {
        let escape = match byte {
            b'"' => Some(&b"\\\""[..]),
            b'\\' => Some(&b"\\\\"[..]),
            b'\n' => Some(&b"\\n"[..]),
            b'\r' => Some(&b"\\r"[..]),
            b'\t' => Some(&b"\\t"[..]),
            _ => None,
        };

        if let Some(escape) = escape {
            if start < index {
                writer.write_chunk(&bytes[start..index]).await?;
            }
            writer.write_chunk(escape).await?;
            start = index + 1;
        }
    }

    if start < bytes.len() {
        writer.write_chunk(&bytes[start..]).await?;
    }

    writer.write_chunk(b"\"").await
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

fn is_public_armory_file(path: &str) -> bool {
    path == "/payload.dd" || path.starts_with(ARMORY_PREFIX)
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
        || filename.len() > LISTED_FILE_NAME_MAX
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

fn download_path<'a>(
    filename: &str,
    path_buffer: &'a mut [u8; LISTED_FILE_PATH_MAX],
) -> Result<&'a str, ArmoryError> {
    if filename == "payload.dd" {
        path_buffer.fill(0);
        path_buffer[..filename.len()].copy_from_slice(filename.as_bytes());
        return core::str::from_utf8(&path_buffer[..filename.len()])
            .map_err(|_| ArmoryError::InvalidFilename);
    }

    armory_path(filename, path_buffer)
}

fn set_armory_files(files: ArmoryFileList) {
    ARMORY_FILES.lock(|cell| {
        *cell.borrow_mut() = files;
    });
}

fn refresh_armory_files() -> bool {
    let Some(storage) = storage() else {
        set_armory_files(ArmoryFileList::empty());
        return false;
    };

    let Ok(storage_guard) = storage.try_lock() else {
        return ARMORY_FILES.lock(|cell| cell.borrow().has_binary());
    };
    let Ok(mut listed) = LISTED_SCRATCH.try_lock() else {
        return ARMORY_FILES.lock(|cell| cell.borrow().has_binary());
    };
    let listed_count = storage_guard.list_files(&mut listed).ok();

    ARMORY_FILES.lock(|files_cell| {
        let mut files = files_cell.borrow_mut();
        if let Some(count) = listed_count {
            files.replace_from_listed(&listed[..count]);
        } else {
            *files = ArmoryFileList::empty();
        }
        files.has_binary()
    })
}

pub(super) fn upload_too_large(filename: &str) -> ArmoryMutationResponse {
    status_led::show(Stage::BinaryInjectFailed);
    ArmoryMutationResponse::new(
        ArmoryError::TooLarge.code(),
        filename,
        false,
        ArmoryError::TooLarge.message(),
        "error",
    )
}

async fn read_file_chunk(filename: &str, offset: usize, buffer: &mut [u8]) -> usize {
    let Some(storage) = storage() else {
        return 0;
    };

    let mut path_buffer = [0u8; LISTED_FILE_PATH_MAX];
    let Ok(path) = download_path(filename, &mut path_buffer) else {
        return 0;
    };

    let storage_guard = storage.lock().await;
    storage_guard.read_at(path, offset, buffer).unwrap_or(0)
}

fn begin_upload(storage: &StorageManager) -> Result<(), ArmoryError> {
    storage
        .ensure_dir(ARMORY_DIR)
        .map_err(|_| ArmoryError::Storage)?;
    remove_existing_armory_files(storage)?;
    storage
        .truncate(STAGED_BINARY_PATH)
        .map_err(|_| ArmoryError::Storage)
}

fn append_upload_chunk(storage: &StorageManager, chunk: &[u8]) -> Result<(), ArmoryError> {
    storage
        .append(STAGED_BINARY_PATH, chunk)
        .map_err(|_| ArmoryError::Storage)
}

pub(super) async fn finish_upload() -> ArmoryMutationResponse {
    let has_binary = refresh_armory_files();
    status_led::show(Stage::LootImported);
    ArmoryMutationResponse::new(
        "ok",
        STAGED_BINARY_NAME,
        has_binary,
        "Upload committed to flash.",
        "success",
    )
}

pub(super) async fn fail_upload(error: ArmoryError) -> ArmoryMutationResponse {
    status_led::show(Stage::BinaryInjectFailed);
    ArmoryMutationResponse::new(
        error.code(),
        STAGED_BINARY_NAME,
        false,
        error.message(),
        "error",
    )
}

pub(super) async fn delete_file(filename: &str) -> ArmoryMutationResponse {
    match delete_file_result(filename).await {
        Ok(()) => {
            let has_binary = refresh_armory_files();
            ArmoryMutationResponse::new(
                "ok",
                filename,
                has_binary,
                "File removed from flash.",
                "success",
            )
        }
        Err(error) => {
            ArmoryMutationResponse::new(error.code(), filename, false, error.message(), "error")
        }
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

fn remove_existing_armory_files(storage: &StorageManager) -> Result<(), ArmoryError> {
    let mut listed = [ListedFile::empty(); MAX_ARMORY_FILES];
    let count = storage
        .list_files(&mut listed)
        .map_err(|_| ArmoryError::Storage)?
        .min(MAX_ARMORY_FILES);

    for file in &listed[..count] {
        let path = file.path();
        if path.starts_with(ARMORY_PREFIX) {
            storage.erase(path).map_err(|_| ArmoryError::Storage)?;
        }
    }

    Ok(())
}
