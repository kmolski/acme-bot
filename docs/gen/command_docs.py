#! /usr/bin/env python
"""Generate markdown documentation from command & cog docstrings."""
#  Copyright (C) 2023  Krzysztof Molski
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

from html import escape
from itertools import chain

from discord.utils import escape_markdown

from acme_bot import import_submodules, get_autoloaded_cogs
from acme_bot.textutils import escape_md_block

HEADER = """
# Commands reference

The following documentation is also available through the `help` command.

Parameter notation follows the manpage conventions - angle brackets indicate
required parameters, while square brackets indicate optional ones. Names of
variable argument lists are followed by three dots.

For example:
**command &lt;required&gt; [optional] [variable_list...]**
"""


def _get_command_cogs(cogs):
    return [
        cmd_cog
        for cmd_cog in cogs
        if (cmd_cog.__cog_commands__ or cmd_cog.__cog_app_commands__)
    ]


def _get_cog_commands(cmd_cog):
    return chain(cmd_cog.__cog_commands__, cmd_cog.__cog_app_commands__)


def _has_any_docs(cmd_cog):
    return any(cmd.help for cmd in _get_cog_commands(cmd_cog))


def _escape_md(text):
    return escape_markdown(escape(text))


def _cog_header(cmd_cog):
    cog_name = cmd_cog.__cog_name__
    return f"""
{_escape_md(cog_name)}
{'-' * len(cog_name)}
"""


def _cog_description(cmd_cog):
    return f"""
{_escape_md(cmd_cog.__cog_description__)}
"""


def _cmd_docs(cmd):
    signature = _escape_md(cmd.signature)
    return f"""
### {'/'.join([cmd.name] + cmd.aliases)}{(" " + signature).rstrip()}
```
{escape_md_block(cmd.help)}
```
"""


def _cog_commands(cmd_cog):
    return "\n".join(
        _cmd_docs(cmd).lstrip()
        for cmd in sorted(_get_cog_commands(cmd_cog), key=lambda cmd: cmd.name)
        if cmd.help
    )


if __name__ == "__main__":
    import_submodules()
    all_cogs = get_autoloaded_cogs()
    command_cogs = _get_command_cogs(all_cogs)

    print(HEADER.lstrip())

    for cog in filter(_has_any_docs, command_cogs):
        print(_cog_header(cog).lstrip())
        print(_cog_description(cog).lstrip())
        print(_cog_commands(cog))
