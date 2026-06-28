use super::service::{self, SavePayloadRequest};
use picoserve::Router;
use picoserve::extract::JsonWithUnescapeBufferSize;
use picoserve::response::chunked::ChunkedResponse;
use picoserve::response::{IntoResponse, Json, StatusCode};
use picoserve::routing::{PathRouter, get, post};

async fn get_payload() -> impl IntoResponse {
    ChunkedResponse::new(service::PayloadChunks)
}

async fn save_payload(
    JsonWithUnescapeBufferSize(_): JsonWithUnescapeBufferSize<SavePayloadRequest, 2048>,
) -> impl IntoResponse {
    let response = service::save_staged().await;
    let status = if response.is_error() {
        StatusCode::BAD_REQUEST
    } else {
        StatusCode::OK
    };

    Json(response).into_response().with_status_code(status)
}

async fn run_payload() -> impl IntoResponse {
    let response = service::trigger_run().await;
    let status = if response.is_error() {
        StatusCode::BAD_REQUEST
    } else {
        StatusCode::OK
    };

    Json(response).into_response().with_status_code(status)
}

pub fn build<R: PathRouter>(router: Router<R, ()>) -> Router<impl PathRouter, ()> {
    router
        .route("/api/payload", get(get_payload).post(save_payload))
        .route("/api/payload/run", post(run_payload))
}
