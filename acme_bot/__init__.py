"""Root module of the music bot."""
import argparse
import logging
from importlib.util import find_spec
from shutil import which

from discord import Intents
from discord.ext import commands
from textx.exceptions import TextXSyntaxError

from acme_bot.config import (
    COMMAND_PREFIX,
    LOG_LEVEL,
    DISCORD_TOKEN,
    load_config,
    RABBITMQ_URI,
)
from acme_bot.music import MusicModule
from acme_bot.shell import ShellModule
from acme_bot.external_control import ExternalControlModule
from acme_bot.version_info import VersionInfoModule


class HelpCommand(commands.DefaultHelpCommand):
    """This class provides a help command that works correctly with
    the shell interpreter."""

    # Catch the "display" keyword argument and ignore it
    # pylint: disable=arguments-differ
    async def command_callback(self, ctx, command=None, **_):
        # Defining this attribute is necessary for the help command to work
        # pylint: disable=attribute-defined-outside-init
        self.context = ctx
        return await super().command_callback(ctx, command=command)


def run():
    """The entry point for acme-bot."""
    parser = argparse.ArgumentParser(description="Launch the ACME Universal Bot.")
    parser.add_argument(
        "-c", "--config", metavar="FILE", help="path to bot configuration file"
    )

    args = vars(parser.parse_args())
    load_config(args.get("config"))

    intents = Intents.default()
    intents.message_content = True
    client = commands.Bot(
        command_prefix=COMMAND_PREFIX(), help_command=HelpCommand(), intents=intents
    )
    logging.basicConfig(
        format="[%(asctime)s] %(levelname)s: %(message)s", level=LOG_LEVEL()
    )

    async def load_cogs():
        if which("ffmpeg"):
            await client.add_cog(MusicModule(client))
        else:
            logging.error("FFMPEG executable not found! Disabling MusicModule.")

        if find_spec("aio_pika"):
            await client.add_cog(ExternalControlModule(client, RABBITMQ_URI()))
        else:
            logging.info(
                "External control not available! Disabling ExternalControlModule."
            )

        await client.add_cog(ShellModule(client))
        await client.add_cog(VersionInfoModule(client))

    client.setup_hook = load_cogs

    @client.event
    async def on_ready():
        """Prints a message to stdout once the bot has started."""
        logging.info("Connection is ready.")

    @client.event
    async def on_command_error(ctx, error):
        """Handles exceptions raised during command execution."""
        if isinstance(error, commands.CommandError) and hasattr(error, "original"):
            await ctx.send(f"Error: {error.original}")
        elif isinstance(error, TextXSyntaxError):
            await ctx.send(f"Syntax error: {error.message}")
        elif isinstance(error, TypeError):
            command = ctx.command
            await ctx.send(
                f"Error: {error}.\n"
                f"Command usage: `{command.qualified_name} {command.signature}`\n"
                f"For more information, refer to `!help {command.name}`."
            )
        else:
            await ctx.send(f"Error: {error}.")

    @client.event
    async def on_disconnect():
        """Handles the termination of connections to Discord servers."""
        # client.get_cog("MusicModule").pause_players()
        logging.warning("Connection closed, will attempt to reconnect.")

    @client.event
    async def on_resumed():
        """Handles restarts of connections to Discord servers."""
        # client.get_cog("MusicModule").resume_players()
        logging.info("Connection resumed.")

    async def eval_command(ctx):
        if ctx.invoked_with:
            message = ctx.message.content
            command = message.removeprefix(ctx.prefix)
            try:
                model = ShellModule.META_MODEL.model_from_str(command.strip())
                await model.eval(ctx)
            except (
                commands.CommandError,  # Explicitly thrown command errors
                TextXSyntaxError,  # Shell syntax errors
                TypeError,  # Type mismatch errors (incorrect command args)
            ) as exc:
                client.dispatch("command_error", ctx, exc)
            # Log the unhandled exceptions for later analysis
            # pylint: disable=broad-except
            except Exception as error:
                logging.exception(
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
        await eval_command(ctx)

    client.run(DISCORD_TOKEN())
