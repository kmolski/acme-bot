#!/usr/bin/env python3
"""The entry point for the music bot."""
from os import environ
from shutil import which
import logging

from discord.ext import commands

from music import MusicModule
from shell import ShellModule


def get_token_from_env():
    """Returns the Discord API token from an environment variable,
    or fails if it doesn't exist."""
    try:
        return environ["DISCORD_TOKEN"]
    except KeyError:
        logging.error(
            "Discord API token not found! "
            "Please provide the token in the DISCORD_TOKEN environment variable!"
        )
        raise


class HelpCommand(commands.DefaultHelpCommand):
    """This class provides a help command that works correctly with
    the shell interpreter."""

    # Here we have to catch the "display" keyword argument and ignore it
    # pylint: disable=arguments-differ
    async def command_callback(self, ctx, command=None, **_):
        return await super().command_callback(ctx, command=command)


def run():
    CLIENT = commands.Bot(command_prefix="!", help_command=HelpCommand())
    logging.basicConfig(
        format="[%(asctime)s] %(levelname)s: %(message)s", level=logging.INFO
    )

    @CLIENT.event
    async def on_ready():
        """Prints a message to stdout once the bot has started."""
        logging.info("Connection is ready.")

    @CLIENT.event
    async def on_command_error(ctx, error):
        """Handles exceptions raised during command execution."""
        if isinstance(error, commands.CommandError):
            if hasattr(error, "original"):
                await ctx.send(f"Error: {error.original}")
            else:
                await ctx.send(f"Error: {error}")
        else:
            logging.exception(
                "Exception caused by message '%s':", ctx.message.content, exc_info=error
            )

    @CLIENT.event
    async def on_disconnect():
        """Handles the termination of connections to Discord servers."""
        # CLIENT.get_cog("MusicModule").pause_players()
        logging.warning("Connection closed, will attempt to reconnect.")

    @CLIENT.event
    async def on_resumed():
        """Handles restarts of connections to Discord servers."""
        # CLIENT.get_cog("MusicModule").resume_players()
        logging.info("Connection resumed.")

    if which("ffmpeg"):
        CLIENT.add_cog(MusicModule(CLIENT))
    else:
        logging.error("FFMPEG executable not found! Disabling MusicModule.")

    CLIENT.add_cog(ShellModule(CLIENT))

    CLIENT.run(get_token_from_env())