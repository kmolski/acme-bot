#!/usr/bin/env python3
"""The entry point for the music bot."""
from os import environ
from discord.ext import commands

from music import MusicModule
from shell import ShellModule


def get_token_from_env():
    """Returns the Discord API token from an environment variable,
    or fails if it doesn't exist."""
    try:
        return environ["DISCORD_TOKEN"]
    except KeyError:
        raise KeyError(
            "Please provide the login token in the DISCORD_TOKEN environment variable!"
        )


if __name__ == "__main__":
    CLIENT = commands.Bot(command_prefix="!")

    @CLIENT.event
    async def on_ready():
        """Prints a message to stdout once the bot has started."""
        print("ACME Universal Bot started!")

    @CLIENT.event
    async def on_command_error(ctx, error):
        # TODO: Improve the command error handling
        # if isinstance(error, commands.Command)
        await ctx.send("An error occured: {}".format(error))

    @CLIENT.event
    async def on_disconnect():
        print("Disconnected!")

    @CLIENT.event
    async def on_resumed():
        print("Connection resumed!")

    CLIENT.add_cog(MusicModule(CLIENT))
    CLIENT.add_cog(ShellModule(CLIENT))

    CLIENT.run(get_token_from_env())
