use serde::Serialize;

#[derive(Serialize)]
pub(super) struct RunHistoryItem {
    ok: bool,
    preview: &'static str,
    sequence: usize,
    source: &'static str,
}

#[derive(Serialize)]
pub(super) struct RunsResponse {
    run_history: &'static [RunHistoryItem],
    seeded: bool,
}

static RUN_HISTORY: &[RunHistoryItem] = &[RunHistoryItem {
    ok: true,
    preview: "payload.dd",
    sequence: 1,
    source: "bootstrap",
}];

pub(super) fn snapshot() -> RunsResponse {
    RunsResponse {
        run_history: RUN_HISTORY,
        seeded: false,
    }
}
