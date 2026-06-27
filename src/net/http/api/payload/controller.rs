use super::service::{self, SavePayloadRequest};
use picoserve::Router;
use picoserve::extract::JsonWithUnescapeBufferSize;
use picoserve::response::{IntoResponse, Json};
use picoserve::routing::{PathRouter, get, post};

async fn get_payload() -> impl IntoResponse {
    static mut BUFFER: [u8; 2048] = [0u8; 2048];

    let buffer_ref: &'static mut [u8; 2048] = unsafe { &mut *core::ptr::addr_of_mut!(BUFFER) };
    Json(service::read(buffer_ref).await)
}

async fn save_payload(
    JsonWithUnescapeBufferSize(_): JsonWithUnescapeBufferSize<SavePayloadRequest, 2048>,
) -> impl IntoResponse {
    Json(service::save_staged().await)
}

async fn validate_payload(
    JsonWithUnescapeBufferSize(_): JsonWithUnescapeBufferSize<SavePayloadRequest, 2048>,
) -> impl IntoResponse {
    Json(service::validate_staged())
}

async fn run_payload() -> impl IntoResponse {
    Json(service::trigger_run())
}

pub fn build<R: PathRouter>(router: Router<R, ()>) -> Router<impl PathRouter, ()> {
    router
        .route("/api/payload", get(get_payload).post(save_payload))
        .route("/api/payload/validate", post(validate_payload))
        .route("/api/payload/run", post(run_payload))
}
