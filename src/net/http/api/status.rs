use picoserve::Router;
use picoserve::response::{IntoResponse, Json};
use picoserve::routing::{PathRouter, get};
use serde::Serialize;

#[derive(Serialize)]
struct StatusResponse {
    status: &'static str,
    uptime: u64,
}

async fn get_status() -> impl IntoResponse {
    let response = StatusResponse {
        status: "running",
        uptime: 120,
    };

    Json(response)
}

pub fn build<R: PathRouter>(router: Router<R, ()>) -> Router<impl PathRouter, ()> {
    router.route("/api/status", get(get_status))
}
