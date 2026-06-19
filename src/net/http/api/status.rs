use picoserve::Router;
use picoserve::response::{IntoResponse, Response, StatusCode};
use picoserve::routing::{PathRouter, get};

async fn get_status() -> impl IntoResponse {
    let json_body = "{\"status\":\"running\",\"uptime\":120}";
    Response::new(StatusCode::OK, json_body).with_header("Content-Type", "application/json")
}

pub fn build<R: PathRouter>(router: Router<R, ()>) -> Router<impl PathRouter, ()> {
    router.route("/api/status", get(get_status))
}
