use crate::ducky::errors::DuckyError;
use crate::ducky::keyboard::{DuckyKeyboard, KeyboardLayout};
use crate::ducky::types::{AssignOp, BinaryOp, DuckyCommand, Expression};
use core::future::Future;
use usbd_hid::descriptor::KeyboardReport;

/// Fixed runtime constraint profiles for an embedded architecture.
const MAX_VARIABLES: usize = 16;
const MAX_STACK_DEPTH: usize = 4;

#[derive(Clone, Copy)]
struct Variable<'a> {
    name: &'a str,
    value: u32,
}

#[derive(Clone, Copy, PartialEq)]
enum ConditionalState {
    Executing,
    Bypassing,
    ConditionMet,
}

/// Bounded DuckyScript runtime for one payload execution.
///
/// The executor owns variable/control-flow state and converts parsed commands
/// into HID reports through a caller-provided writer.
pub struct DuckyExecutor<'a> {
    variables: [Option<Variable<'a>>; MAX_VARIABLES],
    if_stack: [Option<ConditionalState>; MAX_STACK_DEPTH],
    if_top: usize,
    loop_stack: [Option<usize>; MAX_STACK_DEPTH],
    loop_top: usize,
    default_delay: u32,
    keyboard_layout: KeyboardLayout,
}

impl<'a> DuckyExecutor<'a> {
    /// Creates an executor with empty state and US keyboard layout.
    pub fn new() -> Self {
        Self {
            variables: [None; MAX_VARIABLES],
            if_stack: [None; MAX_STACK_DEPTH],
            if_top: 0,
            loop_stack: [None; MAX_STACK_DEPTH],
            loop_top: 0,
            default_delay: 0,
            keyboard_layout: KeyboardLayout::Us,
        }
    }

    /// Sets the layout used when typing printable `STRING` characters.
    pub fn set_keyboard_layout(&mut self, layout: KeyboardLayout) {
        self.keyboard_layout = layout;
    }

    fn eval_expression(&self, expr: &Expression<'a>) -> Result<u32, DuckyError> {
        match expr {
            Expression::Literal(val) => Ok(*val),
            Expression::Variable(name) => self.get_variable(name),
            Expression::BinaryOperation { left, op, right } => {
                let l_val = self.resolve_operand(left)?;
                let r_val = self.resolve_operand(right)?;

                match op {
                    BinaryOp::Add => Ok(l_val + r_val),
                    BinaryOp::Sub => Ok(l_val - r_val),
                    BinaryOp::Mul => Ok(l_val * r_val),
                    BinaryOp::Div => l_val.checked_div(r_val).ok_or(DuckyError::InvalidInteger),
                    BinaryOp::Mod => l_val.checked_rem(r_val).ok_or(DuckyError::InvalidInteger),
                    BinaryOp::Equal => Ok(if l_val == r_val { 1 } else { 0 }),
                    BinaryOp::NotEqual => Ok(if l_val != r_val { 1 } else { 0 }),
                    BinaryOp::LessThan => Ok(if l_val < r_val { 1 } else { 0 }),
                    BinaryOp::LessThanOrEqual => Ok(if l_val <= r_val { 1 } else { 0 }),
                    BinaryOp::GreaterThan => Ok(if l_val > r_val { 1 } else { 0 }),
                    BinaryOp::GreaterThanOrEqual => Ok(if l_val >= r_val { 1 } else { 0 }),
                    BinaryOp::And => Ok(if l_val != 0 && r_val != 0 { 1 } else { 0 }),
                    BinaryOp::Or => Ok(if l_val != 0 || r_val != 0 { 1 } else { 0 }),
                }
            }
        }
    }

    fn resolve_operand(&self, item: &str) -> Result<u32, DuckyError> {
        if let Some(var_name) = item.strip_prefix('$') {
            self.get_variable(var_name)
        } else {
            item.parse::<u32>().map_err(|_| DuckyError::InvalidInteger)
        }
    }

