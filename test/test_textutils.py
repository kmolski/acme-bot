from itertools import cycle, islice, repeat

from acme_bot.textutils import split_message


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
