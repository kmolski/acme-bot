"""Discord music bot with a custom shell language."""
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

import logging
from argparse import ArgumentParser
from datetime import datetime, timezone
from importlib import import_module
from pkgutil import iter_modules
from sys import modules

from discord import Intents
from discord.ext import commands
from textx.exceptions import TextXSyntaxError

from acme_bot.autoloader import get_autoloaded_cogs
from acme_bot.config import load_config
from acme_bot.config.properties import DISCORD_TOKEN, COMMAND_PREFIX, LOG_LEVEL
from acme_bot.shell import ShellModule


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
            datetime.fromtimestamp(record.created, timezone.utc)
            .astimezone()
            .isoformat(timespec="milliseconds")
        )


class HelpCommand(commands.DefaultHelpCommand):
    """The default help command modified to work with the shell interpreter."""

    # Declare `command` as positional, because the shell does not support keyword args
    # pylint: disable=arguments-differ
    async def command_callback(self, ctx, command=None):
        # Defining this attribute is necessary for the help command to work
        # pylint: disable=attribute-defined-outside-init
        self.context = ctx
        return await super().command_callback(ctx, command=command)


def import_submodules():
    """Import all submodules of `acme_bot`."""
    current_module = modules[__name__]
    for _, module_name, _ in iter_modules(current_module.__path__, f"{__name__}."):
        import_module(module_name)


def run():
    """The entry point for acme-bot."""
    parser = ArgumentParser(description="Launch the ACME Universal Bot.")
    parser.add_argument(
        "-c", "--config", metavar="FILE", help="path to bot configuration file"
    )

    args = vars(parser.parse_args())
    load_config(args.get("config"))

    client = commands.Bot(
        command_prefix=COMMAND_PREFIX(),
        help_command=HelpCommand(show_parameter_descriptions=False),
        intents=Intents.all(),
    )
    formatter = RFC3339Formatter(fmt="%(asctime)s %(levelname)8s %(name)s: %(message)s")
    handler = logging.StreamHandler()
    logger = logging.getLogger()

    handler.setFormatter(formatter)
    logger.setLevel(LOG_LEVEL())
    logger.addHandler(handler)

    async def load_cogs():
        import_submodules()
        for module_class in get_autoloaded_cogs():
            await module_class.load(client)

    client.setup_hook = load_cogs

    @client.event
    async def on_command_error(ctx, error):
        """Handle exceptions raised during command execution."""
        if isinstance(error, commands.CommandError) and hasattr(error, "original"):
            await ctx.send(f"Error: {error.original}")
        elif isinstance(error, TextXSyntaxError):
            await ctx.send(f"Syntax error: {error.message}")
        elif isinstance(error, TypeError):
            cmd = ctx.command
            await ctx.send(
                f"Error: {error}\n"
                f"Command usage: `{ctx.prefix}{cmd.qualified_name} {cmd.signature}`\n"
                f"For more information, refer to `{ctx.prefix}help {cmd.name}`."
            )
        else:
            await ctx.send(f"Error: {error}")

    @client.event
    async def on_disconnect():
        """Handle the termination of connections to Discord servers."""
        # client.get_cog("MusicModule").pause_players()
        logging.warning("Connection closed, will attempt to reconnect")

    @client.event
    async def on_resumed():
        """Handle restarts of connections to Discord servers."""
        # client.get_cog("MusicModule").resume_players()
        logging.info("Connection resumed")

    async def eval_command(ctx):
        if ctx.invoked_with:
            message = ctx.message.content
            command = message.removeprefix(ctx.prefix)
            try:
                model = ShellModule.META_MODEL.model_from_str(command.strip())
                await model.eval(ctx)
            except (
                commands.CommandError,  # Command validation errors
                TextXSyntaxError,  # Shell syntax errors
                TypeError,  # Type mismatch errors (incorrect command args)
            ) as exc:
                client.dispatch("command_error", ctx, exc)
            # Log the unhandled exceptions for later analysis
            # pylint: disable=broad-except
            except Exception as error:
                log.exception(
                    "Unhandled exception caused by message '%s':",
                    ctx.message.content,
                    exc_info=error,
                )
            else:
                client.dispatch("command_completion", ctx)

    @client.event
    async def on_message(message):
        if message.author.bot:
            return
        ctx = await client.get_context(message)
        ctx.display = True
        await eval_command(ctx)

    client.run(DISCORD_TOKEN(), log_handler=None)
