"""Shell interpreter based on the TextX parser generator."""
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
from os.path import join, dirname

from discord.ext import commands
from textx import metamodel_from_file

from acme_bot.textutils import MD_BLOCK_FMT


class ExprSeq:
    """This class represents expression sequences for use in the TextX metamodel."""

    def __init__(self, parent=None, expr_comps=None):
        self.parent = parent
        self.expr_comps = expr_comps

    def __eq__(self, other):
        return self.expr_comps == other.expr_comps

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

    def __eq__(self, other):
        return self.exprs == other.exprs

    async def eval(self, ctx):
        """Evaluate an expression composition by evaluating the components and
        passing the return value of the previous expression to the input of the
        following commands."""
        data, result = None, ""
        for index, elem in enumerate(self.exprs, start=1):
            # Display should only be enabled for the last expression in sequence.
            temp_ctx = copy(ctx)
            temp_ctx.display = ctx.display and (index == len(self.exprs))
            try:
                result = await elem.eval(temp_ctx, data)
            except (commands.CommandError, TypeError):
                # To report errors correctly, save the command throwing the exception.
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

    def __eq__(self, other):
        return self.name == other.name and self.args == other.args

    async def eval(self, ctx, pipe):
        """Execute a command by evaluating its arguments, and calling its callback
        using the data piped in from the previous expression."""
        cmd = ctx.bot.get_command(self.name)
        if cmd is None:
            raise commands.CommandError(f"Command `{self.name}` not found")

        ctx.command = cmd
        if not await cmd.can_run(ctx):
            raise commands.CommandError(f"Checks for {cmd.qualified_name} failed")
        await cmd.call_before_hooks(ctx)

        # Argument evaluation should not print outputs.
        temp_ctx = copy(ctx)
        temp_ctx.display = False
        args = (
            ([ctx] if cmd.cog is None else [cmd.cog, ctx])
            + ([pipe] if pipe is not None else [])
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

    def __eq__(self, other):
        return self.value == other.value

    async def eval(self, ctx, *_, **__):
        """Evaluate the string literal, printing it in a code block if necessary."""
        if ctx.display:
            await ctx.send_pages(self.value, fmt=MD_BLOCK_FMT, escape_md_blocks=True)
        return self.value


class IntLiteral:
    """This class represents integer literals for use in the TextX metamodel."""

    def __init__(self, parent, value):
        self.parent = parent
        self.value = value

    def __eq__(self, other):
        return self.value == other.value

    async def eval(self, *_, **__):
        """Evaluate the integer literal."""
        return self.value


class BoolLiteral:
    """This class represents boolean literals for use in the TextX metamodel."""

    def __init__(self, parent, value):
        self.parent = parent
        self.value = value.lower() in ("yes", "true", "enable", "on")

    def __eq__(self, other):
        return self.value == other.value

    async def eval(self, *_, **__):
        """Evaluate the boolean literal."""
        return self.value


class FileContent:
    """This class represents file contents for use in the TextX metamodel."""

    def __init__(self, parent, name):
        self.parent = parent
        self.name = name

    def __eq__(self, other):
        return self.name == other.name

    async def eval(self, ctx, *_, **__):
        """Extract the file contents."""
        async for msg in ctx.history(limit=1000):
            for elem in msg.attachments:
                if elem.filename == self.name:
                    content = str(await elem.read(), errors="replace")
                    if ctx.display:
                        await ctx.send_pages(
                            content, fmt=MD_BLOCK_FMT, escape_md_blocks=True
                        )
                    return content

        raise commands.CommandError("No such file!")


class ExprSubst:
    """This class represents expression substitutions for use in the TextX metamodel."""

    def __init__(self, parent, expr_seq):
        self.parent = parent
        self.expr_seq = expr_seq

    def __eq__(self, other):
        return self.expr_seq == other.expr_seq

    async def eval(self, ctx, *_, **__):
        """Evaluate the expression sequence in the substitution."""
        result = await self.expr_seq.eval(ctx)
        return result


META_MODEL = metamodel_from_file(
    join(dirname(__file__), "grammar.tx"),
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
