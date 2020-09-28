"""Root module of the music bot."""
from os import environ
from shutil import which
import logging

from discord.ext import commands

from acme_bot.music import MusicModule
from acme_bot.shell import ShellModule


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

    # Catch the "display" keyword argument and ignore it
    # pylint: disable=arguments-differ
    async def command_callback(self, ctx, command=None, **_):
        self.context = ctx
        return await super().command_callback(ctx, command=command)


def run():
    """The entry point for acme-bot."""
    client = commands.Bot(command_prefix="!", help_command=HelpCommand())
    logging.basicConfig(
        format="[%(asctime)s] %(levelname)s: %(message)s", level=logging.INFO
    )

    @client.event
    async def on_ready():
        """Prints a message to stdout once the bot has started."""
        logging.info("Connection is ready.")

    @client.event
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

    if which("ffmpeg"):
        client.add_cog(MusicModule(client))
    else:
        logging.error("FFMPEG executable not found! Disabling MusicModule.")

    client.add_cog(ShellModule(client))

    client.run(get_token_from_env())
