"""Shell utility commands."""
#  Copyright (C) 2019-2023  Krzysztof Molski
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

from copy import copy
from datetime import datetime
from io import StringIO
from itertools import groupby
from random import shuffle
from shutil import which

import asyncio
import logging
import re

from discord import File
from discord.ext import commands
from textx import metamodel_from_str

from acme_bot.autoloader import CogFactory, autoloaded
from acme_bot.textutils import split_message, MAX_MESSAGE_LENGTH


def validate_options(args, regex):
    """Validate each argument in args against the provided regex.
    If any argument does not match fully, a CommandError is raised."""
    for arg in args:
        if not regex.fullmatch(arg):
            raise commands.CommandError(f"Argument `{arg}` is not allowed.")


def trim_double_newline(string):
    """Trim down double newlines at the end of the string, such that
    'abc\n\n' becomes 'abc\n', but 'abc\n' is still 'abc\n'."""
    return string if string[-2:] != "\n\n" else string[:-1]


async def execute_system_cmd(name, *args, stdin=None):
    """Execute a system command and communicates with the process.
    The `stdin` argument is encoded and passed into the standard input.
    Therefore, it must be convertible into a `bytes` object."""
    stdin = stdin.encode() if stdin else None
    proc = await asyncio.create_subprocess_exec(
        name,
        *args,
        stdin=asyncio.subprocess.PIPE if stdin else None,
        stdout=asyncio.subprocess.PIPE,
    )

    (stdout, stderr) = await proc.communicate(stdin)

    if proc.returncode != 0:
        logging.warning(
            "%s (PID %s) terminated with code %s", name, proc.pid, proc.returncode
        )
        if error_msg := stderr or stdout:
            raise commands.CommandError(str(error_msg, errors="replace"))

    return str(stdout, errors="replace")


class ExprSeq:
    """This class represents expression sequences for use in the TextX metamodel."""

    def __init__(self, parent=None, expr_comps=None):
        self.parent = parent
        self.expr_comps = expr_comps

    async def eval(self, ctx):
        """Evaluate an expression sequence by evaluating its components and
        concatenating their return values."""
        result = ""
        for elem in self.expr_comps:
            ret = await elem.eval(ctx)
            if ret is not None:
                result += str(ret)
        return result


class ExprComp:
    """This class represents expression compositions for use in the TextX metamodel."""

    def __init__(self, parent, exprs):
        self.parent = parent
        self.exprs = exprs

    async def eval(self, ctx):
        """Evaluate an expression composition by evaluating the components and
        passing the return value of the previous expression to the input of the
        following commands."""
        data, result = None, ""
        end = len(self.exprs) - 1
        for index, elem in enumerate(self.exprs):
            # Only display outputs if this expression is the last one in sequence.
            temp_ctx = copy(ctx)
            temp_ctx.display = ctx.display and (index == end)
            try:
                result = await elem.eval(temp_ctx, data)
            except (commands.CommandError, TypeError):
                # Set the current command to the actual command throwing the exception.
                ctx.command = temp_ctx.command
                raise
            data = result
        return result


class Command:
    """This class represents the bot's commands for use in the TextX metamodel."""

    def __init__(self, parent, name, args):
        self.parent = parent
        self.name = name
        self.args = args

    async def eval(self, ctx, pipe):
        """Execute a command by evaluating its arguments, and calling its callback
        using the data piped in from the previous expression."""
        cmd = ctx.bot.get_command(self.name)
        if cmd is None:
            raise commands.CommandError(f"Command '{self.name}' not found")

        ctx.command = cmd
        if not await cmd.can_run(ctx):
            raise commands.CommandError(f"Checks for {cmd.qualified_name} failed")
        await cmd.call_before_hooks(ctx)

        # Set display to False so that argument evaluation doesn't print outputs.
        temp_ctx = copy(ctx)
        temp_ctx.display = False
        args = (
            ([ctx] if cmd.cog is None else [cmd.cog, ctx])
            + ([pipe] if pipe is not None else [])  # Use the pipe if it's not empty
            + ([await elem.eval(temp_ctx) for elem in self.args])
        )
        result = await cmd.callback(*args)

        await cmd.call_after_hooks(ctx)
        return result


