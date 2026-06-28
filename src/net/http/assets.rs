use picoserve::Router;
use picoserve::io::Write;
use picoserve::response::chunked::{ChunkWriter, ChunkedResponse, Chunks, ChunksWritten};
use picoserve::response::{IntoResponse, StatusCode};
use picoserve::routing::{PathRouter, get};

static INDEX_HTML: &[u8] = include_bytes!("../../../dist/index.html.gz");

pub(crate) fn compressed_index_html() -> &'static [u8] {
    INDEX_HTML
}

#[derive(Copy, Clone)]
struct HtmlAsset;
impl Chunks for HtmlAsset {
    fn content_type(&self) -> &'static str {
        "text/html"
    }

    async fn write_chunks<W: Write>(
        self,
        mut writer: ChunkWriter<W>,
    ) -> Result<ChunksWritten, W::Error> {
        for chunk in INDEX_HTML.chunks(1024) {
            writer.write_chunk(chunk).await?;
        }
        writer.finalize().await
    }
}

async fn stream_html() -> impl IntoResponse {
    ChunkedResponse::new(HtmlAsset)
        .into_response()
        .with_header("Content-Encoding", "gzip")
        .with_header("Vary", "Accept-Encoding")
        .with_status_code(StatusCode::OK)
}

pub fn build<R: PathRouter>(router: Router<R, ()>) -> Router<impl PathRouter, ()> {
    router.route("/", get(stream_html))
}
