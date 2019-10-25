"""This module provides the shell interpreter capability to the bot."""
from datetime import datetime
from io import StringIO
from discord import File
from discord.ext import commands
from textx import metamodel_from_str


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

    async def eval(self, ctx, data, *, display):
        """Executes a command by evaluating its arguments, and calling its callback
        using the data piped in from the previous expression."""
        cmd = ctx.bot.get_command(self.name)
        if cmd is None:
            raise commands.CommandError(f"Command '{ctx.invoked_with}' not found")

        # Unfortunately there is no way to respect command
        # checks without accessing this protected method.
        await cmd._verify_checks(ctx)  # pylint: disable=protected-access
        await cmd.call_before_hooks(ctx)

        args = (
            ([ctx] if cmd.cog is None else [cmd.cog, ctx])
            + ([data] if data else [])  # Use the piped input only if it's not empty
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
        self.value = value

    async def eval(self, *_, **__):
        """Evaluates the boolean literal."""
        return self.value


class FileContent:
    """This class represents file contents for use in the TextX metamodel."""

    def __init__(self, parent, name):
        self.parent = parent
        self.name = name

    async def eval(self, ctx, *_, display):
        """Extracts the contents of the file, printing it
        in a code block if necessary."""
        for elem in ctx.message.attachments:
            if elem.filename == self.name:
                content = str(await elem.read(), errors="replace")
                if display:
                    await ctx.send(f"```\n{content}\n```")
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
        if display:
            await ctx.send(f"```\n{result}\n```")
        return result


class ShellModule(commands.Cog):
    """This module is responsible for interpreting
    complex commands and manipulating text."""

    GRAMMAR = """
ExprSeq: expr_comps=ExprComp ('&&'- expr_comps=ExprComp)* ;

ExprComp: exprs=Expr ('|'- exprs=Command)* ;

Expr: Command | StrLiteral | FileContent | ExprSubst;

Command: name=COMMAND_NAME args*=Argument;

Argument: IntLiteral | BoolLiteral | StrLiteral | FileContent | ExprSubst;

StrLiteral: value=STRING | value=CODE_BLOCK;

IntLiteral: value=INT;

BoolLiteral: value=BOOL;

FileContent: '['- name=FILE_NAME ']'- ;

ExprSubst: '('- expr_seq=ExprSeq ')'- ;

CODE_BLOCK: /```((?:\\`|[^`])*)```/;
COMMAND_NAME: /[\\w\\-]*\\b/;
FILE_NAME: /[\\w\\-_. '"]+/;
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

    @commands.command(aliases=["cat"])
    async def concat(self, ctx, *arguments, display=True):
        """Joins its arguments together into a single string."""
        arguments = [str(element) for element in arguments]
        content = "".join(arguments)
        if display:
            await ctx.send(content)
        return content

    @commands.command(name="!", hidden=True)
    async def eval(self, ctx, *, command):
        """Interprets and executes the given command."""
        model = self.META_MODEL.model_from_str(command)
        await model.eval(ctx)

    @commands.command()
    async def ping(self, ctx, *, display=True):
        """Measures the time it takes to communicate with the Discord servers."""
        start = datetime.now()
        # Adding a reaction is not done until the bot receives a response
        # from the Discord servers, so it can be used to measure the time.
        await ctx.message.add_reaction("\U0001F3D3")
        milliseconds = str((datetime.now() - start).microseconds // 1000)
        if display:
            await ctx.send(f"\U0001F4A8 Meep meep! **{milliseconds} ms**.")
        return milliseconds

    @commands.command()
    async def pretty(self, ctx, content, file_format="", *, display=True):
        """Prints the input data with highlighting specified by 'file_format'."""
        content = f"```{file_format}\n{content}\n```"
        if display:
            await ctx.send(content)
        return content

    @commands.command(name="to-file", aliases=["tee"])
    async def to_file(self, ctx, content, file_name, *, display=True):
        """Redirects the input data to a new file with the specified filename."""
        content, file_name = str(content), f"{ctx.author.name}_{file_name}"
        with StringIO(content) as stream:
            new_file = File(stream, filename=file_name)
            await ctx.send(f"\U0001F4BE Created file **{file_name}**.", file=new_file)
            if display:
                await ctx.send(f"```\n{content}\n```")
        return content

    @commands.command()
    async def tts(self, ctx, content, **_):
        """Makes the bot send a text-to-speech message with the given content."""
        await ctx.send(content, tts=True, delete_after=0.0)