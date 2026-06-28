use super::service;
use picoserve::Router;
use picoserve::extract::Json;
use picoserve::response::IntoResponse;
use picoserve::routing::{PathRouter, post};

async fn update_keyboard_target(
    Json(request): Json<service::KeyboardTargetRequest>,
) -> impl IntoResponse {
    service::update_response(request)
}

pub fn build<R: PathRouter>(router: Router<R, ()>) -> Router<impl PathRouter, ()> {
    router.route("/api/keyboard/layout", post(update_keyboard_target))
}
