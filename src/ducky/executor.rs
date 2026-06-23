// src/ducky/executor.rs

use crate::ducky::errors::DuckyError;
use crate::ducky::keyboard::DuckyKeyboard;
use crate::ducky::types::{AssignOp, BinaryOp, DuckyCommand, Expression};
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

pub struct DuckyExecutor<'a> {
    variables: [Option<Variable<'a>>; MAX_VARIABLES],
    if_stack: [Option<ConditionalState>; MAX_STACK_DEPTH],
    if_top: usize,
    loop_stack: [Option<usize>; MAX_STACK_DEPTH],
    loop_top: usize,
    default_delay: u32,
}

impl<'a> DuckyExecutor<'a> {
    pub fn new() -> Self {
        Self {
            variables: [None; MAX_VARIABLES],
            if_stack: [None; MAX_STACK_DEPTH],
            if_top: 0,
            loop_stack: [None; MAX_STACK_DEPTH],
            loop_top: 0,
            default_delay: 0,
        }
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
                    let seq = DuckyKeyboard::character_to_sequence(c)?;
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

/// Abstract implementation interface connecting to Embassy's hardware USB HID classes safely.
pub trait StatefulWriter {
    async fn write_report(&mut self, report: &KeyboardReport);
    async fn clear_report(&mut self);
    async fn delay_ms(&mut self, ms: u32);
}
