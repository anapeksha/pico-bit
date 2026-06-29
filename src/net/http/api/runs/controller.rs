use super::service;
use picoserve::Router;
use picoserve::response::{IntoResponse, Json};
use picoserve::routing::{PathRouter, get};

async fn get_runs() -> impl IntoResponse {
    Json(service::snapshot())
}

pub fn build<R: PathRouter>(router: Router<R, ()>) -> Router<impl PathRouter, ()> {
    router.route("/api/runs", get(get_runs))
}
