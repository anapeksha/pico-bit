use picoserve::Router;
use picoserve::response::chunked::{ChunkWriter, ChunkedResponse, Chunks, ChunksWritten};
use picoserve::response::{IntoResponse, StatusCode};
use picoserve::routing::{PathRouter, get};

static INDEX_HTML: &[u8] = include_bytes!("../../../dist/index.html");
static INDEX_JS: &[u8] = include_bytes!("../../../dist/assets/index.js");
static INDEX_CSS: &[u8] = include_bytes!("../../../dist/assets/index.css");

#[derive(Copy, Clone)]
struct CssAsset;
impl Chunks for CssAsset {
    fn content_type(&self) -> &'static str {
        "text/css"
    }

    async fn write_chunks<W: picoserve::io::Write>(
        self,
        mut writer: ChunkWriter<W>,
    ) -> Result<ChunksWritten, W::Error> {
        for chunk in INDEX_CSS.chunks(2048) {
            writer.write_chunk(chunk).await?;
        }
        writer.finalize().await
    }
}

#[derive(Copy, Clone)]
struct JsAsset;
impl Chunks for JsAsset {
    fn content_type(&self) -> &'static str {
        "application/javascript"
    }

    // FIX: Changed `&self` to `self`
    async fn write_chunks<W: picoserve::io::Write>(
        self,
        mut writer: ChunkWriter<W>,
    ) -> Result<ChunksWritten, W::Error> {
        for chunk in INDEX_JS.chunks(2048) {
            writer.write_chunk(chunk).await?;
        }
        writer.finalize().await
    }
}

#[derive(Copy, Clone)]
struct HtmlAsset;
impl Chunks for HtmlAsset {
    fn content_type(&self) -> &'static str {
        "text/html"
    }

    // FIX: Changed `&self` to `self`
    async fn write_chunks<W: picoserve::io::Write>(
        self,
        mut writer: ChunkWriter<W>,
    ) -> Result<ChunksWritten, W::Error> {
        for chunk in INDEX_HTML.chunks(1024) {
            writer.write_chunk(chunk).await?;
        }
        writer.finalize().await
    }
}

async fn stream_css() -> impl IntoResponse {
    ChunkedResponse::new(CssAsset)
        .into_response()
        .with_header("Content-Encoding", "gzip")
        .with_status_code(StatusCode::OK)
}

async fn stream_js() -> impl IntoResponse {
    ChunkedResponse::new(JsAsset)
        .into_response()
        .with_header("Content-Encoding", "gzip")
        .with_status_code(StatusCode::OK)
}

async fn stream_html() -> impl IntoResponse {
    ChunkedResponse::new(HtmlAsset)
        .into_response()
        .with_status_code(StatusCode::OK)
}

pub struct AppRouter;

impl AppRouter {
    pub fn build(&self) -> Router<impl PathRouter, ()> {
        Router::<_, ()>::new()
            .route("/assets/index.css", get(stream_css))
            .route("/assets/index.js", get(stream_js))
            .route("/", get(stream_html))
    }
}
