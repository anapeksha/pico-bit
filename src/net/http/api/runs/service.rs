use core::cell::RefCell;
use embassy_sync::blocking_mutex::Mutex;
use embassy_sync::blocking_mutex::raw::CriticalSectionRawMutex;
use serde::ser::{SerializeSeq, SerializeStruct};
use serde::{Serialize, Serializer};

const MAX_RUN_HISTORY: usize = 6;
const RUN_PREVIEW_MAX: usize = 64;

/// Source of a payload execution record.
#[derive(Clone, Copy)]
pub(crate) enum RunSource {
    Boot,
    Manual,
}

impl RunSource {
    /// Compact API representation of the run source.
    pub(crate) fn as_str(self) -> &'static str {
        match self {
            Self::Boot => "boot",
            Self::Manual => "run",
        }
    }
}

/// One bounded run-history entry.
#[derive(Clone, Copy)]
pub(crate) struct RunHistoryItem {
    ok: bool,
    preview: [u8; RUN_PREVIEW_MAX],
    preview_len: usize,
    sequence: usize,
    source: RunSource,
}

impl RunHistoryItem {
    const fn empty() -> Self {
        Self {
            ok: false,
            preview: [0u8; RUN_PREVIEW_MAX],
            preview_len: 0,
            sequence: 0,
            source: RunSource::Manual,
        }
    }

    fn new(sequence: usize, source: RunSource, ok: bool, preview: &str) -> Self {
        let mut entry = Self::empty();
        let preview = preview.as_bytes();
        let len = preview.len().min(RUN_PREVIEW_MAX);

        entry.ok = ok;
        entry.sequence = sequence;
        entry.source = source;
        entry.preview[..len].copy_from_slice(&preview[..len]);
        entry.preview_len = len;
        entry
    }

    /// Whether execution completed without parser/runtime errors.
    pub(crate) fn ok(&self) -> bool {
        self.ok
    }

    /// Short payload preview captured from the executed script.
    pub(crate) fn preview(&self) -> &str {
        core::str::from_utf8(&self.preview[..self.preview_len]).unwrap_or("payload.dd")
    }

    /// Monotonic sequence number within the current boot.
    pub(crate) fn sequence(&self) -> usize {
        self.sequence
    }

    /// Compact source label used by the frontend.
    pub(crate) fn source(&self) -> &'static str {
        self.source.as_str()
    }
}

/// Copyable bounded snapshot of current boot run history.
#[derive(Clone, Copy)]
pub(crate) struct RunsSnapshot {
    entries: [RunHistoryItem; MAX_RUN_HISTORY],
    len: usize,
    seeded: bool,
}

impl RunsSnapshot {
    const fn empty() -> Self {
        Self {
            entries: [RunHistoryItem::empty(); MAX_RUN_HISTORY],
            len: 0,
            seeded: false,
        }
    }

    /// Recorded entries in newest-first order.
    pub(crate) fn entries(&self) -> &[RunHistoryItem] {
        &self.entries[..self.len]
    }

    /// Whether a boot-source run has been recorded.
    pub(crate) fn seeded(&self) -> bool {
        self.seeded
    }
}

struct RunsState {
    snapshot: RunsSnapshot,
    next_sequence: usize,
}

impl RunsState {
    const fn new() -> Self {
        Self {
            snapshot: RunsSnapshot::empty(),
            next_sequence: 1,
        }
    }
}

static RUNS_STATE: Mutex<CriticalSectionRawMutex, RefCell<RunsState>> =
    Mutex::new(RefCell::new(RunsState::new()));

impl Serialize for RunHistoryItem {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let mut state = serializer.serialize_struct("RunHistoryItem", 4)?;
        state.serialize_field("ok", &self.ok)?;
        state.serialize_field("preview", self.preview())?;
        state.serialize_field("sequence", &self.sequence)?;
        state.serialize_field("source", self.source())?;
        state.end()
    }
}

impl Serialize for RunsSnapshot {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let mut state = serializer.serialize_struct("RunsResponse", 2)?;
        state.serialize_field("run_history", &RunHistoryList { snapshot: self })?;
        state.serialize_field("seeded", &self.seeded)?;
        state.end()
    }
}

struct RunHistoryList<'a> {
    snapshot: &'a RunsSnapshot,
}

impl Serialize for RunHistoryList<'_> {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let mut seq = serializer.serialize_seq(Some(self.snapshot.len))?;
        for entry in self.snapshot.entries() {
            seq.serialize_element(entry)?;
        }
        seq.end()
    }
}

/// Records an execution result in the bounded run ring.
pub(crate) fn record_run(source: RunSource, ok: bool, preview: &str) {
    RUNS_STATE.lock(|cell| {
        let mut state = cell.borrow_mut();
        let sequence = state.next_sequence;
        state.next_sequence = state.next_sequence.saturating_add(1);

        let mut index = state.snapshot.len.min(MAX_RUN_HISTORY - 1);
        while index > 0 {
            state.snapshot.entries[index] = state.snapshot.entries[index - 1];
            index -= 1;
        }

        state.snapshot.entries[0] = RunHistoryItem::new(sequence, source, ok, preview);
        state.snapshot.len = (state.snapshot.len + 1).min(MAX_RUN_HISTORY);

        if matches!(source, RunSource::Boot) {
            state.snapshot.seeded = true;
        }
    });
}

/// Returns the latest run history snapshot.
pub(crate) fn snapshot() -> RunsSnapshot {
    RUNS_STATE.lock(|cell| cell.borrow().snapshot)
}
