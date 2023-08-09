from acme_bot.shell.interpreter import (
    META_MODEL,
    ExprSeq,
    ExprComp,
    Command,
    StrLiteral,
)


def test_parse_simple_command():
    expected = ExprSeq(
        expr_comps=[
            ExprComp(
                exprs=[
                    Command(
                        name="echo",
                        args=[StrLiteral(None, value=s) for s in ["hello", "world"]],
                    ),
                ],
            ),
        ],
    )
    assert META_MODEL.model_from_str("echo hello world") == expected
