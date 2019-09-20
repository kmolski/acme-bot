from datetime import datetime
from io import StringIO
from discord import File
from discord.ext import commands
from textx import metamodel_from_str


class ExprSeq:
    def __init__(self, parent=None, expr_comps=None):
        self.parent = parent
        self.expr_comps = expr_comps

    async def eval(self, ctx, display=True):
        result = ""
        for elem in self.expr_comps:
            ret = await elem.eval(ctx, display)
            if ret is not None:
                result += ret
        return result


class ExprComp:
    def __init__(self, parent, exprs):
        self.parent = parent
        self.exprs = exprs

    async def eval(self, ctx, display):
        data, result = "", ""
        end = len(self.exprs) - 1
        for index, elem in enumerate(self.exprs):
            result = await elem.eval(ctx, data, display=display and (index == end))
            data = result
        return result


class Command:
    def __init__(self, parent, name, args):
        self.parent = parent
        self.name = name
        self.args = args

    async def eval(self, ctx, data, *, display):
        cmd = ctx.bot.get_command(self.name)
        if cmd is None:
            raise commands.CommandError(f"Command '{ctx.invoked_with}' not found")

        # Unfortunately there is no way to respect command
        # checks without accessing this protected method.
        await cmd._verify_checks(ctx)  # pylint: disable=protected-access
        await cmd.call_before_hooks(ctx)

        args = (
            ([ctx] if cmd.cog is None else [cmd.cog, ctx])
            + ([data] if data else [])
            + ([await elem.eval(ctx, display=False) for elem in self.args])
        )
        result = await cmd.callback(*args, display=display)

        await cmd.call_after_hooks(ctx)
        return result


class StrLiteral:
    def __init__(self, parent, value):
        self.parent = parent
        self.value = value

    async def eval(self, ctx, *_, display):
        if display:
            await ctx.send(f"```\n{self.value}\n```")
        return self.value


class IntLiteral:
    def __init__(self, parent, value):
        self.parent = parent
        self.value = value

    async def eval(self, *_, **__):
        return self.value


class BoolLiteral:
    def __init__(self, parent, value):
        self.parent = parent
        self.value = value

    async def eval(self, *_, **__):
        return self.value


class FileContent:
    def __init__(self, parent, name):
        self.parent = parent
        self.name = name

    async def eval(self, ctx, *_, display):
        for elem in ctx.message.attachments:
            if elem.filename == self.name:
                content = str(await elem.read(), errors="replace")
                if display:
                    await ctx.send(f"```\n{content}\n```")
                return content

        raise commands.CommandError("No such file!")


class ExprSubst:
    def __init__(self, parent, expr_seq):
        self.parent = parent
        self.expr_seq = expr_seq

    async def eval(self, ctx, *_, display):
        result = await self.expr_seq.eval(ctx)
        if display:
            await ctx.send(f"```\n{result}\n```")
        return result


class ShellModule(commands.Cog):
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
        arguments = [str(element) for element in arguments]
        content = "".join(arguments)
        if display:
            await ctx.send(content)
        return content

    @commands.command(aliases=["!"])
    async def eval(self, ctx, *, expression):
        model = self.META_MODEL.model_from_str(expression)
        await model.eval(ctx)

    @commands.command()
    async def join(self, ctx, *arguments, display=True):
        *arguments, separator = [str(element) for element in arguments]
        content = separator.join(arguments)
        if display:
            await ctx.send(content)
        return content

    @commands.command()
    async def ping(self, ctx, *, display=True):
        start = datetime.now()
        await ctx.message.add_reaction("\U0001F3D3")
        milliseconds = str((datetime.now() - start).microseconds // 1000)
        if display:
            await ctx.send(f"\U0001F4A8 Meep meep! **{milliseconds} ms**.")
        return milliseconds

    @commands.command()
    async def pretty(self, ctx, content, file_format="", *, display=True):
        content = f"```{file_format}\n{content}\n```"
        if display:
            await ctx.send(content)
        return content

    @commands.command(name="to-file", aliases=["tee"])
    async def to_file(self, ctx, content, file_name, *, display=True):
        content, file_name = str(content), f"{ctx.author.name} - {file_name}"
        with StringIO(content) as stream:
            new_file = File(stream, filename=file_name)
            await ctx.send(f"\U0001F4BE Created file **{file_name}**.", file=new_file)
            if display:
                await ctx.send(f"```\n{content}\n```")
        return content

    @commands.command()
    async def tts(self, ctx, content, **_):
        await ctx.send(content, tts=True, delete_after=5.0)
