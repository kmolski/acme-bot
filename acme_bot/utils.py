"""Utility functions shared by all of the bot's modules."""
from itertools import chain
from textwrap import wrap

MAX_MESSAGE_LENGTH = 2000


def split_message(text, limit):
    """Splits a long message into chunks that are limited in length."""
    lines = chain.from_iterable(wrap(line, limit) for line in text.splitlines())

    messages = []
    current_msg = ""
    for line in lines:
        if len(current_msg) + len(line) > limit:
            messages.append(current_msg)
            current_msg = ""
        current_msg += line + "\n"

    messages.append(current_msg)
    return messages
