"""Shell utility commands."""

#  Copyright (C) 2019-2024  Krzysztof Molski
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

import asyncio
import logging
import re
from datetime import datetime
from io import StringIO
from itertools import groupby
from random import shuffle
from shutil import which

from discord import File
from discord.ext import commands

from acme_bot.autoloader import CogFactory, autoloaded
from acme_bot.convutils import to_int
from acme_bot.shell.interpreter import FileContent
from acme_bot.textutils import escape_md_block, MD_BLOCK_FMT


log = logging.getLogger(__name__)


def validate_options(args, regex):
    """Validate each argument in args against the provided regex.
    If any argument does not match fully, a CommandError is raised."""
    for arg in args:
        if not regex.fullmatch(arg):
            raise commands.CommandError(f"Argument `{arg}` is not allowed.")


def trim_double_newline(string):
    """Trim down double newlines at the end of the string, such that
    'abc\n\n' becomes 'abc\n', but 'abc\n' is still 'abc\n'."""
    return string[:-1] if string[-2:] == "\n\n" else string


async def execute_system_cmd(name, *args, stdin=None):
    """Execute a system command and communicates with the process.
    The `stdin` argument is encoded and passed into the standard input.
    Therefore, it must be convertible into a `bytes` object."""
    stdin = stdin.encode() if stdin is not None else None
    proc = await asyncio.create_subprocess_exec(
        name,
        *args,
        stdin=asyncio.subprocess.PIPE if stdin is not None else None,
        stdout=asyncio.subprocess.PIPE,
    )

    (stdout, stderr) = await proc.communicate(stdin)
    if proc.returncode != 0:
        log.warning(
            "%s (PID %s) terminated with return code of %s",
            name,
            proc.pid,
            proc.returncode,
        )
        if error_msg := stderr or stdout:
            raise commands.CommandError(str(error_msg, errors="replace"))

    return str(stdout, errors="replace")


