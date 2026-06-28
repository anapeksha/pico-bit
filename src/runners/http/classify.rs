#[derive(Clone, Copy)]
pub(super) enum StartupRequest {
    Root,
    Bootstrap,
    Armory,
    Payload,
    Runs,
    IgnoredBrowserProbe,
    OtherGet,
    Options,
    KeyboardTarget,
    Other,
}

pub(super) fn classify_startup_request(bytes: &[u8]) -> StartupRequest {
    if request_starts_with(bytes, b"GET / ") || request_starts_with(bytes, b"HEAD / ") {
        return StartupRequest::Root;
    }

    if request_starts_with(bytes, b"GET /api/bootstrap ") {
        return StartupRequest::Bootstrap;
    }

    if request_starts_with(bytes, b"GET /api/armory ") {
        return StartupRequest::Armory;
    }

    if request_starts_with(bytes, b"GET /api/payload ") {
        return StartupRequest::Payload;
    }

    if request_starts_with(bytes, b"GET /api/runs ") {
        return StartupRequest::Runs;
    }

    if request_starts_with(bytes, b"GET /favicon.ico ")
        || request_starts_with(bytes, b"GET /apple-touch-icon")
        || request_starts_with(bytes, b"GET /.well-known/")
        || request_starts_with(bytes, b"GET /manifest")
        || request_starts_with(bytes, b"GET /robots.txt ")
    {
        return StartupRequest::IgnoredBrowserProbe;
    }

    if is_get_or_head_request(bytes) {
        return StartupRequest::OtherGet;
    }

    if request_starts_with(bytes, b"OPTIONS ") {
        return StartupRequest::Options;
    }

    if request_starts_with(bytes, b"POST /api/keyboard/layout ") {
        return StartupRequest::KeyboardTarget;
    }

    StartupRequest::Other
}

pub(super) fn looks_like_http_request(bytes: &[u8]) -> bool {
    const METHODS: &[&[u8]] = &[
        b"GET ",
        b"POST ",
        b"PUT ",
        b"DELETE ",
        b"HEAD ",
        b"OPTIONS ",
        b"PATCH ",
    ];

    METHODS
        .iter()
        .any(|method| method.starts_with(bytes) || bytes.starts_with(method))
}

fn request_starts_with(bytes: &[u8], pattern: &[u8]) -> bool {
    pattern.starts_with(bytes) || bytes.starts_with(pattern)
}

fn is_get_or_head_request(bytes: &[u8]) -> bool {
    request_starts_with(bytes, b"GET ") || request_starts_with(bytes, b"HEAD ")
}