    fn get_variable(&self, name: &str) -> Result<u32, DuckyError> {
        for var in self.variables.iter().flatten() {
            if var.name == name {
                return Ok(var.value);
            }
        }
        Err(DuckyError::UnknownCommand)
    }

    fn set_variable(&mut self, name: &'a str, value: u32, is_decl: bool) -> Result<(), DuckyError> {
        let mut found_idx = None;
        let mut empty_idx = None;

        for (idx, var) in self.variables.iter().enumerate() {
            if let Some(v) = var {
                if v.name == name {
                    found_idx = Some(idx);
                    break;
                }
            } else if empty_idx.is_none() {
                empty_idx = Some(idx);
            }
        }

        if let Some(idx) = found_idx {
            self.variables[idx].as_mut().unwrap().value = value;
            Ok(())
        } else if is_decl {
            if let Some(idx) = empty_idx {
                self.variables[idx] = Some(Variable { name, value });
                Ok(())
            } else {
                Err(DuckyError::TooManyKeys)
            }
        } else {
            Err(DuckyError::UnknownCommand)
        }
    }

    /// Executes one parsed command and returns an optional delay requested by it.
    pub async fn execute_command<W>(
        &mut self,
        command: DuckyCommand<'a>,
        line_num: usize,
        usb_writer: &mut W,
    ) -> Result<Option<u32>, DuckyError>
    where
        W: StatefulWriter,
    {
        let mut actively_skipping = false;
        if self.if_top > 0
            && let Some(state) = self.if_stack[self.if_top - 1]
            && state == ConditionalState::Bypassing
        {
            actively_skipping = true;
        }

        match &command {
            DuckyCommand::ElseIfBlock { .. } | DuckyCommand::ElseBlock | DuckyCommand::EndIf => {}
            DuckyCommand::EndWhile => {
                if self.loop_top > 0
                    && let Some(_start_line) = self.loop_stack[self.loop_top - 1]
                {}
                return Ok(None);
            }
            _ => {
                if actively_skipping {
                    return Ok(None);
                }
            }
        }

        match command {
            DuckyCommand::Comment => Ok(None),
            DuckyCommand::Delay(ms) => Ok(Some(ms)),
            DuckyCommand::DefaultDelay(ms) => {
                self.default_delay = ms;
                Ok(None)
            }

            DuckyCommand::String(text) => {
                for c in text.chars() {
                    let seq =
                        DuckyKeyboard::character_to_sequence_for_layout(c, self.keyboard_layout)?;
                    usb_writer.write_report(&seq.report).await;
                    usb_writer.delay_ms(10).await; // Character hold timing safety margin
                    usb_writer.clear_report().await;
                    usb_writer.delay_ms(10).await;
                }
                Ok(Some(self.default_delay))
            }

            DuckyCommand::KeySequence(seq) => {
                usb_writer.write_report(&seq.report).await;
                usb_writer.delay_ms(20).await;
                usb_writer.clear_report().await;
                Ok(Some(self.default_delay))
            }

            DuckyCommand::VariableAssign {
                name,
                operator,
                expression,
                is_declaration,
            } => {
                let current = if is_declaration {
                    0
                } else {
                    self.get_variable(name)?
                };
                let delta = self.eval_expression(&expression)?;

                let result = match operator {
                    AssignOp::Equal => delta,
                    AssignOp::AddEqual => current + delta,
                    AssignOp::SubEqual => current - delta,
                    AssignOp::MulEqual => current * delta,
                    AssignOp::DivEqual => current / delta,
                    _ => delta, // Extend bitwise variations here as needed
                };

                self.set_variable(name, result, is_declaration)?;
                Ok(None)
            }

            DuckyCommand::IfBlock { condition } => {
                if self.if_top >= MAX_STACK_DEPTH {
                    return Err(DuckyError::TooManyKeys);
                }

                // If a parent block is already bypassing, nested blocks must bypass too
                let parent_skipping = self.if_top > 0
                    && matches!(
                        self.if_stack[self.if_top - 1],
                        Some(ConditionalState::Bypassing)
                    );

                let state = if parent_skipping {
                    ConditionalState::Bypassing
                } else {
                    let result = self.eval_expression(&condition)? != 0;
                    if result {
                        ConditionalState::Executing
                    } else {
                        ConditionalState::Bypassing
                    }
                };

                self.if_stack[self.if_top] = Some(state);
                self.if_top += 1;
                Ok(None)
            }

            DuckyCommand::ElseIfBlock { condition } => {
                if self.if_top == 0 {
                    return Err(DuckyError::UnknownCommand);
                }
                let current_state = self.if_stack[self.if_top - 1].unwrap();

                match current_state {
                    // 1. A previous branch ran successfully, so we mark it as ConditionMet and skip this one
                    ConditionalState::Executing => {
                        self.if_stack[self.if_top - 1] = Some(ConditionalState::ConditionMet);
                    }
                    // 2. A previous branch failed, so we evaluate this ELSEIF condition
                    ConditionalState::Bypassing => {
                        let result = self.eval_expression(&condition)? != 0;
                        if result {
                            self.if_stack[self.if_top - 1] = Some(ConditionalState::Executing);
                        }
                    }
                    // 3. A branch prior to this was already executed, keep skipping
                    ConditionalState::ConditionMet => {}
                }
                Ok(None)
            }

            DuckyCommand::ElseBlock => {
                if self.if_top == 0 {
                    return Err(DuckyError::UnknownCommand);
                }
                let current_state = self.if_stack[self.if_top - 1].unwrap();

                match current_state {
                    // Only execute the ELSE block if the previous branches were completely bypassed
                    ConditionalState::Bypassing => {
                        self.if_stack[self.if_top - 1] = Some(ConditionalState::Executing);
                    }
                    // If an IF or ELSEIF already ran (Executing or ConditionMet), bypass the ELSE
                    _ => {
                        self.if_stack[self.if_top - 1] = Some(ConditionalState::Bypassing);
                    }
                }
                Ok(None)
            }

            DuckyCommand::EndIf => {
                if self.if_top == 0 {
                    return Err(DuckyError::UnknownCommand);
                }
                self.if_top -= 1;
                self.if_stack[self.if_top] = None;
                Ok(None)
            }

            DuckyCommand::WhileLoop { condition } => {
                if self.loop_top >= MAX_STACK_DEPTH {
                    return Err(DuckyError::TooManyKeys);
                }
                let result = self.eval_expression(&condition)? != 0;

                if result {
                    self.loop_stack[self.loop_top] = Some(line_num);
                    self.loop_top += 1;
                }
                Ok(None)
            }

            _ => Err(DuckyError::UnknownCommand),
        }
    }
}

