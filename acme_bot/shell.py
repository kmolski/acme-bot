"""This module provides the shell interpreter capability to the bot."""
from datetime import datetime
from io import StringIO
from shutil import which

import asyncio
import re

from discord import File
from discord.ext import commands
from textx import metamodel_from_str

from acme_bot.utils import split_message, MAX_MESSAGE_LENGTH


def validate_options(args, regex):
    """Validates each argument in args against the provided regex.
    If any argument does not match fully, a CommandError is raised."""
    for arg in args:
        if not regex.fullmatch(arg):
            raise commands.CommandError(f"Argument `{arg}` is not allowed.")


def trim_double_newline(string):
    """Trims down double newlines at the end of the string, such that
    'abc\n\n' becomes 'abc\n', but 'abc\n' is still 'abc\n'."""
    return string if string[-2:] != "\n\n" else string[:-1]


async def execute_system_cmd(name, *args, stdin=None):
    """Executes a system command and communicates with the process.
    The `stdin` argument is encoded and passed into the standard input.
    Therefore, it must be convertible into a `bytes` object."""
    stdin = stdin.encode() if stdin else None
    proc = await asyncio.create_subprocess_exec(
        name,
        *args,
        stdin=asyncio.subprocess.PIPE if stdin else None,
        stdout=asyncio.subprocess.PIPE,
    )

    (stdout, _) = await proc.communicate(stdin)
    await proc.wait()

    return str(stdout, errors="replace")


class ExprSeq:
    """This class represents expression sequences for use in the TextX metamodel."""

    def __init__(self, parent=None, expr_comps=None):
        self.parent = parent
        self.expr_comps = expr_comps

    async def eval(self, ctx, display=True):
        """Evaluates an expression sequence by evaluating its components and
        concatenating their return values."""
        result = ""
        for elem in self.expr_comps:
            ret = await elem.eval(ctx, display)
            if ret is not None:
                result += ret
        return result


class ExprComp:
    """This class represents expression compositions for use in the TextX metamodel."""

    def __init__(self, parent, exprs):
        self.parent = parent
        self.exprs = exprs

    async def eval(self, ctx, display):
        """Evaluates an expression composition by evaluating the components and
        passing the return value of the previous expression to the input of the
        following commands."""
        data, result = "", ""
        end = len(self.exprs) - 1
        for index, elem in enumerate(self.exprs):
            # The "display" keyword argument controls printing messages to the chat.
            # It is only true if this expression is the last one being evaluated.
            result = await elem.eval(ctx, data, display=display and (index == end))
            data = result
        return result


class Command:
    """This class represents the bot's commands for use in the TextX metamodel."""

    def __init__(self, parent, name, args):
        self.parent = parent
        self.name = name
        self.args = args

    async def eval(self, ctx, pipe, *, display):
        """Executes a command by evaluating its arguments, and calling its callback
        using the data piped in from the previous expression."""
        cmd = ctx.bot.get_command(self.name)
        if cmd is None:
            raise commands.CommandError(f"Command '{self.name}' not found")

        if not await cmd.can_run(ctx):
            raise commands.CommandError(f"Checks for {cmd.qualified_name} failed")
        await cmd.call_before_hooks(ctx)

        args = (
            ([ctx] if cmd.cog is None else [cmd.cog, ctx])
            + ([pipe] if pipe else [])  # Use the piped input only if it's not empty
            # Setting "display" to false, so that the argument eval doesn't print.
            + ([await elem.eval(ctx, display=False) for elem in self.args])
        )
        result = await cmd.callback(*args, display=display)

        await cmd.call_after_hooks(ctx)
        return result


class StrLiteral:
    """This class represents string literals for use in the TextX metamodel."""

    def __init__(self, parent, value):
        self.parent = parent
        self.value = value

    async def eval(self, ctx, *_, display):
        """Evaluates the string literal, printing it in a code block if necessary."""
        if display:
            await ctx.send(f"```\n{self.value}\n```")
        return self.value


class IntLiteral:
    """This class represents integer literals for use in the TextX metamodel."""

    def __init__(self, parent, value):
        self.parent = parent
        self.value = value

    async def eval(self, *_, **__):
        """Evaluates the integer literal."""
        return self.value


class BoolLiteral:
    """This class represents boolean literals for use in the TextX metamodel."""

    def __init__(self, parent, value):
        self.parent = parent
        self.value = value.lower() in ("yes", "true", "enable", "on")

    async def eval(self, *_, **__):
        """Evaluates the boolean literal."""
        return self.value


class FileContent:
    """This class represents file contents for use in the TextX metamodel."""

    def __init__(self, parent, name):
        self.parent = parent
        self.name = name

    async def eval(self, ctx, *_, display):
        """Extracts the contents of the file."""
        async for msg in ctx.history(limit=1000):
            for elem in msg.attachments:
                if elem.filename == self.name:
                    content = str(await elem.read(), errors="replace")
                    if display:
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

    async def eval(self, ctx, *_, display):
        """Evaluates the expression sequence in the substitution."""
        result = await self.expr_seq.eval(ctx, display)
        return result


