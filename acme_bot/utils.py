from textwrap import wrap

MESSAGE_LENGTH_LIMIT = 2000


def split_message(text, limit):
    messages = []
    current_msg = ""
    for line in wrap(text, limit):
        if len(current_msg) + len(line) > limit:
            messages.append(current_msg)
            current_msg = ""
        current_msg += line + "\n"

    return messages
