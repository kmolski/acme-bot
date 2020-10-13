"""This module provides the music playback capability to the bot."""
from concurrent import futures
from itertools import chain
from math import ceil
import logging

from discord.ext import commands

from acme_bot.music.downloader import MusicDownloader, add_expire_time
from acme_bot.music.player import MusicPlayer, PlayerState
from acme_bot.utils import split_message, MAX_MESSAGE_LENGTH


def assemble_menu(header, entries):
    """This function creates a menu with the given header
    and information about the queue entries."""
    menu = header
    for index, entry in enumerate(entries):
        menu += "\n{}. **{title}** - {uploader}".format(index, **entry)
    return menu


def pred_select(ctx, results):
    """This function creates a predicate function for use
    with wait_for and selections from a list."""

    def pred(msg):
        return (
            msg.channel == ctx.channel
            and msg.author == ctx.author
            and msg.content.isnumeric()
            and int(msg.content) in range(0, len(results))
        )

    return pred


def pred_confirm(ctx, menu_msg):
    """This function creates a predicate function for use
    with wait_for and confirmations."""

    def pred(resp, user):
        return (
            resp.message.id == menu_msg.id
            and user == ctx.author
            and resp.emoji in ("\u2714", "\u274C")
        )

    return pred


def get_entry_duration(entry):
    """Returns the duration of an YTDL entry as a tuple of (minutes, seconds)"""
    # The entry duration from YTDL is not always an integer
    duration = ceil(entry["duration"])
    return duration // 60, duration % 60


def display_entry(entry_data):
    """This function displays an entry with the duration in the MM:SS format."""
    minutes, seconds = get_entry_duration(entry_data[1])
    return "{}. **{title}** - {uploader} - {}:{:02}".format(
        entry_data[0], minutes, seconds, **entry_data[1]
    )


def export_entry(entry):
    """This function exports an entry string with the URL, title and duration."""
    minutes, seconds = get_entry_duration(entry)
    return "{webpage_url}    {title} - {}:{:02}".format(minutes, seconds, **entry)


def format_entry_lists(fmt, *iterables, init=None):
    """Exports many lists of entries using the given formatting function."""
    lines = [init] * (init is not None)
    for entry in chain.from_iterable(iterables):
        lines.append(fmt(entry))
    lines.append("")
    return "\n".join(lines)


def extract_urls(urls):
    """Strips entry strings from their title and duration, leaving the URL."""
    return (line.split()[0] for line in urls.split("\n") if line)


