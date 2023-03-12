from itertools import cycle, islice, repeat

from acme_bot.textutils import escape_md_block, send_pages
from test.discord_context import fake_context


async def test_send_pages_short_msgs_are_unchanged():
    short = "too short to split"

    fake_ctx = fake_context()
    await send_pages(fake_ctx, short)
    assert fake_ctx.messages == [short]


async def test_send_pages_long_lines_are_split_to_multiple_messages():
    long_line = "much much longer " * 3

    fake_ctx = fake_context()
    await send_pages(fake_ctx, long_line, max_length=10)
    assert fake_ctx.messages == list(islice(cycle(["much much", "longer"]), 6))


async def test_send_pages_long_multiline_split_into_multiple_messages():
    long = "much much longer\n" * 4

    fake_ctx = fake_context()
    await send_pages(fake_ctx, long, max_length=20)
    assert fake_ctx.messages == list(islice(repeat("much much longer"), 4))


async def test_send_pages_preserves_empty_lines():
    with_empty = "foobar\n\n" * 4

    fake_ctx = fake_context()
    await send_pages(fake_ctx, with_empty)
    assert fake_ctx.messages == [with_empty.rstrip()]


async def test_send_pages_accepts_format_string():
    content = "sample text"
    fmt = "```\n{}\n```"

    fake_ctx = fake_context()
    await send_pages(fake_ctx, content, fmt=fmt)
    assert fake_ctx.messages[0] == fmt.format(content)
    assert "```" in fake_ctx.messages[0]


async def test_send_pages_escapes_markdown_blocks_in_content():
    content = """
        sample text
        ```
        the backticks around this should be replaced with
        something that won't break the outer code block
        ```
        sample text
    """

    fake_ctx = fake_context()
    await send_pages(fake_ctx, content, escape_md_blocks=True)
    assert "```" not in fake_ctx.messages[0]


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
