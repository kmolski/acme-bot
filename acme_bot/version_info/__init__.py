"""Version & license information commands."""
#  Copyright (C) 2022-2023  Krzysztof Molski
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

from dataclasses import dataclass
from importlib.metadata import version
from os.path import dirname, join

from discord.ext import commands

from acme_bot.autoloader import CogFactory, autoloaded


def get_commit_info_from_module():
    """Read the commit hash and date from the `commit.txt` file in this directory."""
    try:
        path = join(dirname(__file__), "commit.txt")
        with open(path, encoding="utf-8") as info_file:
            commit_hash, commit_date = info_file.read().strip().split()
            return commit_hash, commit_date
    except OSError:
        return None, None


@dataclass
class BuildInfo:
    """Information about the current build of the application."""

    version_number: str
    commit_hash: str
    commit_date: str

    @property
    def github_link(self):
        """Return a link to the source code of the current build, hosted on GitHub."""
        return f"https://github.com/kmolski/acme-bot/tree/{self.commit_hash}"


@autoloaded
class VersionInfoModule(commands.Cog, CogFactory):
    """Version & license information commands."""

    COPYRIGHT_INFO = "\n".join(["Copyright (C) 2019-2023  Krzysztof Molski"])

    MESSAGE_TEMPLATE = """
acme-bot {} ({} {})
{}

This program is free software: you can redistribute it and/or modify it under the terms
of the GNU Affero General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE
See the GNU Affero General Public License for more details.

The source code of this build is available here: {}.
"""

    def __init__(self, build_info):
        self.build_info = build_info

    @classmethod
    def create_cog(cls, bot):
        version_number = version("acme-bot")
        commit_hash, commit_date = get_commit_info_from_module()
        build_info = BuildInfo(version_number, commit_hash, commit_date)
        return cls(build_info)

    @commands.command(aliases=["vers"])
    async def version(self, ctx):
        """
        Show the version & license information for this instance.

        RETURN VALUE
            The version number as a string.
        """

        if ctx.display:
            content = self.MESSAGE_TEMPLATE.format(
                self.build_info.version_number,
                self.build_info.commit_hash or "commit info not available",
                self.build_info.commit_date or "",
                self.COPYRIGHT_INFO,
                self.build_info.github_link,
            )
            await ctx.send(content)
        return self.build_info.version_number
