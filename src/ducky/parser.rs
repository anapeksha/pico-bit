use crate::ducky::errors::DuckyError;
use crate::ducky::keyboard::{DuckyKeyboard, KeyboardOs};
use crate::ducky::types::{AssignOp, BinaryOp, DuckyCommand, Expression};

/// Line-oriented DuckyScript parser used by validation and runtime execution.
pub struct DuckyParser;

impl DuckyParser {
    /// Parses a single DuckyScript line for the active host operating system.
    ///
    /// Printable text is handled later by the executor using the selected
    /// keyboard layout. This parser-level OS is used for key-chord aliases such
    /// as `COMMAND`, `OPTION`, and `WINDOWS`.
    pub fn parse_line_for_os(line: &str, os: KeyboardOs) -> Result<DuckyCommand<'_>, DuckyError> {
        let trimmed = line.trim();

        if trimmed.is_empty() {
            return Err(DuckyError::EmptyLine);
        }

        if trimmed.starts_with("REM") || trimmed.starts_with("//") {
            return Ok(DuckyCommand::Comment);
        }

        match trimmed {
            "END_IF" => return Ok(DuckyCommand::EndIf),
            "END_WHILE" => return Ok(DuckyCommand::EndWhile),
            "END_FUNCTION" => return Ok(DuckyCommand::EndFunction),
            "ELSE" => return Ok(DuckyCommand::ElseBlock),
            _ => {}
        }

        if trimmed.starts_with("$") || trimmed.starts_with("VAR ") {
            return Self::parse_assignment(trimmed);
        }

        let (token, args) = match trimmed.split_once(char::is_whitespace) {
            Some((tok, rest)) => (tok, Some(rest.trim())),
            None => (trimmed, None),
        };

        match token {
            "DELAY" => {
                let expr_str = args.ok_or(DuckyError::MissingArgument)?;
                let ms = expr_str
                    .parse::<u32>()
                    .map_err(|_| DuckyError::InvalidInteger)?;
                Ok(DuckyCommand::Delay(ms))
            }

            "DEFAULTDELAY" | "DEFAULT_DELAY" => {
                let expr_str = args.ok_or(DuckyError::MissingArgument)?;
                let ms = expr_str
                    .parse::<u32>()
                    .map_err(|_| DuckyError::InvalidInteger)?;
                Ok(DuckyCommand::DefaultDelay(ms))
            }

            "STRING" => {
                let text = args.ok_or(DuckyError::MissingArgument)?;
                Ok(DuckyCommand::String(text))
            }

            "IF" => {
                let cond_str = args.ok_or(DuckyError::MissingArgument)?;
                let condition = Self::parse_expression(cond_str)?;
                Ok(DuckyCommand::IfBlock { condition })
            }

            "ELSEIF" | "ELSE_IF" => {
                let cond_str = args.ok_or(DuckyError::MissingArgument)?;
                let condition = Self::parse_expression(cond_str)?;
                Ok(DuckyCommand::ElseIfBlock { condition })
            }

            "WHILE" => {
                let cond_str = args.ok_or(DuckyError::MissingArgument)?;
                let condition = Self::parse_expression(cond_str)?;
                Ok(DuckyCommand::WhileLoop { condition })
            }

            "FUNCTION" => {
                let func_signature = args.ok_or(DuckyError::MissingArgument)?;
                let name = func_signature
                    .trim_end_matches('(')
                    .trim_end_matches(')')
                    .trim();
                Ok(DuckyCommand::FunctionDef { name })
            }

            "RETURN" => {
                let expression = match args {
                    Some(expr_str) => Some(Self::parse_expression(expr_str)?),
                    None => None,
                };
                Ok(DuckyCommand::Return { expression })
            }

            "REPEAT" => {
                let expr_str = args.ok_or(DuckyError::MissingArgument)?;
                let expression = Self::parse_expression(expr_str)?;
                Ok(DuckyCommand::Repeat { expression })
            }

            "HOLD" => {
                let combo = args.ok_or(DuckyError::MissingArgument)?;
                Ok(DuckyCommand::Hold { combo })
            }

            "RELEASE" => {
                let combo = args.ok_or(DuckyError::MissingArgument)?;
                Ok(DuckyCommand::Release { combo })
            }

            _ => {
                if trimmed.ends_with("()") {
                    let name = trimmed.trim_end_matches('(').trim_end_matches(')').trim();
                    Ok(DuckyCommand::FunctionCall { name })
                } else {
                    let sequence = DuckyKeyboard::parse_token_sequence_for_os(trimmed, os)?;
                    Ok(DuckyCommand::KeySequence(sequence))
                }
            }
        }
    }

    fn parse_expression(expr_str: &str) -> Result<Expression<'_>, DuckyError> {
        let trimmed = expr_str.trim().trim_matches('(').trim_matches(')');

        let ops = [
            ("==", BinaryOp::Equal),
            ("!=", BinaryOp::NotEqual),
            ("<=", BinaryOp::LessThanOrEqual),
            (">=", BinaryOp::GreaterThanOrEqual),
            ("<", BinaryOp::LessThan),
            (">", BinaryOp::GreaterThan),
            ("+", BinaryOp::Add),
            ("-", BinaryOp::Sub),
            ("*", BinaryOp::Mul),
            ("/", BinaryOp::Div),
            ("%", BinaryOp::Mod),
            ("&&", BinaryOp::And),
            ("||", BinaryOp::Or),
        ];

        for (op_str, op_variant) in ops.iter() {
            if let Some((left, right)) = trimmed.split_once(op_str) {
                return Ok(Expression::BinaryOperation {
                    left: left.trim(),
                    op: op_variant.clone(),
                    right: right.trim(),
                });
            }
        }

        if let Some(var_name) = trimmed.strip_prefix('$') {
            Ok(Expression::Variable(var_name))
        } else if let Ok(val) = trimmed.parse::<u32>() {
            Ok(Expression::Literal(val))
        } else {
            Err(DuckyError::InvalidInteger)
        }
    }

    fn parse_assignment(statement: &str) -> Result<DuckyCommand<'_>, DuckyError> {
        let mut is_declaration = false;
        let mut target = statement;

        if let Some(stripped) = statement.strip_prefix("VAR ") {
            is_declaration = true;
            target = stripped.trim();
        }

        let operators = [
            ("<<=", AssignOp::ShiftLeftEqual),
            (">>=", AssignOp::ShiftRightEqual),
            ("+=", AssignOp::AddEqual),
            ("-=", AssignOp::SubEqual),
            ("*=", AssignOp::MulEqual),
            ("/=", AssignOp::DivEqual),
            ("%=", AssignOp::ModEqual),
            ("&=", AssignOp::BitAndEqual),
            ("|=", AssignOp::BitOrEqual),
            ("^=", AssignOp::BitXorEqual),
            ("=", AssignOp::Equal),
        ];

        for (op_str, op_variant) in operators.iter() {
            if let Some((name, expr_str)) = target.split_once(op_str) {
                let clean_name = name.trim();
                if !clean_name.starts_with('$') {
                    return Err(DuckyError::UnknownCommand);
                }

                let expression = Self::parse_expression(expr_str)?;

                return Ok(DuckyCommand::VariableAssign {
                    name: &clean_name[1..],
                    operator: op_variant.clone(),
                    expression,
                    is_declaration,
                });
            }
        }

        Err(DuckyError::UnknownCommand)
    }
}