impl<'a> Default for DuckyExecutor<'a> {
    fn default() -> Self {
        Self::new()
    }
}

/// Minimal async HID writer interface required by the executor.
pub trait StatefulWriter {
    /// Sends a non-empty keyboard report.
    fn write_report<'a>(&'a mut self, report: &'a KeyboardReport) -> impl Future<Output = ()> + 'a;
    /// Releases all pressed keys.
    fn clear_report(&mut self) -> impl Future<Output = ()> + '_;
    /// Waits for host-visible key timing.
    fn delay_ms(&mut self, ms: u32) -> impl Future<Output = ()> + '_;
}

#[cfg(test)]
mod tests {
    extern crate std;

    use super::{DuckyExecutor, StatefulWriter};
    use crate::ducky::errors::DuckyError;
    use crate::ducky::types::{AssignOp, BinaryOp, DuckyCommand, Expression};
    use core::future::Future;
    use core::pin::Pin;
    use core::task::{Context, Poll, RawWaker, RawWakerVTable, Waker};
    use std::vec::Vec;
    use usbd_hid::descriptor::KeyboardReport;

    #[derive(Default)]
    struct TestWriter {
        reports: Vec<KeyboardReport>,
        clear_count: usize,
        delays: Vec<u32>,
    }

    impl StatefulWriter for TestWriter {
        async fn write_report(&mut self, report: &KeyboardReport) {
            self.reports.push(*report);
        }

