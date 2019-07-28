#!/usr/bin/env python3
from os import environ
from discord.ext import commands

from music import MusicModule
# from shell import ShellModule

try:
    TOKEN = environ["DISCORD_TOKEN"]
except KeyError:
    print("Please provide the login token in the DISCORD_TOKEN environment variable!")
    raise

CLIENT = commands.Bot(command_prefix="!")


@CLIENT.event
async def on_ready():
    print("ACME Universal Bot started!")


CLIENT.add_cog(MusicModule(CLIENT))

CLIENT.run(TOKEN)
