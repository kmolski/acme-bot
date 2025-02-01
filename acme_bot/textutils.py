"""Text utility functions used by other modules."""

#  Copyright (C) 2020-2024  Krzysztof Molski
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

from itertools import chain
from re import sub, MULTILINE
from textwrap import wrap

# According to https://discord.com/developers/docs/resources/channel
MAX_MESSAGE_LENGTH = 2000

MD_BLOCK_FMT = "```\n{}\n```"


def _split_message(text, limit):
    """Split a message into chunks with the specified maximum length.
    Lines longer than the limit are wrapped and split across chunks."""

    lines = chain.from_iterable(
        # To preserve empty lines, only wrap lines longer than the limit.
        wrap(line, limit) if len(line) > limit else [line]
        for line in text.splitlines()
    )

    messages = []
    current_msg = ""
    for line in lines:
        if len(current_msg) + len(line) > limit:
            messages.append(current_msg.rstrip())
            current_msg = ""
        current_msg += line + "\n"

    messages.append(current_msg.rstrip())
    return messages


async def send_pages(
    ctx,
    content,
    *,
    fmt=None,
    view=None,
    reference=None,
):
    """Split and send a message with the specified content and format."""
    max_length = MAX_MESSAGE_LENGTH
    if fmt is not None:
        max_length -= len(fmt)

    msg_chunks = _split_message(content, max_length)
    for i, chunk in enumerate(msg_chunks, start=1):
        if fmt is not None:
            chunk = fmt.format(chunk)
        chunk_view = view if i == len(msg_chunks) else None
        await ctx.send(chunk, reference=reference, view=chunk_view)


def escape_md_block(text):
    """Escape triple backtick delimiters in the given text."""
    return sub(r"```", "\U0000200b".join("```"), text, flags=MULTILINE)


def format_duration(secs):
    """Format duration seconds to a human-readable (HH:MM:SS) format."""
    formatted = ""
    mins = secs // 60
    hrs = mins // 60
    mins %= 60
    secs %= 60
    if hrs > 0:
        formatted += f"{hrs}:{mins:02}:"
    else:
        formatted += f"{mins}:"
    return formatted + f"{secs:02}"