@autoloaded
class ShellModule(commands.Cog, CogFactory):
    """Shell utility commands."""

    __GREP_ARGS = re.compile(r"-[0-9ABCEFGiovwx]+")

    @classmethod
    async def create_cog(cls, bot):
        return cls()

    @commands.command(aliases=["conc", "cat"])
    async def concat(self, ctx, *arguments):
        """
        Concatenate all argument strings.

        ARGUMENTS
            arguments... - input strings

        RETURN VALUE
            The arguments joined into a single string.
        """
        content = "".join(str(arg) for arg in arguments)
        if ctx.display:
            await ctx.send_pages(escape_md_block(content), fmt=MD_BLOCK_FMT)
        return content

    @commands.command()
    async def ping(self, ctx):
        """
        Measure latency between the bot and Discord servers.

        RETURN VALUE
            The millisecond latency as an integer.
        """
        start = datetime.now()
        # Adding a reaction is not done until the bot receives a response
        # from the Discord servers, so it can be used to measure the time.
        await ctx.message.add_reaction("\U0001F3D3")
        milliseconds = str((datetime.now() - start).microseconds // 1000)
        if ctx.display:
            await ctx.send(f"\U0001F4A8 Meep meep! **{milliseconds} ms**.")
        return milliseconds

    @commands.command(aliases=["prin"])
    async def print(self, ctx, content, file_format=""):
        """
        Pretty print the input string with the given syntax highlighting.

        ARGUMENTS
            content     - input string
            file_format - format for syntax highlighting (default: none)

        RETURN VALUE
            The unchanged input data as a string.
        """
        content, file_format = str(content), str(file_format)
        if ctx.display:
            await ctx.send_pages(
                escape_md_block(content), fmt=f"```{file_format}\n{{}}\n```"
            )
        return content

    @commands.command(name="to-file", aliases=["tfil", "tee"])
    async def to_file(self, ctx, content, file_name):
        """
        Redirect the input string to a file with the given name.

        The output file name will be prefixed with your username.

        ARGUMENTS
            content   - input string
            file_name - name of the file to write into

        RETURN VALUE
            The unchanged input data as a string.
        """
        content, file_name = str(content), f"{ctx.author.name}_{file_name}"
        with StringIO(content) as stream:
            new_file = File(stream, filename=file_name)
            await ctx.send(f"\U0001F4BE Created file **{file_name}**.", file=new_file)
        return content

    @commands.command()
    async def open(self, ctx, file_name):
        """
        Read the contents of a file with the given name.

        ARGUMENTS
            file_name - name of the file to read

        RETURN VALUE
            The contents of the file as a string.
        """
        file_content = FileContent(None, str(file_name))
        return await file_content.eval(ctx)

    @commands.command(enabled=which("grep"))
    async def grep(self, ctx, data, patterns, *opts):
        """
        Select lines of the input string that match the given patterns.

        ARGUMENTS
            data     - input string
            patterns - regex patterns to match
            opts...  - additional options:
                '-A NUM' - include NUM lines of context following each match
                '-B NUM' - include NUM lines of context preceding each match
                '-C NUM' - include NUM lines of context around each match

                '-E' - interpret `patterns` as extended regular expressions
                '-F' - interpret `patterns` as fixed strings
                '-G' - interpret `patterns` as basic regular expressions

                '-i' - perform case-insensitive matching
                '-o' - only show the matching part of the lines
                '-v' - only show the non-matching input lines
                '-w' - only show matches of whole words
                '-x' - only show exact matches of whole lines

        RETURN VALUE
            The selected input data lines as a string.
        """
        data, patterns = str(data), str(patterns)

        opts = [str(option) for option in opts]
        validate_options(opts, self.__GREP_ARGS)
        # Filter out empty lines that produce all-matching patterns.
        patterns = "\n".join(p for p in patterns.splitlines() if p)

        output = trim_double_newline(
            await execute_system_cmd(
                "grep", "--color=never", "-e", patterns, *opts, "--", "-", stdin=data
            )
        )

        if ctx.display:
            await ctx.send_pages(escape_md_block(output), fmt=MD_BLOCK_FMT)

        return output

    @commands.command(aliases=["unit"], enabled=which("units"))
    async def units(self, ctx, from_unit, to_unit):
        """
        Convert between measurement units.

        ARGUMENTS
            from_unit - the input expression or measurement unit
            to_unit   - the output measurement unit

        RETURN VALUE
            The conversion result as a string.
        """
        from_unit, to_unit = str(from_unit), str(to_unit)

        output = (
            await execute_system_cmd("units", "--terse", "--", from_unit, to_unit)
        ).strip()

        if ctx.display:
            await ctx.send_pages(f"\U0001F9EE {from_unit} = {output} {to_unit}.")
        return output

    @commands.command()
    async def tail(self, ctx, data, line_count=10):
        """
        Show the final lines of the input string.

        ARGUMENTS
            data       - input string
            line_count - number of final lines to display (default: 10)

        RETURN VALUE
            The last [line_count] lines of input data as a string.
        """
        data, line_count = str(data), to_int(line_count)
        if line_count <= 0:
            raise commands.CommandError("Argument `line_count` must be positive.")

        lines = data.splitlines()[-line_count:]
        output = "\n".join(lines)

        if ctx.display:
            await ctx.send_pages(escape_md_block(output), fmt=MD_BLOCK_FMT)

        return output

    @commands.command()
    async def head(self, ctx, data, line_count=10):
        """
        Show the initial lines of the input string.

        ARGUMENTS
            data       - input string
            line_count - number of initial lines to display (default: 10)

        RETURN VALUE
            The first [line_count] lines of input data as a string.
        """
        data, line_count = str(data), to_int(line_count)
        if line_count <= 0:
            raise commands.CommandError("Argument `line_count` must be positive.")

        lines = data.splitlines()[:line_count]
        output = "\n".join(lines)

        if ctx.display:
            await ctx.send_pages(escape_md_block(output), fmt=MD_BLOCK_FMT)

        return output

    @commands.command(aliases=["line"])
    async def lines(self, ctx, data, start, end):
        """
        Show the given line range of the input string.

        ARGUMENTS
            data  - input string
            start - number of the first line to display
            end   - number of the last line to display

        RETURN VALUE
            The selected input data lines as a string.
        """
        start, end = to_int(start), to_int(end)
        if start <= 0:
            raise commands.CommandError("Argument `start` must be positive.")
        if start > end:
            raise commands.CommandError(
                "Argument `start` must not be greater than `end`."
            )

        lines = data.splitlines()[start - 1 : end]
        output = "\n".join(lines)

        if ctx.display:
            await ctx.send_pages(escape_md_block(output), fmt=MD_BLOCK_FMT)

        return output

    @commands.command(aliases=["coun", "wc"])
    async def count(self, ctx, data):
        """
        Count lines in the input string.

        ARGUMENTS
            data - input string

        RETURN VALUE
            The number of lines in the input data as an integer.
        """
        data = str(data).splitlines()
        count = len(data)

        if ctx.display:
            await ctx.send_pages(str(count), fmt=MD_BLOCK_FMT)

        return count

    @commands.command(aliases=["enum", "nl"])
    async def enumerate(self, ctx, data):
        """
        Number lines of the input string.

        ARGUMENTS
            data - input string

        RETURN VALUE
            The numbered lines of the input data as a string.
        """
        lines = str(data).splitlines()
        line_count = len(lines)
        max_digits = len(str(line_count))
        output = "\n".join(
            f"{n:{max_digits}}  {line}" for n, line in enumerate(lines, start=1)
        )

        if ctx.display:
            await ctx.send_pages(escape_md_block(output), fmt=MD_BLOCK_FMT)

        return output

    @commands.command()
    async def sort(self, ctx, data):
        """
        Sort lines of the input string alphabetically.

        ARGUMENTS
            data - input string

        RETURN VALUE
            The sorted lines of the input data as a string.
        """
        lines = str(data).splitlines()
        output = "\n".join(sorted(lines))

        if ctx.display:
            await ctx.send_pages(escape_md_block(output), fmt=MD_BLOCK_FMT)

        return output

    @commands.command(aliases=["uniq"])
    async def unique(self, ctx, data):
        """
        Remove adjacent matching lines from the input string.

        ARGUMENTS
            data - input string

        RETURN VALUE
            The unique lines of the input data as a string.
        """
        lines = str(data).splitlines()
        output = "\n".join(line for line, _ in groupby(lines))

        if ctx.display:
            await ctx.send_pages(escape_md_block(output), fmt=MD_BLOCK_FMT)

        return output

    @commands.command(aliases=["shuf"])
    async def shuffle(self, ctx, data):
        """
        Randomly shuffle lines of the input string.

        ARGUMENTS
            data - input string

        RETURN VALUE
            The shuffled lines of the input data as a string.
        """
        lines = str(data).splitlines()
        shuffle(lines)
        output = "\n".join(lines)

        if ctx.display:
            await ctx.send_pages(escape_md_block(output), fmt=MD_BLOCK_FMT)

        return output
