pub mod controller;
mod service;

/// Compact result shared by direct HTTP paths and the HID runner trigger flow.
pub(crate) struct PayloadActionResult {
    code: &'static str,
    success: bool,
    error_line: Option<usize>,
    message: &'static str,
}

impl PayloadActionResult {
    /// Compact machine-readable action result code.
    pub(crate) fn code(&self) -> &'static str {
        self.code
    }

    /// Whether validation/save/run preparation succeeded.
    pub(crate) fn success(&self) -> bool {
        self.success
    }

    /// Optional source line that failed validation.
    pub(crate) fn error_line(&self) -> Option<usize> {
        self.error_line
    }

    /// Short machine-facing action message.
    pub(crate) fn message(&self) -> &'static str {
        self.message
    }
}

/// Consumes the pending manual run flag.
pub(crate) fn consume_run_trigger() -> bool {
    service::consume_run_trigger()
}

/// Stages, validates, and writes payload code to `payload.dd`.
pub(crate) async fn save_code(code: &str) -> PayloadActionResult {
    service::stage(code);
    let response = service::save_staged().await;

    PayloadActionResult {
        code: response.code(),
        success: response.success(),
        error_line: response.error_line(),
        message: response.message().unwrap_or(if response.success() {
            "Payload updated successfully."
        } else {
            "Payload update failed."
        }),
    }
}

/// Validates `payload.dd` and requests execution by the HID runner.
pub(crate) async fn trigger_run() -> PayloadActionResult {
    let response = service::trigger_run().await;

    PayloadActionResult {
        code: response.code(),
        success: response.success(),
        error_line: response.error_line(),
        message: response.message(),
    }
}
