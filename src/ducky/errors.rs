use defmt::{Format, error};

#[derive(Debug, Format, PartialEq, Clone)]
pub enum DuckyError {
    EmptyLine,
    UnknownCommand,
    InvalidKey,
    InvalidInteger,
    MissingArgument,
    TooManyKeys,
}

#[derive(Debug, PartialEq, Clone)]
pub struct ErrorDiagnostic<'a> {
    pub line_number: usize,
    pub error: DuckyError,
    pub raw_line: &'a str,
}

impl<'a> ErrorDiagnostic<'a> {
    pub fn new(line_number: usize, error: DuckyError, raw_line: &'a str) -> Self {
        Self {
            line_number,
            error,
            raw_line,
        }
    }

    pub fn log_diagnostic(&self) {
        error!(
            "DuckyScript Error on Line {}: {:?} -> \"{}\"",
            self.line_number, self.error, self.raw_line
        );
    }
}
