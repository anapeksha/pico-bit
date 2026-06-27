use super::service;
use picoserve::Router;
use picoserve::response::{IntoResponse, Json};
use picoserve::routing::{PathRouter, post};

async fn update_keyboard_target() -> impl IntoResponse {
    Json(service::current_target())
}

pub fn build<R: PathRouter>(router: Router<R, ()>) -> Router<impl PathRouter, ()> {
    router.route("/api/keyboard-layout", post(update_keyboard_target))
}
