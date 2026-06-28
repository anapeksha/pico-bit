use super::service;
use picoserve::Router;
use picoserve::extract::Json;
use picoserve::response::{IntoResponse, Json as JsonResponse, StatusCode};
use picoserve::routing::{PathRouter, post};

async fn update_keyboard_target(
    Json(request): Json<service::KeyboardTargetRequest>,
) -> impl IntoResponse {
    let response = service::update_target(request);
    let status = if response.is_error() {
        StatusCode::BAD_REQUEST
    } else {
        StatusCode::OK
    };

    JsonResponse(response)
        .into_response()
        .with_status_code(status)
}

pub fn build<R: PathRouter>(router: Router<R, ()>) -> Router<impl PathRouter, ()> {
    router.route("/api/keyboard-layout", post(update_keyboard_target))
}
