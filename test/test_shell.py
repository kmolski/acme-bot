import re

import pytest
from discord.ext import commands

from acme_bot.shell import validate_options, trim_double_newline, execute_system_cmd


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


async def test_execute_system_cmd_returns_output():
    result = await execute_system_cmd("echo", "foo")
    assert result == "foo\n"


async def test_concat_joins_arguments(mock_ctx, shell_module):
    assert await shell_module.concat(None, mock_ctx, False, 1) == "False1"
    assert mock_ctx.messages[0] == "```\nFalse1\n```"


async def test_ping_adds_reaction(mock_ctx, shell_module):
    assert await shell_module.ping(None, mock_ctx) >= "10"
    assert "\U0001f3d3" in mock_ctx.message.reactions


async def test_print_displays_the_content(mock_ctx, shell_module):
    assert await shell_module.print(None, mock_ctx, "foo", "python") == "foo"
    assert mock_ctx.messages[0] == "```python\nfoo\n```"


async def test_to_file_writes_the_file(mock_ctx, shell_module):
    assert await shell_module.to_file(None, mock_ctx, "foo", "filename") == "foo"
    assert "filename" in mock_ctx.messages[0]
    assert "foo" in mock_ctx.files[0].fp


async def test_open_returns_existing_file(mock_ctx_history, shell_module):
    expected = "Hello, world!�(��"
    assert await shell_module.open(None, mock_ctx_history, "stub_file") == expected
    assert mock_ctx_history.messages[0] == f"```\n{expected}\n```"


async def test_open_throws_with_nonexistent_file(mock_ctx, shell_module):
    with pytest.raises(commands.CommandError):
        await shell_module.open(None, mock_ctx, "stub_file")


async def test_tail_returns_the_last_lines(mock_ctx, shell_module):
    assert await shell_module.tail(None, mock_ctx, "foo\nbar\nbaz", 2) == "bar\nbaz"
    assert mock_ctx.messages[0] == "```\nbar\nbaz\n```"


async def test_tail_throws_with_zero(mock_ctx, shell_module):
    with pytest.raises(commands.CommandError):
        await shell_module.tail(None, mock_ctx, "foo\nbar\nbaz", 0)


async def test_head_returns_the_first_lines(mock_ctx, shell_module):
    assert await shell_module.head(None, mock_ctx, "foo\nbar\nbaz", 2) == "foo\nbar"
    assert mock_ctx.messages[0] == "```\nfoo\nbar\n```"


async def test_head_throws_with_zero(mock_ctx, shell_module):
    with pytest.raises(commands.CommandError):
        await shell_module.head(None, mock_ctx, "foo\nbar\nbaz", 0)


async def test_lines_returns_the_line_range(mock_ctx, shell_module):
    assert await shell_module.lines(None, mock_ctx, "foo\nbar\nbaz", 1, 2) == "foo\nbar"
    assert mock_ctx.messages[0] == "```\nfoo\nbar\n```"


async def test_lines_throws_with_negative_start(mock_ctx, shell_module):
    with pytest.raises(commands.CommandError):
        await shell_module.lines(shell_module, mock_ctx, "foo\nbar\nbaz", -10, 1)


async def test_lines_throws_when_start_is_greater_than_end(mock_ctx, shell_module):
    with pytest.raises(commands.CommandError):
        await shell_module.lines(shell_module, mock_ctx, "foo\nbar\nbaz", 2, 1)


async def test_count_returns_the_number_of_lines(mock_ctx, shell_module):
    assert await shell_module.count(None, mock_ctx, "foo\nbar\nbaz") == 3
    assert mock_ctx.messages[0] == "```\n3\n```"


async def test_enumerate_returns_the_numbered_lines(mock_ctx, shell_module):
    assert (
        await shell_module.enumerate(None, mock_ctx, "foo\nbar\nbaz")
        == "1  foo\n2  bar\n3  baz"
    )
    assert mock_ctx.messages[0] == "```\n1  foo\n2  bar\n3  baz\n```"


async def test_sort_returns_the_sorted_lines(mock_ctx, shell_module):
    assert await shell_module.sort(None, mock_ctx, "foo\nbar\nbaz") == "bar\nbaz\nfoo"
    assert mock_ctx.messages[0] == "```\nbar\nbaz\nfoo\n```"


async def test_unique_returns_the_unique_lines(mock_ctx, shell_module):
    assert await shell_module.unique(None, mock_ctx, "foo\nfoo\nfoo\nbar") == "foo\nbar"
    assert mock_ctx.messages[0] == "```\nfoo\nbar\n```"