class MusicModule(commands.Cog):
    """This module is responsible for playing music and managing playlists."""

    ACTION_TIMEOUT = 30.0

    def __init__(self, bot):
        self.bot = bot
        self.downloader = MusicDownloader(bot.loop)
        self.__players = {}

    def __get_player(self, ctx):
        """Returns a MusicPlayer instance for the channel in the current context."""
        return self.__players[ctx.voice_client.channel.id]

    @commands.command()
    async def join(self, ctx, *, display=True):
        """Makes the bot join the user's current voice channel."""
        if display:
            await ctx.send(
                f"\u27A1 Joining voice channel **{ctx.voice_client.channel.name}**."
            )

    @commands.command()
    async def leave(self, ctx, *, display=True):
        """Removes the bot from the user's current voice channel."""
        with self.__get_player(ctx) as player:
            player.stop()
            head, tail, _ = player.queue_data()
        del self.__players[ctx.voice_client.channel.id]
        logging.info(
            "Deleted the MusicPlayer instance for Channel ID %s.",
            ctx.voice_client.channel.id,
        )
        await ctx.voice_client.disconnect()
        if display:
            await ctx.send("\u23CF Quitting the voice channel.")
        return format_entry_lists(export_entry, head, tail)

    @commands.command()
    async def play(self, ctx, *query, display=True):
        """Searches for and plays a track from YouTube."""
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
            elif display:
                await ctx.send(
                    "\u2795 **{title}** by {uploader} added to the queue.".format(**new)
                )

        return export_entry(new)

    @commands.command(name="play-snd")
    async def play_snd(self, ctx, *query, display=True):
        """Searches for and plays a track from Soundcloud."""
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
            elif display:
                await ctx.send(
                    "\u2795 **{title}** by {uploader} added to the queue.".format(**new)
                )

        return export_entry(new)

    @commands.command(name="play-url")
    async def play_url(self, ctx, *urls, display=True):
        """Plays a YouTube/Soundcloud track from the given URL."""
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
        if display:
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
    async def playlist_url(self, ctx, *urls, display=True):
        """Extracts track URLs from the given playlists."""
        url_list = "\n".join(str(url) for url in urls)
        async with ctx.typing():
            # Get the tracks from the given URL list
            results = await self.downloader.get_entries_by_urls(extract_urls(url_list))
        if display:
            await ctx.send(f"\u2705 Extracted {len(results)} tracks.")

        return format_entry_lists(export_entry, results)

    @commands.command(aliases=["prev"])
    async def previous(self, ctx, offset: int = 1, **_):
        """Plays the previous video from the queue."""
        offset = int(offset)
        with self.__get_player(ctx) as player:
            player.move(-offset)

    @commands.command(aliases=["next"])
    async def skip(self, ctx, offset: int = 1, **_):
        """Plays the next video from the queue."""
        offset = int(offset)
        with self.__get_player(ctx) as player:
            player.move(offset)

    @commands.command()
    async def loop(self, ctx, should_loop: bool, *, display=True):
        """Sets looping behaviour of the player."""
        should_loop = bool(should_loop)
        with self.__get_player(ctx) as player:
            player.loop = should_loop
        if display:
            msg = "on" if should_loop else "off"
            await ctx.send(f"\U0001F501 Playlist loop {msg}.")
        return msg

    @commands.command()
    async def pause(self, ctx, *, display=True):
        """Pauses the player."""
        with self.__get_player(ctx) as player:
            player.pause()
        if display:
            await ctx.send("\u23F8 Paused.")

    @commands.command()
    async def queue(self, ctx, *, display=True):
        """Displays the queue contents."""
        with self.__get_player(ctx) as player:
            head, tail, split = player.queue_data()
            if display:
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
    async def resume(self, ctx, *, display=True):
        """Resumes the player."""
        with self.__get_player(ctx) as player:
            msg = await player.resume()
            if msg and display:
                await ctx.send(msg)

    @commands.command()
    async def shuffle(self, ctx, *, display=True):
        """Shuffles the queue contents."""
        with self.__get_player(ctx) as player:
            player.shuffle()
        if display:
            await ctx.send("\U0001F500 Queue shuffled.")

    @commands.command()
    async def clear(self, ctx, *, display=True):
        """Deletes the queue contents."""
        with self.__get_player(ctx) as player:
            head, tail, _ = player.queue_data()
            player.clear()
            if display:
                await ctx.send("\u2716 Queue cleared.")
            return format_entry_lists(export_entry, head, tail)

    @commands.command()
    async def stop(self, ctx, *, display=True):
        """Stops the player."""
        with self.__get_player(ctx) as player:
            player.stop()
        if display:
            await ctx.send("\u23F9 Stopped.")

    @commands.command()
    async def volume(self, ctx, volume: int, *, display=True):
        """Changes the volume of the player."""
        volume = int(volume)
        with self.__get_player(ctx) as player:
            player.set_volume(volume)
        if display:
            await ctx.send(f"\U0001F4E2 Volume is now at **{volume}%**.")
        return str(volume)

    @commands.command()
    async def current(self, ctx, *, display=True):
        """Displays information about the current track."""
        with self.__get_player(ctx) as player:
            current = player.current()
            if display:
                await ctx.send(
                    "\u25B6 Playing **{title}** by {uploader} now."
                    "\n{webpage_url}".format(**current)
                )
            return export_entry(current)

    @commands.command()
    async def remove(self, ctx, offset: int, *, display=True):
        """Removes a track from the queue."""
        offset = int(offset)
        with self.__get_player(ctx) as player:
            removed = player.remove(offset)
            if display:
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
        """Ensures that the author of the message is in a voice channel,
        otherwise joins the author's voice channel.
        """
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
                logging.info(
                    "Created a MusicPlayer instance for Channel ID %s.",
                    ctx.voice_client.channel.id,
                )
                self.__players[ctx.voice_client.channel.id] = MusicPlayer(
                    ctx, self.downloader
                )
            else:
                raise commands.CommandError("You are not connected to a voice channel.")

    @clear.before_invoke
    @leave.before_invoke
    @loop.before_invoke
    @pause.before_invoke
    @resume.before_invoke
    @stop.before_invoke
    async def __ensure_voice_or_fail(self, ctx):
        """Ensures that the author of the message is in a voice channel,
        otherwise throws an exception that prevents the command from executing.
        """
        if ctx.voice_client is None:
            raise commands.CommandError("You are not connected to a voice channel.")

    @current.before_invoke
    @previous.before_invoke
    @queue.before_invoke
    @remove.before_invoke
    @shuffle.before_invoke
    @skip.before_invoke
    async def __ensure_voice_and_non_empty_queue(self, ctx):
        """Ensures that the author of the message is in a voice channel,
        a MusicPlayer for that channel exists and the queue is not empty."""
        await self.__ensure_voice_or_fail(ctx)
        if self.__get_player(ctx).is_empty():
            raise commands.CommandError("The queue is empty!")
