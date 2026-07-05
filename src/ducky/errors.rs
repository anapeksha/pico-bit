use defmt::{Format, error};

/// Error category emitted by the DuckyScript parser or executor.
#[derive(Debug, Format, PartialEq, Clone)]
pub enum DuckyError {
    EmptyLine,
    UnknownCommand,
    InvalidKey,
    InvalidInteger,
    MissingArgument,
    TooManyKeys,
}

/// Line-oriented validation diagnostic for editor and run feedback.
#[derive(Debug, PartialEq, Clone)]
pub struct ErrorDiagnostic<'a> {
    pub line_number: usize,
    pub error: DuckyError,
    pub raw_line: &'a str,
}

impl<'a> ErrorDiagnostic<'a> {
    /// Creates a diagnostic with the original script line preserved.
    pub fn new(line_number: usize, error: DuckyError, raw_line: &'a str) -> Self {
        Self {
            line_number,
            error,
            raw_line,
        }
    }

    /// Emits the diagnostic through defmt for firmware-side debugging.
    pub fn log_diagnostic(&self) {
        error!(
            "DuckyScript Error on Line {}: {:?} -> \"{}\"",
            self.line_number, self.error, self.raw_line
        );
    }
}

#[cfg(test)]
mod tests {
    use super::{DuckyError, ErrorDiagnostic};

    #[test]
    fn diagnostic_preserves_line_error_and_raw_text() {
        let diagnostic = ErrorDiagnostic::new(7, DuckyError::InvalidKey, "CTRL NOT_A_KEY");

        assert_eq!(diagnostic.line_number, 7);
        assert_eq!(diagnostic.error, DuckyError::InvalidKey);
        assert_eq!(diagnostic.raw_line, "CTRL NOT_A_KEY");
    }
}
