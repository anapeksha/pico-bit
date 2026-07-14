use super::service;
use picoserve::Router;
use picoserve::response::{IntoResponse, Json};
use picoserve::routing::{PathRouter, get};

async fn get_metrics() -> impl IntoResponse {
    Json(service::snapshot().await)
}

pub fn build<R: PathRouter>(router: Router<R, ()>) -> Router<impl PathRouter, ()> {
    router.route("/api/metrics", get(get_metrics))
}
