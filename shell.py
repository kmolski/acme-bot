from datetime import datetime
from io import StringIO
from discord import File
from discord.ext import commands
from textx import metamodel_from_str


class ExprSeq:
    def __init__(self, parent=None, expr=None):
        self.parent = parent
        self.expr = expr

    async def eval(self, ctx):
        result = ""
        for elem in self.expr:
            ret = await elem.eval(ctx)
            if ret is not None:
                result += ret
        return result


class ExprComp:
    def __init__(self, parent, expr):
        self.parent = parent
        self.expr = expr

    async def eval(self, ctx):
        result, data = "", ""
        for elem in self.expr:
            result = await elem.eval(ctx, data)
            data = result
        return result


class Command:
    def __init__(self, parent, name, args):
        self.parent = parent
        self.name = name
        self.args = args

    async def eval(self, ctx, data):
        #   result = []
        #   async def get_output(
        #       content=None,
        #       *,
        #       tts=False,
        #       embed=None,
        #       file=None,
        #       files=None,
        #       delete_after=None,
        #       nonce=None
        #   ):
        #       result += (content, tts, embed, file, files, delete_after, nonce)
        cmd = ctx.bot.get_command(self.name)
        if cmd is None:
            raise commands.errors.CommandNotFound(
                'Command "{}" is not found'.format(ctx.invoked_with)
            )

        await cmd._verify_checks(ctx)
        await cmd.call_before_hooks(ctx)

        args = [ctx] if cmd.cog is None else [cmd.cog, ctx]
        args += [data] if data else []
        args += [await elem.eval(ctx) for elem in self.args]
        result = await cmd.callback(*args)

        await cmd.call_after_hooks(ctx)
        return result


class StrLiteral:
    def __init__(self, parent, value):
        self.parent = parent
        self.value = value

    async def eval(self, *_):
        return self.value


class IntLiteral:
    def __init__(self, parent, value):
        self.parent = parent
        self.value = value

    async def eval(self, *_):
        return self.value


class BoolLiteral:
    def __init__(self, parent, value):
        self.parent = parent
        self.value = value

    async def eval(self, *_):
        return self.value


class FileContent:
    def __init__(self, parent, name):
        self.parent = parent
        self.name = name

    async def eval(self, ctx, *_):
        for elem in ctx.message.attachments:
            if elem.filename == self.name:
                return str(await elem.read(), errors="replace")

        raise ValueError("No such file!")


class ExprSubst:
    def __init__(self, parent, expr):
        self.parent = parent
        self.expr = expr

    async def eval(self, ctx, *_):
        return await self.expr.eval(ctx)


class ShellModule(commands.Cog):
    GRAMMAR = """
ExprSeq:
    expr=ExprComp ('&&'- expr=ExprComp)*
;

ExprComp:
    expr=Expr ('|'- expr=Expr)*
;

Expr:
    Command | StrLiteral | FileContent | ExprSubst
;

Command:
    name=/[\\w\\-]*\\b/ args*=Argument
;

Argument:
    StrLiteral | IntLiteral | BoolLiteral | FileContent | ExprSubst
;

StrLiteral:
    value=STRING
;

IntLiteral:
    value=INT
;

BoolLiteral:
    value=BOOL
;

FileContent:
    '['- name=/[\\w\\-_. '"]+/ ']'-
;

ExprSubst:
    '('- expr=ExprSeq ')'-
;
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
