from itertools import cycle, islice

from discord.ui import View

from acme_bot.textutils import escape_md_block, send_pages


async def test_send_pages_short_msgs_are_unchanged(fake_ctx):
    short = "too short to split"

    await send_pages(fake_ctx, short)
    assert fake_ctx.messages == [short]


async def test_send_pages_long_lines_are_split_to_multiple_messages(fake_ctx):
    long_line = "much much longer " * 3

    await send_pages(fake_ctx, long_line, max_length=10)
    assert fake_ctx.messages == list(islice(cycle(["much much", "longer"]), 6))


async def test_send_pages_long_multiline_split_into_multiple_messages(fake_ctx):
    long = "much much longer\n" * 4

    await send_pages(fake_ctx, long, max_length=20)
    assert fake_ctx.messages == ["much much longer"] * 4


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


async def test_send_pages_escapes_markdown_blocks_in_content(fake_ctx):
    content = """
        sample text
        ```
        the backticks around this should be replaced with
        something that won't break the outer code block
        ```
        sample text
    """

    await send_pages(fake_ctx, content, escape_md_blocks=True)
    assert "```" not in fake_ctx.messages[0]


async def test_send_pages_sends_view_in_last_chunk(fake_ctx):
    long = "much much longer\n" * 4
    view = View()

    await send_pages(fake_ctx, long, max_length=20, view=view)
    assert fake_ctx.views[:3] == [None] * 3
    assert fake_ctx.views[3] == view


async def test_send_pages_accepts_message_reference(fake_ctx):
    long = "much much longer\n" * 4
    message = {}

    await send_pages(fake_ctx, long, max_length=20, reference=message)
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
