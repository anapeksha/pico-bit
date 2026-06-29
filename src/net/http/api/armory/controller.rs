use super::service;
use picoserve::Router;
use picoserve::response::IntoResponse;
use picoserve::routing::{PathRouter, get, parse_path_segment, post_service};

async fn list_armory() -> impl IntoResponse {
    service::list_response().await
}

async fn delete_armory(filename: heapless::String<64>) -> impl IntoResponse {
    service::delete_response(filename).await
}

async fn download_armory(filename: heapless::String<64>) -> impl IntoResponse {
    service::download_response(filename)
}

pub fn build<R: PathRouter>(router: Router<R, ()>) -> Router<impl PathRouter, ()> {
    router
        .route("/api/armory", get(list_armory))
        .route(
            (
                "/api/armory/upload",
                parse_path_segment::<heapless::String<64>>(),
            ),
            post_service(service::UploadArmory),
        )
        .route(
            ("/api/armory", parse_path_segment::<heapless::String<64>>()),
            get(download_armory).delete(delete_armory),
        )
}