class StrLiteral:
    """This class represents string literals for use in the TextX metamodel."""

    def __init__(self, parent, value):
        self.parent = parent
        self.value = value

    async def eval(self, ctx):
        """Evaluate the string literal, printing it in a code block if necessary."""
        if ctx.display:
            await ctx.send(f"```\n{self.value}\n```")
        return self.value


class IntLiteral:
    """This class represents integer literals for use in the TextX metamodel."""

    def __init__(self, parent, value):
        self.parent = parent
        self.value = value

    async def eval(self, *_, **__):
        """Evaluate the integer literal."""
        return self.value


class BoolLiteral:
    """This class represents boolean literals for use in the TextX metamodel."""

    def __init__(self, parent, value):
        self.parent = parent
        self.value = value.lower() in ("yes", "true", "enable", "on")

    async def eval(self, *_, **__):
        """Evaluate the boolean literal."""
        return self.value


class FileContent:
    """This class represents file contents for use in the TextX metamodel."""

    def __init__(self, parent, name):
        self.parent = parent
        self.name = name

    async def eval(self, ctx):
        """Extract the file contents."""
        async for msg in ctx.history(limit=1000):
            for elem in msg.attachments:
                if elem.filename == self.name:
                    content = str(await elem.read(), errors="replace")
                    if ctx.display:
                        fmt = "```\n{}\n```"
                        chunks = split_message(content, MAX_MESSAGE_LENGTH - len(fmt))
                        for chunk in chunks:
                            await ctx.send(fmt.format(chunk))
                    return content

        raise commands.CommandError("No such file!")


class ExprSubst:
    """This class represents expression substitutions for use in the TextX metamodel."""

    def __init__(self, parent, expr_seq):
        self.parent = parent
        self.expr_seq = expr_seq

    async def eval(self, ctx):
        """Evaluate the expression sequence in the substitution."""
        result = await self.expr_seq.eval(ctx)
        return result


