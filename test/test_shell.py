import re

import pytest
from discord.ext import commands

from acme_bot.shell import validate_options, trim_double_newline


def test_validate_options_passes_on_valid_opt():
    regex = re.compile(r"-[ABC]+")
    validate_options(["-ABC"], regex)


def test_validate_options_throws_on_invalid_opt():
    regex = re.compile(r"-[ABC]+")
    with pytest.raises(commands.CommandError):
        validate_options(["-DEF"], regex)


def test_trim_double_newline_with_single_newline():
    string = "foo\n"
    assert trim_double_newline(string) == string


def test_trim_double_newline_with_double_newline():
    assert trim_double_newline("foo\n\n") == "foo\n"


async def test_concat_joins_arguments(fake_ctx, shell_module):
    assert await shell_module.concat(None, fake_ctx, False, 1) == "False1"
    assert fake_ctx.messages[0] == "```\nFalse1\n```"


async def test_ping_adds_reaction(fake_ctx, shell_module):
    assert await shell_module.ping(None, fake_ctx) >= "10"
    assert "\U0001F3D3" in fake_ctx.message.reactions


async def test_print_displays_the_content(fake_ctx, shell_module):
    assert await shell_module.print(None, fake_ctx, "foo", "python") == "foo"
    assert fake_ctx.messages[0] == "```python\nfoo\n```"


async def test_to_file_writes_the_file(fake_ctx, shell_module):
    assert await shell_module.to_file(None, fake_ctx, "foo", "filename") == "foo"
    assert "filename" in fake_ctx.messages[0]
    assert "foo" in fake_ctx.files[0].fp


async def test_tail_returns_the_last_lines(fake_ctx, shell_module):
    assert await shell_module.tail(None, fake_ctx, "foo\nbar\nbaz", 2) == "bar\nbaz"
    assert fake_ctx.messages[0] == "```\nbar\nbaz\n```"


async def test_tail_throws_with_zero(fake_ctx, shell_module):
    with pytest.raises(commands.CommandError):
        await shell_module.tail(None, fake_ctx, "foo\nbar\nbaz", 0)


async def test_head_returns_the_first_lines(fake_ctx, shell_module):
    assert await shell_module.head(None, fake_ctx, "foo\nbar\nbaz", 2) == "foo\nbar"
    assert fake_ctx.messages[0] == "```\nfoo\nbar\n```"


async def test_head_throws_with_zero(fake_ctx, shell_module):
    with pytest.raises(commands.CommandError):
        await shell_module.head(None, fake_ctx, "foo\nbar\nbaz", 0)


async def test_lines_returns_the_line_range(fake_ctx, shell_module):
    assert await shell_module.lines(None, fake_ctx, "foo\nbar\nbaz", 1, 2) == "foo\nbar"
    assert fake_ctx.messages[0] == "```\nfoo\nbar\n```"


async def test_lines_throws_with_negative_start(fake_ctx, shell_module):
    with pytest.raises(commands.CommandError):
        await shell_module.lines(shell_module, fake_ctx, "foo\nbar\nbaz", -10, 1)


async def test_lines_throws_when_start_is_greater_than_end(fake_ctx, shell_module):
    with pytest.raises(commands.CommandError):
        await shell_module.lines(shell_module, fake_ctx, "foo\nbar\nbaz", 2, 1)


async def test_count_returns_the_number_of_lines(fake_ctx, shell_module):
    assert await shell_module.count(None, fake_ctx, "foo\nbar\nbaz") == 3
    assert fake_ctx.messages[0] == "```\n3\n```"


async def test_enumerate_returns_the_numbered_lines(fake_ctx, shell_module):
    assert (
        await shell_module.enumerate(None, fake_ctx, "foo\nbar\nbaz")
        == "1  foo\n2  bar\n3  baz"
    )
    assert fake_ctx.messages[0] == "```\n1  foo\n2  bar\n3  baz\n```"


async def test_sort_returns_the_sorted_lines(fake_ctx, shell_module):
    assert await shell_module.sort(None, fake_ctx, "foo\nbar\nbaz") == "bar\nbaz\nfoo"
    assert fake_ctx.messages[0] == "```\nbar\nbaz\nfoo\n```"


async def test_unique_returns_the_unique_lines(fake_ctx, shell_module):
    assert await shell_module.unique(None, fake_ctx, "foo\nfoo\nfoo\nbar") == "foo\nbar"
    assert fake_ctx.messages[0] == "```\nfoo\nbar\n```"
