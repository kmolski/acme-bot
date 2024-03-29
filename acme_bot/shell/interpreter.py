"""Shell interpreter based on the TextX parser generator."""

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

from copy import copy
from os.path import join, dirname

from discord.ext import commands
from textx import metamodel_from_file

from acme_bot.textutils import escape_md_block, MD_BLOCK_FMT


class ExprSeq:
    """Expression sequence AST node."""

    def __init__(self, parent=None, expr_comps=None):
        self.parent = parent
        self.expr_comps = expr_comps

    def __eq__(self, other):
        return self.expr_comps == other.expr_comps

    async def eval(self, ctx):
        """Evaluate sequence components and join their return values."""
        results = []
        for elem in self.expr_comps:
            ret = await elem.eval(ctx)
            if ret is not None:
                results += str(ret)
        return "".join(results)


class ExprComp:
    """Expression composition AST node."""

    def __init__(self, parent=None, exprs=None):
        self.parent = parent
        self.exprs = exprs if exprs is not None else []

    def __eq__(self, other):
        return self.exprs == other.exprs

    async def eval(self, ctx):
        """Evaluate composition components, passing the return value of the
        previous expression to the input of the following commands."""
        data, result = None, None
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
    """Bot command AST node."""

    def __init__(self, parent=None, name=None, args=None):
        self.parent = parent
        self.name = name
        self.args = args if args is not None else []

    def __eq__(self, other):
        return self.name == other.name and self.args == other.args

    async def eval(self, ctx, pipe):
        """Execute the command by evaluating its arguments and calling its callback."""
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
    """String literal AST node."""

    def __init__(self, parent, value):
        self.parent = parent
        self.value = value

    def __eq__(self, other):
        return self.value == other.value

    async def eval(self, ctx, *_, **__):
        """Evaluate the literal, printing it in a code block if necessary."""
        if ctx.display:
            await ctx.send_pages(escape_md_block(self.value), fmt=MD_BLOCK_FMT)
        return self.value


class IntLiteral:
    """Integer literal AST node."""

    def __init__(self, parent, value):
        self.parent = parent
        self.value = value

    def __eq__(self, other):
        return self.value == other.value

    async def eval(self, *_, **__):
        """Evaluate the integer literal."""
        return self.value


class BoolLiteral:
    """Boolean literal AST node."""

    def __init__(self, parent, value):
        self.parent = parent
        self.value = value.lower() in ("yes", "true", "enable", "on")

    def __eq__(self, other):
        return self.value == other.value

    async def eval(self, *_, **__):
        """Evaluate the boolean literal."""
        return self.value


class FileContent:
    """Discord file content AST node."""

    def __init__(self, parent, name):
        self.parent = parent
        self.name = name

    def __eq__(self, other):
        return self.name == other.name

    async def eval(self, ctx, *_, **__):
        """Read file contents from the first attachment found in the current channel."""
        async for msg in ctx.history(limit=1000):
            for elem in msg.attachments:
                if elem.filename == self.name:
                    content = str(await elem.read(), errors="replace")
                    if ctx.display:
                        await ctx.send_pages(escape_md_block(content), fmt=MD_BLOCK_FMT)
                    return content
        raise commands.CommandError(f"File `{self.name}` not found")


class ExprSubst:
    """Expression substitution AST node."""

    def __init__(self, parent, expr_seq):
        self.parent = parent
        self.expr_seq = expr_seq

    def __eq__(self, other):
        return self.expr_seq == other.expr_seq

    async def eval(self, ctx, *_, **__):
        """Evaluate the sequence in the substitution."""
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
