"""Discord music bot with a custom shell language."""

#  Copyright (C) 2019-2025  Krzysztof Molski
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

import logging
from argparse import ArgumentParser
from datetime import datetime, UTC
from functools import partial
from importlib import import_module
from pkgutil import walk_packages
from sys import modules

from discord import Intents
from discord.ext import commands
from textx.exceptions import TextXSyntaxError

from acme_bot.autoloader import get_autoloaded_cogs
from acme_bot.config import load_config
from acme_bot.config.properties import DISCORD_TOKEN, COMMAND_PREFIX, LOG_LEVEL
from acme_bot.shell.interpreter import META_MODEL
from acme_bot.textutils import send_pages

log = logging.getLogger(__name__)


class RFC3339Formatter(logging.Formatter):
    """
    Log formatter using RFC 3339 compliant timestamps.

    The timestamp format is documented here:
    https://datatracker.ietf.org/doc/html/rfc3339#section-5.6
    """

    def formatTime(self, record, datefmt=None):
        """Format the creation datetime using the RFC 3339 format."""
        return (
            datetime.fromtimestamp(record.created, UTC)
            .astimezone()
            .isoformat(timespec="milliseconds")
        )


class HelpCommand(commands.DefaultHelpCommand):
    """The default help command modified to work with the shell interpreter."""

    # Declare `command` as positional, because the shell does not support keyword args
    async def command_callback(self, ctx, command=None):
        self.context = ctx
        return await super().command_callback(ctx, command=command)


def import_submodules():
    """Import all submodules of acme_bot."""
    current_module = modules[__name__]
    for _, module_name, _ in walk_packages(current_module.__path__, f"{__name__}."):
        import_module(module_name)


class AcmeBot(commands.Bot):
    """The main bot class."""

    async def setup_hook(self):
        import_submodules()
        for module_class in get_autoloaded_cogs():
            await module_class.load(self)

    async def eval_command(self, ctx):
        """Evaluate a command in the given context."""
        if ctx.invoked_with:
            message = ctx.message.content
            command = message.removeprefix(ctx.prefix)
            try:
                model = META_MODEL.model_from_str(command.strip())
                await model.eval(ctx)
            except (
                commands.CommandError,  # Command validation errors
                TextXSyntaxError,  # Shell syntax errors
                TypeError,  # Type mismatch errors (incorrect command args)
            ) as exc:
                self.dispatch("command_error", ctx, exc)
            # Log the unhandled exceptions for later analysis
            except Exception as exc:
                log.exception(
                    "Unhandled exception caused by message '%s':",
                    ctx.message.content,
                    exc_info=exc,
                )
            else:
                self.dispatch("command_completion", ctx)

    async def on_message(self, message, /):
        if message.author.bot:
            return
        ctx = await self.get_context(message)
        ctx.display = True
        ctx.send_pages = partial(send_pages, ctx)
        await self.eval_command(ctx)

    async def on_command_error(self, ctx, error, /):
        """Handle exceptions raised during command execution."""
        match error:
            case commands.CommandError(original=_):
                await ctx.send_pages(f"Error: {error.original}")
            case TextXSyntaxError():
                await ctx.send_pages(f"Syntax error: {error.message}")
            case TypeError() | ValueError():
                cmd = ctx.command
                await ctx.send_pages(
                    f"Error: {error}\n"
                    f"Command usage: `{ctx.prefix}{cmd.name} {cmd.signature}`\n"
                    f"For more information, refer to `{ctx.prefix}help {cmd.name}`."
                )
            case _:
                await ctx.send_pages(f"Error: {error}")


def run():
    """The entry point for acme-bot."""
    parser = ArgumentParser(description="Launch the ACME Universal Bot.")
    parser.add_argument(
        "-c", "--config", metavar="FILE", help="path to bot configuration file"
    )

    args = vars(parser.parse_args())
    load_config(args.get("config"))

    formatter = RFC3339Formatter(fmt="%(asctime)s %(levelname)8s %(name)s: %(message)s")
    handler = logging.StreamHandler()
    logger = logging.getLogger()

    handler.setFormatter(formatter)
    logger.setLevel(LOG_LEVEL())
    logger.addHandler(handler)

    intents = Intents.default()
    intents.message_content = True
    client = AcmeBot(
        command_prefix=COMMAND_PREFIX(),
        help_command=HelpCommand(show_parameter_descriptions=False),
        intents=intents,
    )
    client.run(DISCORD_TOKEN(), log_handler=None)
