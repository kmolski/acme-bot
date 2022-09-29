"""This module provides the music playback capability to the bot."""
import logging
import string
from concurrent import futures
from itertools import chain
from math import ceil
from random import choices
from shutil import which

from discord.ext import commands

from acme_bot.autoloader import CogFactory, autoloaded
from acme_bot.music.downloader import MusicDownloader, add_expire_time
from acme_bot.music.player import MusicPlayer, PlayerState
from acme_bot.textutils import split_message, MAX_MESSAGE_LENGTH


def assemble_menu(header, entries):
    """Create a menu with the given header and information about the queue entries."""
    menu = header
    for index, entry in enumerate(entries):
        menu += "\n{}. **{title}** - {uploader}".format(index, **entry)
    return menu


def pred_select(ctx, results):
    """Create a predicate function for use with wait_for and selections from a list."""

    def pred(msg):
        return (
            msg.channel == ctx.channel
            and msg.author == ctx.author
            and msg.content.isnumeric()
            and (0 <= int(msg.content) < len(results))
        )

    return pred


def pred_confirm(ctx, menu_msg):
    """Create a predicate function for use with wait_for and confirmations."""

    def pred(resp, user):
        return (
            resp.message.id == menu_msg.id
            and user == ctx.author
            and resp.emoji in ("\u2714", "\u274C")
        )

    return pred


def get_entry_duration(entry):
    """Return the duration of an YTDL entry as a tuple of (minutes, seconds)"""
    duration = ceil(entry["duration"])  # The YTDL duration is not always an integer
    return duration // 60, duration % 60


def display_entry(entry_data):
    """Display an entry with the duration in MM:SS format."""
    minutes, seconds = get_entry_duration(entry_data[1])
    return "{}. **{title}** - {uploader} - {}:{:02}".format(
        entry_data[0], minutes, seconds, **entry_data[1]
    )


def export_entry(entry):
    """Export an entry string with the URL, title and duration."""
    minutes, seconds = get_entry_duration(entry)
    return "{webpage_url}    {title} - {}:{:02}".format(minutes, seconds, **entry)


def format_entry_lists(fmt, *iterables, init=None):
    """Export entry iterables using the given formatting function."""
    lines = [init] * (init is not None)
    for entry in chain.from_iterable(iterables):
        lines.append(fmt(entry))
    lines.append("")
    return "\n".join(lines)


def extract_urls(urls):
    """Strip entry strings from their title and duration, leaving the URL."""
    return (line.split()[0] for line in urls.split("\n") if line)


