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


class HelpCommand(commands.DefaultHelpCommand):
    # pylint: disable=arguments-differ
    async def command_callback(self, ctx, command=None, **_):
        return await super().command_callback(ctx, command=command)


if __name__ == "__main__":
    CLIENT = commands.Bot(command_prefix="!", help_command=HelpCommand())

    @CLIENT.event
    async def on_ready():
        """Prints a message to stdout once the bot has started."""
        print("ACME Universal Bot started!")

    @CLIENT.event
    async def on_command_error(ctx, error):
        # TODO: Make this log all exceptions (with traceback and original message)!
        if isinstance(error, commands.CommandError):
            if hasattr(error, "original"):
                await ctx.send(f"Error: {error.original}")
            else:
                await ctx.send(f"Error: {error}")

    @CLIENT.event
    async def on_disconnect():
        # CLIENT.get_cog("MusicModule").pause_players()
        print("Disconnected!")

    @CLIENT.event
    async def on_resumed():
        # CLIENT.get_cog("MusicModule").resume_players()
        print("Connection resumed!")

    CLIENT.add_cog(MusicModule(CLIENT))
    CLIENT.add_cog(ShellModule(CLIENT))

    CLIENT.run(get_token_from_env())
