"""This module provides version & license information commands to the bot."""
from importlib.metadata import version
from os.path import dirname, join

from discord.ext import commands


def get_version_number():
    return version("acme-bot")


def get_commit_info():
    try:
        path = join(dirname(__file__), "commit.txt")
        with open(path) as info_file:
            return info_file.read().strip()
    except OSError:
        return "commit info unavailable"


def get_github_link():
    return f"https://github.com/kmolski/acme-bot/tree/{get_commit_info().split()[0]}"


class VersionInfoModule(commands.Cog):
    """This module provides version & license information commands."""

    COPYRIGHT_INFO = """
Copyright (C) 2019-2022  Krzysztof Molski
""".strip()

    LICENSE_TEXT = f"""
{COPYRIGHT_INFO}

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

    VERSION_INFO = f"""
acme-bot {get_version_number()} ({get_commit_info()})
{COPYRIGHT_INFO}

This program is free software; run `license` command for more details.
The source code of this build is available here: {get_github_link()}.
"""

    @commands.command(aliases=["lic"])
    async def license(self, ctx, display=True):
        """Display the license of the bot."""
        if display:
            await ctx.send(f"```\n{self.LICENSE_TEXT}\n```")
        return self.LICENSE_TEXT

    @commands.command(aliases=["ver"])
    async def version(self, ctx, display=True):
        """Display the version of the bot instance and the link to its source code."""

        if display:
            await ctx.send(self.VERSION_INFO)
        return get_version_number()