@autoloaded
class ShellModule(commands.Cog, CogFactory):
    """Shell utility commands."""

    GRAMMAR = r"""
ExprSeq: expr_comps=ExprComp ('&&'- expr_comps=ExprComp)* ;

ExprComp: exprs=Expr ('|'- exprs=Command)* ;

Expr: Command | FileContent | ExprSubst | StrLiteral;

Command: name=COMMAND_NAME args*=Argument;

Argument: IntLiteral | BoolLiteral | FileContent | ExprSubst | StrLiteral;

StrLiteral: value=STRING | value=CODE_BLOCK | value = UNQUOTED_WORD;

IntLiteral: value=NUMBER;

BoolLiteral: value=BOOLEAN;

FileContent: '['- name=FILE_NAME ']'- ;

ExprSubst: '('- expr_seq=ExprSeq ')'- ;

BOOLEAN: /(?i)(yes|true|enable|on|no|false|disable|off)\b/;
CODE_BLOCK: /(?ms)```(?:[^`\n]*\n)?(.*?)```/;
COMMAND_NAME: /[\w\-]+\b/;
FILE_NAME: /[\w\-. '\"]+/;
UNQUOTED_WORD: /(\S+)\b/;
"""

    META_MODEL = metamodel_from_str(
        GRAMMAR,
        classes=[
            ExprSeq,
            ExprComp,
            Command,
            StrLiteral,
            IntLiteral,
            BoolLiteral,
            FileContent,
            ExprSubst,
        ],
        use_regexp_group=True,
    )

    __GREP_ARGS = re.compile(r"-[0-9ABCEFGiovwx]+")

    @classmethod
    def create_cog(cls, bot):
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
            for chunk in split_message(content, MAX_MESSAGE_LENGTH):
                await ctx.send(chunk)
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

    @commands.command()
    async def print(self, ctx, content, file_format=""):
        """
        Pretty print the input string with the given syntax highlighting.

        ARGUMENTS
            content     - input string
            file_format - format for syntax highlighting (default: none)

        RETURN VALUE
            The unchanged input data as a string.
        """
        content = str(content)
        if ctx.display:
            format_str = f"```{file_format}\n{{}}\n```"
            chunks = split_message(content, MAX_MESSAGE_LENGTH - len(format_str))
            for chunk in chunks:
                await ctx.send(format_str.format(chunk))
        return f"```{file_format}\n{content}\n```"

    @commands.command(name="to-file", aliases=["tofi", "tee"])
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
        file_name = str(file_name)
        file_content = FileContent(None, file_name)
        return await file_content.eval(ctx)

    @commands.command()
    async def tts(self, ctx, content):
        """
        Send the input string as a text-to-speech message.

        ARGUMENTS
            content - message content

        RETURN VALUE
            The unchanged input data as a string.
        """
        content = str(content)
        await ctx.send(content, tts=True, delete_after=8.0)
        return content

    @commands.command(enabled=which("grep"))
    async def grep(self, ctx, data, patterns, *opts):
        """
        Select lines of the input string that match the given patterns.

        ARGUMENTS
            data     - input string
            patterns - regex patterns to match
            opts     - additional options:
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
        patterns = "\n".join(p for p in patterns.split("\n") if p)

        output = trim_double_newline(
            await execute_system_cmd(
                "grep", "--color=never", "-e", patterns, *opts, "--", "-", stdin=data
            )
        )

        if ctx.display:
            format_str = "```\n{}\n```"
            chunks = split_message(output, MAX_MESSAGE_LENGTH - len(format_str))
            for chunk in chunks:
                await ctx.send(format_str.format(chunk))

        return output

    @commands.command(enabled=which("units"))
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
            await ctx.send(f"\U0001F9EE {from_unit} = {output} {to_unit}.")
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
        data, line_count = str(data), int(line_count)

        lines = data.splitlines()[-line_count:]
        output = "\n".join(lines)

        if ctx.display:
            format_str = "```\n{}\n```"
            chunks = split_message(output, MAX_MESSAGE_LENGTH - len(format_str))
            for chunk in chunks:
                await ctx.send(format_str.format(chunk))

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
        data, line_count = str(data), int(line_count)

        lines = data.splitlines()[:line_count]
        output = "\n".join(lines)

        if ctx.display:
            format_str = "```\n{}\n```"
            chunks = split_message(output, MAX_MESSAGE_LENGTH - len(format_str))
            for chunk in chunks:
                await ctx.send(format_str.format(chunk))

        return output

    @commands.command()
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
        start, end = int(start) - 1, int(end)
        if start > end:
            raise commands.CommandError(
                f"Argument `start` = {start} must not be greater than `end` = {end}."
            )

        return await self.tail(ctx, await self.head(ctx, data, end), end - start)

    @commands.command(aliases=["wc"])
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
            format_str = "```\n{}\n```"
            await ctx.send(format_str.format(count))

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
            format_str = "```\n{}\n```"
            chunks = split_message(output, MAX_MESSAGE_LENGTH - len(format_str))
            for chunk in chunks:
                await ctx.send(format_str.format(chunk))

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
            format_str = "```\n{}\n```"
            chunks = split_message(output, MAX_MESSAGE_LENGTH - len(format_str))
            for chunk in chunks:
                await ctx.send(format_str.format(chunk))

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
            format_str = "```\n{}\n```"
            chunks = split_message(output, MAX_MESSAGE_LENGTH - len(format_str))
            for chunk in chunks:
                await ctx.send(format_str.format(chunk))

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
            format_str = "```\n{}\n```"
            chunks = split_message(output, MAX_MESSAGE_LENGTH - len(format_str))
            for chunk in chunks:
                await ctx.send(format_str.format(chunk))

        return output
