use defmt::{Format, Formatter, write};
use usbd_hid::descriptor::KeyboardReport;

/// Parsed DuckyScript command with borrowed script text where possible.
#[derive(Debug, PartialEq, Clone, Format)]
pub enum DuckyCommand<'a> {
    Comment,
    Delay(u32),
    DefaultDelay(u32),
    String(&'a str),

    WhileLoop {
        condition: Expression<'a>,
    },

    IfBlock {
        condition: Expression<'a>,
    },
    ElseIfBlock {
        condition: Expression<'a>,
    },
    ElseBlock,

    EndIf,
    EndWhile,

    FunctionDef {
        name: &'a str,
    },
    EndFunction,

    FunctionCall {
        name: &'a str,
    },

    Repeat {
        expression: Expression<'a>,
    },

    Return {
        expression: Option<Expression<'a>>,
    },

    VariableAssign {
        name: &'a str,
        operator: AssignOp,
        expression: Expression<'a>,
        is_declaration: bool,
    },

    Hold {
        combo: &'a str,
    },
    Release {
        combo: &'a str,
    },

    KeySequence(KeySequence),
}

/// Numeric expression used by variables and control-flow conditions.
#[derive(Debug, PartialEq, Clone, Format)]
pub enum Expression<'a> {
    Literal(u32),
    Variable(&'a str),
    BinaryOperation {
        left: &'a str,
        op: BinaryOp,
        right: &'a str,
    },
}

/// Binary operators supported by the embedded expression evaluator.
#[derive(Debug, PartialEq, Clone, Format)]
pub enum BinaryOp {
    Add,
    Sub,
    Mul,
    Div,
    Mod,
    Equal,
    NotEqual,
    LessThan,
    LessThanOrEqual,
    GreaterThan,
    GreaterThanOrEqual,
    And,
    Or,
}

/// Assignment operators supported by variable statements.
#[derive(Debug, PartialEq, Clone, Format)]
pub enum AssignOp {
    Equal,
    AddEqual,
    SubEqual,
    MulEqual,
    DivEqual,
    ModEqual,
    BitAndEqual,
    BitOrEqual,
    BitXorEqual,
    ShiftLeftEqual,
    ShiftRightEqual,
}

/// USB keyboard report wrapper produced by key sequence parsing.
#[derive(Debug, PartialEq, Clone)]
pub struct KeySequence {
    /// HID boot-keyboard report ready to send through `usbd-hid`.
    pub report: KeyboardReport,
}

impl Default for KeySequence {
    fn default() -> Self {
        Self {
            report: KeyboardReport {
                modifier: 0,
                reserved: 0,
                leds: 0,
                keycodes: [0; 6],
            },
        }
    }
}

impl Format for KeySequence {
    fn format(&self, fmt: Formatter) {
        write!(
            fmt,
            "KeySequence {{ modified: {=u8:X}, keycodes: {=[u8; 6]:X} }}",
            self.report.modifier, self.report.keycodes
        )
    }
}

#[allow(dead_code)]
/// HID modifier bit masks used by generated keyboard reports.
pub mod modifiers {
    pub const NONE: u8 = 0x00;
    pub const LEFT_CTRL: u8 = 0x01;
    pub const LEFT_SHIFT: u8 = 0x02;
    pub const LEFT_ALT: u8 = 0x04;
    pub const LEFT_GUI: u8 = 0x08;
    pub const RIGHT_CTRL: u8 = 0x10;
    pub const RIGHT_SHIFT: u8 = 0x20;
    pub const RIGHT_ALT: u8 = 0x40;
    pub const RIGHT_GUI: u8 = 0x80;
}
