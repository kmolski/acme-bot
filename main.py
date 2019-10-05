#!/usr/bin/env python3
"""The entry point for the music bot."""
from os import environ
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
    # pylint: disable=arguments-differ
    async def command_callback(self, ctx, command=None, **_):
        return await super().command_callback(ctx, command=command)


if __name__ == "__main__":
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
        # TODO: Make this log all exceptions (with traceback and original message)!
        if isinstance(error, commands.CommandError):
            if hasattr(error, "original"):
                await ctx.send(f"Error: {error.original}")
            else:
                await ctx.send(f"Error: {error}")
        logging.exception(
            "Exception caused by message '%s':", ctx.message.content, exc_info=error
        )

    @CLIENT.event
    async def on_disconnect():
        # CLIENT.get_cog("MusicModule").pause_players()
        logging.warning("Connection closed, will attempt to reconnect.")

    @CLIENT.event
    async def on_resumed():
        # CLIENT.get_cog("MusicModule").resume_players()
        logging.info("Connection resumed.")

    CLIENT.add_cog(MusicModule(CLIENT))
    CLIENT.add_cog(ShellModule(CLIENT))

    CLIENT.run(get_token_from_env())