        async fn clear_report(&mut self) {
            self.clear_count += 1;
        }

        async fn delay_ms(&mut self, ms: u32) {
            self.delays.push(ms);
        }
    }

    fn block_on<F: Future>(future: F) -> F::Output {
        fn raw_waker() -> RawWaker {
            fn clone(_: *const ()) -> RawWaker {
                raw_waker()
            }
            fn noop(_: *const ()) {}

            RawWaker::new(
                core::ptr::null(),
                &RawWakerVTable::new(clone, noop, noop, noop),
            )
        }

        let waker = unsafe { Waker::from_raw(raw_waker()) };
        let mut context = Context::from_waker(&waker);
        let mut future = core::pin::pin!(future);

        loop {
            match Future::poll(Pin::as_mut(&mut future), &mut context) {
                Poll::Ready(value) => return value,
                Poll::Pending => {}
            }
        }
    }

    #[test]
    fn delay_and_default_delay_return_expected_waits() {
        let mut executor = DuckyExecutor::new();
        let mut writer = TestWriter::default();

        assert_eq!(
            block_on(executor.execute_command(DuckyCommand::DefaultDelay(15), 1, &mut writer)),
            Ok(None)
        );
        assert_eq!(
            block_on(executor.execute_command(DuckyCommand::Delay(50), 2, &mut writer)),
            Ok(Some(50))
        );
    }

    #[test]
    fn string_command_writes_and_clears_each_character() {
        let mut executor = DuckyExecutor::new();
        let mut writer = TestWriter::default();

        assert_eq!(
            block_on(executor.execute_command(DuckyCommand::String("Aa"), 1, &mut writer)),
            Ok(Some(0))
        );

        assert_eq!(writer.reports.len(), 2);
        assert_eq!(writer.clear_count, 2);
        assert_eq!(writer.delays, [10, 10, 10, 10]);
        assert_ne!(writer.reports[0].modifier, writer.reports[1].modifier);
    }

    #[test]
    fn variables_can_be_declared_and_reused() {
        let mut executor = DuckyExecutor::new();
        let mut writer = TestWriter::default();

        assert_eq!(
            block_on(executor.execute_command(
                DuckyCommand::VariableAssign {
                    name: "count",
                    operator: AssignOp::Equal,
                    expression: Expression::Literal(4),
                    is_declaration: true,
                },
                1,
                &mut writer,
            )),
            Ok(None)
        );
        assert_eq!(
            block_on(executor.execute_command(
                DuckyCommand::VariableAssign {
                    name: "count",
                    operator: AssignOp::AddEqual,
                    expression: Expression::Literal(2),
                    is_declaration: false,
                },
                2,
                &mut writer,
            )),
            Ok(None)
        );
        assert_eq!(
            block_on(executor.execute_command(
                DuckyCommand::IfBlock {
                    condition: Expression::BinaryOperation {
                        left: "$count",
                        op: BinaryOp::Equal,
                        right: "6",
                    },
                },
                3,
                &mut writer,
            )),
            Ok(None)
        );
    }

    #[test]
    fn assigning_undeclared_variable_fails() {
        let mut executor = DuckyExecutor::new();
        let mut writer = TestWriter::default();

        assert_eq!(
            block_on(executor.execute_command(
                DuckyCommand::VariableAssign {
                    name: "missing",
                    operator: AssignOp::Equal,
                    expression: Expression::Literal(1),
                    is_declaration: false,
                },
                1,
                &mut writer,
            )),
            Err(DuckyError::UnknownCommand)
        );
    }
}
