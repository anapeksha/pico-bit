use super::service::{self, SavePayloadRequest};
use picoserve::Router;
use picoserve::extract::JsonWithUnescapeBufferSize;
use picoserve::response::IntoResponse;
use picoserve::routing::{PathRouter, get, post};

async fn get_payload() -> impl IntoResponse {
    service::read_response()
}

async fn save_payload(
    JsonWithUnescapeBufferSize(_): JsonWithUnescapeBufferSize<SavePayloadRequest, 2048>,
) -> impl IntoResponse {
    service::save_response().await
}

async fn run_payload() -> impl IntoResponse {
    service::run_response().await
}

pub fn build<R: PathRouter>(router: Router<R, ()>) -> Router<impl PathRouter, ()> {
    router
        .route("/api/payload", get(get_payload).post(save_payload))
        .route("/api/payload/run", post(run_payload))
}
