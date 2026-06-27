use super::service;
use picoserve::Router;
use picoserve::response::IntoResponse;
use picoserve::response::chunked::ChunkedResponse;
use picoserve::routing::{PathRouter, get};

async fn get_bootstrap() -> impl IntoResponse {
    ChunkedResponse::new(service::BootstrapChunks)
}

pub fn build<R: PathRouter>(router: Router<R, ()>) -> Router<impl PathRouter, ()> {
    router.route("/api/bootstrap", get(get_bootstrap))
}
