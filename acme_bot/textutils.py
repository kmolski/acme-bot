"""Text utility functions used by other modules."""
#  Copyright (C) 2020-2023  Krzysztof Molski
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
from textwrap import wrap

# According to https://discord.com/developers/docs/resources/channel
MAX_MESSAGE_LENGTH = 2000


def split_message(text, limit):
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
