use super::service;
use picoserve::io::Read;
use picoserve::request::Request;
use picoserve::response::chunked::ChunkedResponse;
use picoserve::response::{IntoResponse, Json, ResponseWriter, StatusCode};
use picoserve::routing::{
    PathRouter, RequestHandlerService, delete, get, parse_path_segment, post_service,
};
use picoserve::{ResponseSent, Router};

const UPLOAD_CHUNK_SIZE: usize = 1024;

async fn list_armory() -> impl IntoResponse {
    ChunkedResponse::new(service::ArmoryListChunks)
}

async fn delete_armory(filename: heapless::String<64>) -> impl IntoResponse {
    let protected_payload = filename.as_str() == "payload.dd";
    let response = service::delete_file(filename.as_str()).await;
    let status = if response.is_error() {
        if protected_payload {
            StatusCode::FORBIDDEN
        } else {
            StatusCode::BAD_REQUEST
        }
    } else {
        StatusCode::OK
    };

    Json(response).into_response().with_status_code(status)
}

struct UploadArmory;

impl<State> RequestHandlerService<State, (heapless::String<64>,)> for UploadArmory {
    async fn call_request_handler_service<R, W>(
        &self,
        _state: &State,
        (filename,): (heapless::String<64>,),
        mut request: Request<'_, R>,
        response_writer: W,
    ) -> Result<ResponseSent, W::Error>
    where
        R: Read,
        W: ResponseWriter<Error = R::Error>,
    {
        let filename = filename.as_str();
        let content_length = request.body_connection.content_length();

        let (status, response) = if content_length > service::MAX_ARMORY_UPLOAD_BYTES {
            (
                StatusCode::PAYLOAD_TOO_LARGE,
                service::upload_too_large(filename),
            )
        } else {
            match service::begin_upload_result(filename).await {
                Ok(()) => {
                    let mut reader = request.body_connection.body().reader();
                    let mut buffer = [0u8; UPLOAD_CHUNK_SIZE];
                    let mut received = 0usize;
                    let mut failure = None;

                    loop {
                        let read = reader.read(&mut buffer).await?;
                        if read == 0 {
                            break;
                        }

                        received += read;
                        if received > service::MAX_ARMORY_UPLOAD_BYTES {
                            failure = Some(service::ArmoryError::TooLarge);
                            break;
                        }

                        if let Err(error) =
                            service::append_upload_chunk(filename, &buffer[..read]).await
                        {
                            failure = Some(error);
                            break;
                        }
                    }

                    match failure {
                        Some(error) => (
                            status_for_error(error),
                            service::fail_upload(filename, error).await,
                        ),
                        None => (StatusCode::OK, service::finish_upload(filename).await),
                    }
                }
                Err(error) => (
                    status_for_error(error),
                    service::fail_upload(filename, error).await,
                ),
            }
        };

        Json(response)
            .into_response()
            .with_status_code(status)
            .write_to(request.body_connection.finalize().await?, response_writer)
            .await
    }
}

fn status_for_error(error: service::ArmoryError) -> StatusCode {
    match error {
        service::ArmoryError::InvalidFilename => StatusCode::BAD_REQUEST,
        service::ArmoryError::ProtectedPayload => StatusCode::FORBIDDEN,
        service::ArmoryError::Storage => StatusCode::INSUFFICIENT_STORAGE,
        service::ArmoryError::StorageUnavailable => StatusCode::SERVICE_UNAVAILABLE,
        service::ArmoryError::TooLarge => StatusCode::PAYLOAD_TOO_LARGE,
    }
}

pub fn build<R: PathRouter>(router: Router<R, ()>) -> Router<impl PathRouter, ()> {
    router
        .route("/api/armory", get(list_armory))
        .route(
            (
                "/api/armory/upload",
                parse_path_segment::<heapless::String<64>>(),
            ),
            post_service(UploadArmory),
        )
        .route(
            ("/api/armory", parse_path_segment::<heapless::String<64>>()),
            delete(delete_armory),
        )
}
