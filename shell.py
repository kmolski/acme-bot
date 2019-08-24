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
            raise commands.CommandError(
                "Command '{}' not found".format(ctx.invoked_with)
            )

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
            await ctx.send("```\n{}\n```".format(self.value))
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
                    await ctx.send("```\n{}\n```".format(content))
                return content

        raise commands.CommandError("No such file!")


class ExprSubst:
    def __init__(self, parent, expr_seq):
        self.parent = parent
        self.expr_seq = expr_seq

    async def eval(self, ctx, *_, display):
        result = await self.expr_seq.eval(ctx)
        if display:
            await ctx.send("```\n{}\n```".format(result))
        return result


class ShellModule(commands.Cog):
    GRAMMAR = """
ExprSeq: expr_comps=ExprComp ('&&'- expr_comps=ExprComp)* ;

ExprComp: exprs=Expr ('|'- exprs=Expr)* ;

Expr: Command | StrLiteral | FileContent | ExprSubst;

Command: name=/[\\w\\-]*\\b/ args*=Argument;

Argument: StrLiteral | IntLiteral | BoolLiteral | FileContent | ExprSubst;

StrLiteral: value=STRING;

IntLiteral: value=INT;

BoolLiteral: value=BOOL;

FileContent: '['- name=/[\\w\\-_. '"]+/ ']'- ;

ExprSubst: '('- expr_seq=ExprSeq ')'- ;
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
    )

    @commands.command(name="!")
    async def execute(self, ctx, *, expr):
        model = self.META_MODEL.model_from_str(expr)
        result = await model.eval(ctx)
        if result:
            await ctx.send(result)

    @commands.command()
    async def concat(self, _, *args):
        content = " ".join(args)
        return content

    @commands.command()
    async def ping(self, ctx):
        start = datetime.now()
        msg = await ctx.send("Meep!")
        await msg.edit(
            content="Meep meep! {}ms.".format(
                (datetime.now() - start).microseconds // 1000
            )
        )

    @commands.command(name="to-file")
    async def to_file(self, ctx, content, filename):
        with StringIO(content) as stream:
            new_file = File(stream, filename=filename)
            await ctx.send("Created file {}.".format(filename), file=new_file)
