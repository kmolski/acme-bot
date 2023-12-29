import pytest

from acme_bot.shell.interpreter import (
    META_MODEL,
    ExprSeq,
    ExprComp,
    Command,
    StrLiteral,
    IntLiteral,
    BoolLiteral,
    ExprSubst,
    FileContent,
)


def single_command(command):
    return ExprSeq(expr_comps=[ExprComp(exprs=[command])])


def test_parse_simple_command():
    expected = single_command(
        Command(
            name="echo",
            args=[StrLiteral(None, value=s) for s in ["hello", "world"]],
        )
    )
    assert META_MODEL.model_from_str("echo hello world") == expected


def test_parse_file_substitution():
    expected = single_command(
        Command(
            name="echo",
            args=[
                IntLiteral(None, value=1),
                BoolLiteral(None, value="False"),
                ExprSubst(
                    None,
                    expr_seq=single_command(
                        Command(name="open", args=[StrLiteral(None, "bar.txt")])
                    ),
                ),
                FileContent(None, name="foo.txt"),
            ],
        )
    )
    assert META_MODEL.model_from_str("echo 1 no (open bar.txt) [foo.txt]") == expected


async def test_expr_seq_eval_joins_output(fake_ctx):
    ast = ExprSeq(
        expr_comps=[IntLiteral(None, value=1), BoolLiteral(None, value="False")]
    )
    assert await ast.eval(fake_ctx) == "1False"


async def test_expr_comp_returns_last_expr(fake_ctx):
    ast = ExprComp(exprs=[IntLiteral(None, value=1), StrLiteral(None, value="hello")])
    assert await ast.eval(fake_ctx) == "hello"


async def test_expr_comp_propagates_exceptions(fake_ctx):
    ast = ExprComp(exprs=[IntLiteral(None, value=1), Command(name="echo", args=[])])
    with pytest.raises(Exception):
        await ast.eval(fake_ctx)


async def test_expr_subst_evals_subexpr(fake_ctx):
    ast = ExprSubst(parent=None, expr_seq=IntLiteral(None, value=1))
    assert await ast.eval(fake_ctx) == 1