#[cfg(test)]
mod tests {
    use super::DuckyParser;
    use crate::ducky::errors::DuckyError;
    use crate::ducky::keyboard::KeyboardOs;
    use crate::ducky::types::{AssignOp, BinaryOp, DuckyCommand, Expression, modifiers};

    #[test]
    fn parses_comments_and_empty_lines() {
        assert_eq!(
            DuckyParser::parse_line_for_os("REM note", KeyboardOs::Windows),
            Ok(DuckyCommand::Comment)
        );
        assert_eq!(
            DuckyParser::parse_line_for_os("// note", KeyboardOs::Windows),
            Ok(DuckyCommand::Comment)
        );
        assert_eq!(
            DuckyParser::parse_line_for_os("   ", KeyboardOs::Windows),
            Err(DuckyError::EmptyLine)
        );
    }

    #[test]
    fn parses_delays_strings_and_control_blocks() {
        assert_eq!(
            DuckyParser::parse_line_for_os("DELAY 250", KeyboardOs::Windows),
            Ok(DuckyCommand::Delay(250))
        );
        assert_eq!(
            DuckyParser::parse_line_for_os("DEFAULT_DELAY 20", KeyboardOs::Windows),
            Ok(DuckyCommand::DefaultDelay(20))
        );
        assert_eq!(
            DuckyParser::parse_line_for_os("STRING hello world", KeyboardOs::Windows),
            Ok(DuckyCommand::String("hello world"))
        );
        assert_eq!(
            DuckyParser::parse_line_for_os("IF $ready == 1", KeyboardOs::Windows),
            Ok(DuckyCommand::IfBlock {
                condition: Expression::BinaryOperation {
                    left: "$ready",
                    op: BinaryOp::Equal,
                    right: "1",
                },
            })
        );
        assert_eq!(
            DuckyParser::parse_line_for_os("ELSE", KeyboardOs::Windows),
            Ok(DuckyCommand::ElseBlock)
        );
        assert_eq!(
            DuckyParser::parse_line_for_os("END_IF", KeyboardOs::Windows),
            Ok(DuckyCommand::EndIf)
        );
    }

    #[test]
    fn parses_variable_assignments_and_rejects_invalid_assignments() {
        assert_eq!(
            DuckyParser::parse_line_for_os("VAR $count = 3", KeyboardOs::Windows),
            Ok(DuckyCommand::VariableAssign {
                name: "count",
                operator: AssignOp::Equal,
                expression: Expression::Literal(3),
                is_declaration: true,
            })
        );
        assert_eq!(
            DuckyParser::parse_line_for_os("$count += 2", KeyboardOs::Windows),
            Ok(DuckyCommand::VariableAssign {
                name: "count",
                operator: AssignOp::AddEqual,
                expression: Expression::Literal(2),
                is_declaration: false,
            })
        );
        assert_eq!(
            DuckyParser::parse_line_for_os("VAR count = 1", KeyboardOs::Windows),
            Err(DuckyError::UnknownCommand)
        );
    }

    #[test]
    fn parses_key_sequences_as_fallback() {
        let command =
            DuckyParser::parse_line_for_os("CTRL ALT DELETE", KeyboardOs::Windows).unwrap();
        let DuckyCommand::KeySequence(sequence) = command else {
            panic!("expected key sequence");
        };

        assert_eq!(
            sequence.report.modifier,
            modifiers::LEFT_CTRL | modifiers::LEFT_ALT
        );
        assert_eq!(sequence.report.keycodes[0], 0x4C);
    }

    #[test]
    fn parses_key_sequences_for_selected_os() {
        let command = DuckyParser::parse_line_for_os("COMMAND SPACE", KeyboardOs::MacOs).unwrap();
        let DuckyCommand::KeySequence(sequence) = command else {
            panic!("expected key sequence");
        };

        assert_eq!(sequence.report.modifier, modifiers::LEFT_GUI);
        assert_eq!(sequence.report.keycodes[0], 0x2C);
    }
}