class ShellModule(commands.Cog):
    """This module is responsible for interpreting
    complex commands and manipulating text."""

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

    __META_MODEL = metamodel_from_str(
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

    __GREP_ARGS = re.compile(r"-[0-9ABCEFGPcimnovwxy]+")

    @commands.command(aliases=["cat"])
    async def concat(self, ctx, *arguments, display=True):
        """Joins its arguments together into a single string."""
        content = "".join(str(arg) for arg in arguments)
        if display:
            for chunk in split_message(content, MAX_MESSAGE_LENGTH):
                await ctx.send(chunk)
        return content

    @commands.command(name="!", hidden=True)
    async def eval(self, ctx, *, command):
        """Interpret and execute the given command."""
        model = self.__META_MODEL.model_from_str(command)
        await model.eval(ctx)

    @commands.command()
    async def ping(self, ctx, *, display=True):
        """Measure the time it takes to communicate with the Discord servers."""
        start = datetime.now()
        # Adding a reaction is not done until the bot receives a response
        # from the Discord servers, so it can be used to measure the time.
        await ctx.message.add_reaction("\U0001F3D3")
        milliseconds = str((datetime.now() - start).microseconds // 1000)
        if display:
            await ctx.send(f"\U0001F4A8 Meep meep! **{milliseconds} ms**.")
        return milliseconds

    @commands.command()
    async def print(self, ctx, content, file_format="", *, display=True):
        """Print the input data with highlighting specified by 'file_format'."""
        content = str(content)
        if display:
            format_str = f"```{file_format}\n{{}}\n```"
            chunks = split_message(content, MAX_MESSAGE_LENGTH - len(format_str))
            for chunk in chunks:
                await ctx.send(format_str.format(chunk))
        return f"```{file_format}\n{content}\n```"

    @commands.command(name="to-file", aliases=["tee"])
    async def to_file(self, ctx, content, file_name, *, display=True):
        """Redirect the input data to a new file with the specified filename."""
        content, file_name = str(content), f"{ctx.author.name}_{file_name}"
        with StringIO(content) as stream:
            new_file = File(stream, filename=file_name)
            await ctx.send(f"\U0001F4BE Created file **{file_name}**.", file=new_file)
        return content

    @commands.command()
    async def open(self, ctx, file_name, *, display=True):
        """Read the contents of a file with the specified filename."""
        file_name = str(file_name)
        file_content = FileContent(None, file_name)
        return await file_content.eval(ctx, display=display)

    @commands.command()
    async def tts(self, ctx, content, **_):
        """Send a text-to-speech message with the given content."""
        content = str(content)
        await ctx.send(content, tts=True, delete_after=0.0)
        return content

    @commands.command(enabled=which("grep"))
    async def grep(self, ctx, data, patterns, *opts, display=True):
        """Print the lines of `data` that match one or more of the specified patterns.
        Additionally, a subset of `grep` arguments can be supplied as `opts`."""
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

        if display:
            format_str = "```\n{}\n```"
            chunks = split_message(output, MAX_MESSAGE_LENGTH - len(format_str))
            for chunk in chunks:
                await ctx.send(format_str.format(chunk))

        return output

    @commands.command(aliases=["uni"], enabled=which("units"))
    async def units(self, ctx, *arguments, display=True):
        """Convert between units. The initial arguments describe the input unit,
        and the last argument describes the output unit."""
        arguments = [str(arg) for arg in arguments]
        from_unit, to_unit = " ".join(arguments[:-1]), arguments[-1]

        output = (
            await execute_system_cmd(
                "units", "--verbose", "--one-line", "--", from_unit, to_unit
            )
        ).strip()

        if display:
            await ctx.send(f"\U0001F9EE {output}.")
        return output

    @commands.command(aliases=["tai"], enabled=which("tail"))
    async def tail(self, ctx, data, line_count=10, display=True):
        """Take the last `line_count` lines of the input."""
        data, line_count = str(data), int(line_count)

        output = trim_double_newline(
            await execute_system_cmd("tail", "-n", str(line_count), "-", stdin=data)
        )

        if display:
            format_str = "```\n{}\n```"
            chunks = split_message(output, MAX_MESSAGE_LENGTH - len(format_str))
            for chunk in chunks:
                await ctx.send(format_str.format(chunk))

        return output

    @commands.command(aliases=["hea"], enabled=which("head"))
    async def head(self, ctx, data, line_count=10, display=True):
        """Take the first `line_count` lines of the input."""
        data, line_count = str(data), int(line_count)

        output = trim_double_newline(
            await execute_system_cmd("head", "-n", str(line_count), "-", stdin=data)
        )

        if display:
            format_str = "```\n{}\n```"
            chunks = split_message(output, MAX_MESSAGE_LENGTH - len(format_str))
            for chunk in chunks:
                await ctx.send(format_str.format(chunk))

        return output

    @commands.command(aliases=["lin"], enabled=(head.enabled and tail.enabled))
    async def lines(self, ctx, data, start, end, display=True):
        """Take lines from the specified line range (`start-end`) of the input."""
        start, end = int(start) - 1, int(end)
        if start > end:
            raise commands.CommandError(
                f"Argument `start` = {start} must not be greater than `end` = {end}."
            )

        return await self.tail(
            ctx, await self.head(ctx, data, end, display=False), end - start, display
        )
