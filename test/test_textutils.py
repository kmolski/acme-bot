from discord.ui import View

from acme_bot.textutils import (
    escape_md_block,
    format_duration,
    send_pages,
    MAX_MESSAGE_LENGTH,
)


async def test_send_pages_short_msgs_are_unchanged(fake_ctx):
    short = "too short to split"

    await send_pages(fake_ctx, short)
    assert fake_ctx.messages == [short]


async def test_send_pages_long_lines_are_split_to_multiple_messages(fake_ctx):
    long_line = "much much longer " * 200

    await send_pages(fake_ctx, long_line)
    assert len(fake_ctx.messages) == 2
    assert all(len(msg) <= MAX_MESSAGE_LENGTH for msg in fake_ctx.messages)


async def test_send_pages_long_multiline_split_into_multiple_messages(fake_ctx):
    long = "much much longer\n" * 200

    await send_pages(fake_ctx, long)
    assert len(fake_ctx.messages) == 2
    assert all(len(msg) <= MAX_MESSAGE_LENGTH for msg in fake_ctx.messages)


async def test_send_pages_preserves_empty_lines(fake_ctx):
    with_empty = "foobar\n\n" * 4

    await send_pages(fake_ctx, with_empty)
    assert fake_ctx.messages == [with_empty.rstrip()]


async def test_send_pages_accepts_format_string(fake_ctx):
    content = "sample text"
    fmt = "```\n{}\n```"

    await send_pages(fake_ctx, content, fmt=fmt)
    assert fake_ctx.messages[0] == fmt.format(content)
    assert "```" in fake_ctx.messages[0]


async def test_send_pages_sends_view_in_last_chunk(fake_ctx):
    long = "much much longer\n" * 400
    view = View()

    await send_pages(fake_ctx, long, view=view)
    assert fake_ctx.views[:3] == [None] * 3
    assert fake_ctx.views[3] == view


async def test_send_pages_accepts_message_reference(fake_ctx):
    long = "much much longer\n" * 400
    message = {}

    await send_pages(fake_ctx, long, reference=message)
    assert fake_ctx.references == [message] * 4


def test_escape_md_block_preserves_non_block_code():
    with_code = "foo `code section` bar"
    assert escape_md_block(with_code) == with_code


def test_escape_md_block_removes_triple_backtick_blocks():
    with_backticks = """
        sample text
        ```
        the backticks around this should be replaced with
        something that won't break the outer code block
        ```
        sample text
    """
    assert "```" not in escape_md_block(with_backticks)


def test_format_duration_displays_hours_when_duration_ge_one_hour():
    assert format_duration(12 * 60 * 60 + 4 * 60 + 6) == "12:04:06"


def test_format_duration_hides_hours_when_duration_lt_one_hour():
    assert format_duration(2 * 60 + 4) == "2:04"