@autoloaded
class MusicModule(commands.Cog, CogFactory):
    """This module is responsible for playing music and managing playlists."""

    ACCESS_CODE_LENGTH = 6
    ACTION_TIMEOUT = 30.0

    def __init__(self, bot, downloader):
        self.bot = bot
        self.downloader = downloader
        self.__players = {}
        self.players_by_code = {}

    @classmethod
    def is_available(cls):
        if which("ffmpeg") is None:
            logging.error("FFMPEG executable not found! Disabling MusicModule.")
            return False

        return True

    @classmethod
    def create_cog(cls, bot):
        downloader = MusicDownloader(bot.loop)
        return cls(bot, downloader)

    def __get_player(self, ctx):
        """Return a MusicPlayer instance for the channel in the current context."""
        return self.__players[ctx.voice_client.channel.id]

    def __generate_access_code(self):
        while code := "".join(choices(string.digits, k=self.ACCESS_CODE_LENGTH)):
            if code not in self.players_by_code:
                return code

    async def __delete_player(self, player):
        del self.players_by_code[player.access_code]
        del self.__players[player.channel_id]
        logging.info(
            "Deleted the MusicPlayer instance for Channel ID %s.",
            player.channel_id,
        )
        await player.disconnect()

    @commands.Cog.listener()
    async def on_voice_state_update(self, _, before, after):
        """Leave voice channels that don't contain any other users."""
        if before.channel is not None and after.channel is None:
            if before.channel.members == [self.bot.user]:
                logging.info(
                    "Voice channel ID %s is now empty, disconnecting.",
                    before.channel.id,
                )
                player = self.__players[before.channel.id]
                await self.__delete_player(player)

    @commands.command()
    async def join(self, ctx):
        """Join the sender's current voice channel."""
        if ctx.display:
            await ctx.send(
                f"\u27A1 Joining voice channel **{ctx.voice_client.channel.name}**."
            )

    @commands.command()
    async def leave(self, ctx):
        """Leave the sender's current voice channel."""
        with self.__get_player(ctx) as player:
            player.stop()
            head, tail, _ = player.queue_data()
            await self.__delete_player(player)
        if ctx.display:
            await ctx.send("\u23CF Quitting the voice channel.")
        return format_entry_lists(export_entry, head, tail)

    @commands.command()
    async def play(self, ctx, *query):
        """Search for and play a track from YouTube."""
        query = " ".join(str(part) for part in query)
        async with ctx.typing():
            # Get video list for query
            results = await self.downloader.get_entries_by_query("ytsearch10:", query)
            # Assemble and display menu
            menu_msg = await ctx.send(
                assemble_menu("\u2049 Choose one of the following results:", results)
            )

        try:
            response = await self.bot.wait_for(
                "message", check=pred_select(ctx, results), timeout=self.ACTION_TIMEOUT
            )
        except futures.TimeoutError:
            await menu_msg.edit(content="\u231B *Action expired.*")
            return

        new = results[int(response.content)]
        add_expire_time(new)  # Update the entry with its expiration time

        with self.__get_player(ctx) as player:
            player.append(new)  # Add the new entry to the player's queue

            if player.state == PlayerState.IDLE:
                # If the player is not playing, paused or stopped, start playing
                await player.start_player(new)
            elif ctx.display:
                await ctx.send(
                    "\u2795 **{title}** by {uploader} added to the queue.".format(**new)
                )

        return export_entry(new)

    @commands.command(name="play-snd")
    async def play_snd(self, ctx, *query):
        """Search for and play a track from Soundcloud."""
        query = " ".join(str(part) for part in query)
        async with ctx.typing():
            # Get video list for query
            results = await self.downloader.get_entries_by_query("scsearch10:", query)
            # Assemble and display menu
            menu_msg = await ctx.send(
                assemble_menu("\u2049 Choose one of the following results:", results)
            )

        try:
            response = await self.bot.wait_for(
                "message", check=pred_select(ctx, results), timeout=self.ACTION_TIMEOUT
            )
        except futures.TimeoutError:
            await menu_msg.edit(content="\u231B *Action expired.*")
            return

        new = results[int(response.content)]
        add_expire_time(new)  # Update the entry with its expiration time

        with self.__get_player(ctx) as player:
            player.append(new)  # Add the new entry to the player's queue

            if player.state == PlayerState.IDLE:
                # If the player is not playing, paused or stopped, start playing
                await player.start_player(new)
            elif ctx.display:
                await ctx.send(
                    "\u2795 **{title}** by {uploader} added to the queue.".format(**new)
                )

        return export_entry(new)

    @commands.command(name="play-url")
    async def play_url(self, ctx, *urls):
        """Play a YouTube/Soundcloud track from the given URL."""
        url_list = "\n".join(str(url) for url in urls)
        async with ctx.typing():
            # Get the tracks from the given URL list
            results = await self.downloader.get_entries_by_urls(extract_urls(url_list))
            # Assemble and display menu
            menu_msg = await ctx.send(
                f"\u2049 Do you want to add {len(results)} tracks to the queue?"
            )
            # Add the reactions used to confirm or cancel the action
            await menu_msg.add_reaction("\u2714")
            await menu_msg.add_reaction("\u274C")

        try:
            response, _ = await self.bot.wait_for(
                "reaction_add",
                check=pred_confirm(ctx, menu_msg),
                timeout=self.ACTION_TIMEOUT,
            )
        except futures.TimeoutError:
            await menu_msg.edit(content="\u231B *Action expired.*")
            return

        if response.emoji == "\u274C":
            await menu_msg.edit(content="\u274C *Action cancelled.*")
            return

        await menu_msg.delete()
        if ctx.display:
            await ctx.send(f"\u2795 {len(results)} tracks added to the queue.")

        with self.__get_player(ctx) as player:
            player.extend(results)  # Add the new entries to the player's queue

            for elem in results:
                add_expire_time(elem)  # Update the new entry with its expiration time
                if player.state == PlayerState.IDLE:
                    # If the player is not playing, paused or stopped, start playing
                    await player.start_player(elem)

        return format_entry_lists(export_entry, results)

    @commands.command(name="playlist-url")
    async def playlist_url(self, ctx, *urls):
        """Extract track URLs from the given playlists."""
        url_list = "\n".join(str(url) for url in urls)
        async with ctx.typing():
            # Get the tracks from the given URL list
            results = await self.downloader.get_entries_by_urls(extract_urls(url_list))
        if ctx.display:
            await ctx.send(f"\u2705 Extracted {len(results)} tracks.")

        return format_entry_lists(export_entry, results)

    @commands.command(aliases=["prev"])
    async def previous(self, ctx, offset: int = 1):
        """Play the previous video from the queue."""
        offset = int(offset)
        with self.__get_player(ctx) as player:
            player.move(-offset)

    @commands.command(aliases=["next"])
    async def skip(self, ctx, offset: int = 1):
        """Play the next video from the queue."""
        offset = int(offset)
        with self.__get_player(ctx) as player:
            player.move(offset)

    @commands.command()
    async def loop(self, ctx, should_loop: bool):
        """Set the looping behaviour of the player."""
        should_loop = bool(should_loop)
        with self.__get_player(ctx) as player:
            player.loop = should_loop
        if ctx.display:
            msg = "on" if should_loop else "off"
            await ctx.send(f"\U0001F501 Playlist loop {msg}.")
        return msg

    @commands.command()
    async def pause(self, ctx):
        """Pause the player."""
        with self.__get_player(ctx) as player:
            player.pause()
        if ctx.display:
            await ctx.send("\u23F8 Paused.")

    @commands.command()
    async def queue(self, ctx):
        """Display the queue contents."""
        with self.__get_player(ctx) as player:
            head, tail, split = player.queue_data()
            if ctx.display:
                queue_info = format_entry_lists(
                    display_entry,
                    enumerate(head),
                    enumerate(tail, start=split),
                    init="\U0001F3BC Current queue:",
                )
                for chunk in split_message(queue_info, MAX_MESSAGE_LENGTH):
                    await ctx.send(chunk)
            return format_entry_lists(export_entry, head, tail)

    @commands.command()
    async def resume(self, ctx):
        """Resume the player."""
        with self.__get_player(ctx) as player:
            msg = await player.resume()
            if msg and ctx.display:
                await ctx.send(msg)

    @commands.command()
    async def shuffle(self, ctx):
        """Shuffle the queue contents."""
        with self.__get_player(ctx) as player:
            player.shuffle()
        if ctx.display:
            await ctx.send("\U0001F500 Queue shuffled.")

    @commands.command()
    async def clear(self, ctx):
        """Delete the queue contents."""
        with self.__get_player(ctx) as player:
            head, tail, _ = player.queue_data()
            player.clear()
            if ctx.display:
                await ctx.send("\u2716 Queue cleared.")
            return format_entry_lists(export_entry, head, tail)

    @commands.command()
    async def stop(self, ctx):
        """Stop the player."""
        with self.__get_player(ctx) as player:
            player.stop()
        if ctx.display:
            await ctx.send("\u23F9 Stopped.")

    @commands.command()
    async def volume(self, ctx, volume: int):
        """Change the volume of the player."""
        volume = int(volume)
        with self.__get_player(ctx) as player:
            player.set_volume(volume)
        if ctx.display:
            await ctx.send(f"\U0001F4E2 Volume is now at **{volume}%**.")
        return str(volume)

    @commands.command()
    async def current(self, ctx):
        """Display information about the current track."""
        with self.__get_player(ctx) as player:
            current = player.current()
            if ctx.display:
                await ctx.send(
                    "\u25B6 Playing **{title}** by {uploader} now."
                    "\n{webpage_url}".format(**current)
                )
            return export_entry(current)

    @commands.command()
    async def remove(self, ctx, offset: int):
        """Remove a track from the queue."""
        offset = int(offset)
        with self.__get_player(ctx) as player:
            removed = player.remove(offset)
            if ctx.display:
                await ctx.send(
                    "\u2796 **{title}** by {uploader} "
                    "removed from the playlist.".format(**removed)
                )
            return export_entry(removed)

    @join.before_invoke
    @play.before_invoke
    @play_snd.before_invoke
    @play_url.before_invoke
    @volume.before_invoke
    async def __ensure_voice_or_join(self, ctx):
        """Ensure that the sender is in a voice channel,
        otherwise join the sender's voice channel."""

        if ctx.voice_client is None:
            if author_voice := ctx.author.voice:
                await author_voice.channel.connect()

                access_code = self.__generate_access_code()
                await ctx.send(
                    f"\U0001F5DD The access code for this player is {access_code}."
                )

                channel_id = ctx.voice_client.channel.id
                player = MusicPlayer(ctx, self.downloader, access_code)
                logging.info(
                    "Created a MusicPlayer instance with "
                    "access code %s for Channel ID %s.",
                    access_code,
                    channel_id,
                )

                self.__players[channel_id] = player
                self.players_by_code[access_code] = player
            else:
                raise commands.CommandError("You are not connected to a voice channel.")

    @clear.before_invoke
    @leave.before_invoke
    @loop.before_invoke
    @pause.before_invoke
    @resume.before_invoke
    @stop.before_invoke
    async def __ensure_voice_or_fail(self, ctx):
        """Ensure that the sender is in a voice channel, or throw
        an exception that prevents the command from executing."""

        if ctx.voice_client is None:
            raise commands.CommandError("You are not connected to a voice channel.")

    @current.before_invoke
    @previous.before_invoke
    @queue.before_invoke
    @remove.before_invoke
    @shuffle.before_invoke
    @skip.before_invoke
    async def __ensure_voice_and_non_empty_queue(self, ctx):
        """Ensure that the sender is in a voice channel, a MusicPlayer
        for that channel exists and the queue is not empty."""

        await self.__ensure_voice_or_fail(ctx)
        if self.__get_player(ctx).is_empty():
            raise commands.CommandError("The queue is empty!")
