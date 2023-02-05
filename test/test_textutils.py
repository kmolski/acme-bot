from itertools import cycle, islice, repeat

from acme_bot.textutils import escape_md_block, split_message


def test_split_message_short_msgs_are_unchanged():
    short = "too short to split"
    assert split_message(short, 100) == [short]


def test_split_message_long_lines_are_split_to_multiple_messages():
    long_line = "much much longer " * 3
    assert split_message(long_line, 10) == list(
        islice(cycle(["much much", "longer"]), 6)
    )


def test_split_message_long_multiline_split_into_multiple_messages():
    long = "much much longer\n" * 4
    assert split_message(long, 20) == list(islice(repeat("much much longer"), 4))


def test_split_message_preserves_empty_lines():
    with_empty = "foobar\n\n" * 4
    assert split_message(with_empty, 1000) == [with_empty.rstrip()]


def test_escape_md_block_preserves_non_block_code():
    with_code = "foo `code section` bar"
    assert escape_md_block(with_code) == with_code


def test_escape_md_block_remove_triple_backtick_blocks():
    with_backticks = """
        sample text
        ```
        the backticks around this should be replaced with
        something that won't break the outer code block
        ```
        sample text
    """
    assert "```" not in escape_md_block(with_backticks)
