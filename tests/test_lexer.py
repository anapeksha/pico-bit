from ducky import lex_script, tokenize_expression


def test_lex_script_applies_define_substitutions() -> None:
    lines = [
        line for line in lex_script('DEFINE GREETING Hello\nSTRING GREETING\n') if not line.is_blank
    ]

    assert len(lines) == 1
    assert lines[0].keyword == 'STRING'
    assert lines[0].argument == 'Hello'


def test_tokenize_expression_preserves_expected_tokens() -> None:
    tokens = tokenize_expression('($x + 1) && TRUE', 7)

    assert [token.value for token in tokens] == ['(', '$x', '+', '1', ')', '&&', 'TRUE']
