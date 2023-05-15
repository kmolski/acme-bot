"""Music player commands."""
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

import asyncio
import logging
import string
from concurrent.futures import ProcessPoolExecutor
from itertools import chain
from random import choices
from shutil import which

from discord.ext import commands
from yt_dlp import YoutubeDL

from acme_bot.autoloader import CogFactory, autoloaded
from acme_bot.config.properties import MUSIC_EXTRACTOR_MAX_WORKERS
from acme_bot.music.extractor import MusicExtractor, add_expire_time
from acme_bot.music.player import MusicPlayer, PlayerState

log = logging.getLogger(__name__)


def assemble_menu(header, entries):
    """Create a menu with the given header and information about the queue entries."""
    menu = header
    for index, entry in enumerate(entries):
        menu += "\n{}. **{title}** - {uploader} - {duration_string}".format(
            index, **entry
        )
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


def display_entry(entry):
    """Display an entry with the duration in MM:SS format."""
    return "{}. **{title}** - {uploader} - {duration_string}".format(
        entry[0], **entry[1]
    )


def export_entry(entry):
    """Export an entry string with the URL, title and duration."""
    return "{webpage_url}    {title} - {duration_string}".format(**entry)


def format_entry_lists(fmt, *iterables, header=None):
    """Export entry iterables using the given formatting function."""
    lines = [header] * (header is not None)
    for entry in chain.from_iterable(iterables):
        lines.append(fmt(entry))
    lines.append("")
    return "\n".join(lines)


def extract_urls(urls):
    """Strip entry strings from their title and duration, leaving the URL."""
    return (line.split()[0] for line in urls.split("\n") if line)


@autoloaded
class MusicModule(commands.Cog, CogFactory):
    """Music player commands."""

    ACCESS_CODE_LENGTH = 6
    ACTION_TIMEOUT = 30.0

    DOWNLOAD_OPTIONS = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "nocheckcertificate": True,
        "ignoreerrors": True,
        "logtostderr": False,
        "quiet": True,
        "no_warnings": True,
        "default_search": "auto",
        "source_address": "0.0.0.0",
    }

    def __init__(self, bot, extractor):
        self.bot = bot
        self.extractor = extractor
        self.__players = {}
        self.players_by_code = {}

    @classmethod
    def is_available(cls):
        if which("ffmpeg") is None:
            log.error("Cannot load MusicModule: FFMPEG executable not found!")
            return False

        return True

    @classmethod
    def create_cog(cls, bot):
        executor = ProcessPoolExecutor(
            max_workers=MUSIC_EXTRACTOR_MAX_WORKERS.get(),
            initializer=MusicExtractor.init_downloader,
            initargs=(YoutubeDL, cls.DOWNLOAD_OPTIONS),
        )
        extractor = MusicExtractor(executor, bot.loop)
        return cls(bot, extractor)

    async def cog_unload(self):
        self.extractor.shutdown_executor()

    def __get_player(self, ctx):
        """Return a MusicPlayer instance for the channel in the current context."""
        return self.__players[ctx.voice_client.channel.id]

    def __generate_access_code(self):
        while code := "".join(choices(string.digits, k=self.ACCESS_CODE_LENGTH)):
            if code not in self.players_by_code:
                return code
        assert False

    async def __delete_player(self, player):
        del self.players_by_code[player.access_code]
        del self.__players[player.channel_id]
        log.info(
            "Deleted the MusicPlayer instance for Channel ID %s",
            player.channel_id,
        )
        await player.disconnect()

    @commands.Cog.listener("on_voice_state_update")
    async def _quit_channel_if_empty(self, _, before, after):
        """Leave voice channels that don't contain any other users."""
        if before.channel is not None and after.channel is None:
            if before.channel.members == [self.bot.user]:
                log.info(
                    "Voice channel ID %s is now empty, disconnecting",
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
        """
        Leave the sender's current voice channel.

        RETURN VALUE
            The deleted track URLs as a string.
        """
        async with self.__get_player(ctx) as player:
            player.stop()
            head, tail, _ = player.split_view()
            await self.__delete_player(player)
        if ctx.display:
            await ctx.send("\u23CF Quitting the voice channel.")
        return format_entry_lists(export_entry, head, tail)

    @commands.command()
    async def play(self, ctx, *query):
        """
        Search for and play a track from YouTube.

        ARGUMENTS
            query... - the search query

        RETURN VALUE
            The added track URL as a string.
        """
        query = " ".join(str(part) for part in query)
        async with ctx.typing():
            # Get video list for query
            results = await self.extractor.get_entries_by_query("ytsearch10:", query)
            # Assemble and display menu
            menu_msg = await ctx.send(
                assemble_menu("\u2049 Choose one of the following results:", results)
            )

        try:
            response = await self.bot.wait_for(
                "message", check=pred_select(ctx, results), timeout=self.ACTION_TIMEOUT
            )
        except asyncio.exceptions.TimeoutError:
            await menu_msg.edit(content="\u231B *Action expired.*")
            return

        new = results[int(response.content)]
        add_expire_time(new)  # Update the entry with its expiration time

        async with self.__get_player(ctx) as player:
            player.append(new)  # Add the new entry to the player's queue

            if player.state == PlayerState.IDLE:
                # If the player is not playing, paused or stopped, start playing
                await player.start_player(new)
            elif ctx.display:
                await ctx.send(
                    "\u2795 **{title}** by {uploader} added to the queue.".format(**new)
                )

        return export_entry(new)

    @commands.command(name="play-snd", aliases=["psnd"])
    async def play_snd(self, ctx, *query):
        """
        Search for and play a track from Soundcloud.

        ARGUMENTS
            query... - the search query

        RETURN VALUE
            The added track URL as a string.
        """
        query = " ".join(str(part) for part in query)
        async with ctx.typing():
            # Get video list for query
            results = await self.extractor.get_entries_by_query("scsearch10:", query)
            # Assemble and display menu
            menu_msg = await ctx.send(
                assemble_menu("\u2049 Choose one of the following results:", results)
            )

        try:
            response = await self.bot.wait_for(
                "message", check=pred_select(ctx, results), timeout=self.ACTION_TIMEOUT
            )
        except asyncio.exceptions.TimeoutError:
            await menu_msg.edit(content="\u231B *Action expired.*")
            return

        new = results[int(response.content)]
        add_expire_time(new)  # Update the entry with its expiration time

        async with self.__get_player(ctx) as player:
            player.append(new)  # Add the new entry to the player's queue

            if player.state == PlayerState.IDLE:
                # If the player is not playing, paused or stopped, start playing
                await player.start_player(new)
            elif ctx.display:
                await ctx.send(
                    "\u2795 **{title}** by {uploader} added to the queue.".format(**new)
                )

        return export_entry(new)

    @commands.command(name="play-url", aliases=["purl"])
    async def play_url(self, ctx, *urls):
        """
        Play YouTube/Soundcloud tracks from the given URLs.

        ARGUMENTS
            urls... - track URLs to play

        RETURN VALUE
            The added track URLs as a string.
        """
        url_list = "\n".join(str(url) for url in urls)
        async with ctx.typing():
            # Get the tracks from the given URL list
            results = await self.extractor.get_entries_by_urls(extract_urls(url_list))
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
        except asyncio.exceptions.TimeoutError:
            await menu_msg.edit(content="\u231B *Action expired.*")
            return

        if response.emoji == "\u274C":
            await menu_msg.edit(content="\u274C *Action cancelled.*")
            return

        await menu_msg.delete()
        if ctx.display:
            await ctx.send(f"\u2795 {len(results)} tracks added to the queue.")

        async with self.__get_player(ctx) as player:
            player.extend(results)  # Add the new entries to the player's queue

            for elem in results:
                add_expire_time(elem)  # Update the new entry with its expiration time
                if player.state == PlayerState.IDLE:
                    # If the player is not playing, paused or stopped, start playing
                    await player.start_player(elem)

        return format_entry_lists(export_entry, results)

    @commands.command(name="list-urls", aliases=["lurl"])
    async def list_urls(self, ctx, *urls):
        """
        Extract track URLs from the given playlists.

        ARGUMENTS
            urls... - playlist URLs to extract tracks from

        RETURN VALUE
            The extracted track URLs as a string.
        """
        url_list = "\n".join(str(url) for url in urls)
        async with ctx.typing():
            results = await self.extractor.get_entries_by_urls(extract_urls(url_list))
        if ctx.display:
            await ctx.send(f"\u2705 Extracted {len(results)} tracks.")

        return format_entry_lists(export_entry, results)

    @commands.command(aliases=["prev"])
    async def previous(self, ctx, offset: int = 1):
        """
        Go back the given number of tracks.

        ARGUMENTS
            offset - number of tracks to rewind (default: 1)
        """
        offset = int(offset)
        async with self.__get_player(ctx) as player:
            player.move(-offset)

    @commands.command(aliases=["next"])
    async def skip(self, ctx, offset: int = 1):
        """
        Skip the given number of tracks.

        ARGUMENTS
            offset - number of tracks to skip (default: 1)
        """
        offset = int(offset)
        async with self.__get_player(ctx) as player:
            player.move(offset)

    @commands.command()
    async def loop(self, ctx, do_loop: bool):
        """
        Set the looping behaviour of the player.

        ARGUMENTS
            do_loop - whether to loop after playing all tracks

        RETURN VALUE
            The loop parameter as a boolean.
        """
        do_loop = bool(do_loop)
        async with self.__get_player(ctx) as player:
            player.loop = do_loop
        if ctx.display:
            msg = "on" if do_loop else "off"
            await ctx.send(f"\U0001F501 Playlist loop {msg}.")
        return do_loop

    @commands.command()
    async def pause(self, ctx):
        """Pause the player."""
        async with self.__get_player(ctx) as player:
            player.pause()
        if ctx.display:
            await ctx.send("\u23F8 Paused.")

    @commands.command()
    async def queue(self, ctx):
        """
        Show all tracks from the current queue.

        RETURN VALUE
            The track URLs as a string.
        """
        async with self.__get_player(ctx) as player:
            head, tail, split = player.split_view()
            if ctx.display:
                queue_info = format_entry_lists(
                    display_entry,
                    enumerate(head),
                    enumerate(tail, start=split),
                    header="\U0001F3BC Current queue:",
                )
                await ctx.send_pages(queue_info)
            return format_entry_lists(export_entry, head, tail)

    @commands.command(aliases=["resu"])
    async def resume(self, ctx):
        """Resume playing the current track."""
        async with self.__get_player(ctx) as player:
            await player.resume()

    @commands.command()
    async def clear(self, ctx):
        """
        Delete all tracks from the queue.

        RETURN VALUE
            The removed track URLs as a string.
        """
        async with self.__get_player(ctx) as player:
            head, tail, _ = player.split_view()
            player.clear()
            if ctx.display:
                await ctx.send("\u2716 Queue cleared.")
            return format_entry_lists(export_entry, head, tail)

    @commands.command()
    async def stop(self, ctx):
        """Stop playing the current track."""
        async with self.__get_player(ctx) as player:
            player.stop()
        if ctx.display:
            await ctx.send("\u23F9 Stopped.")

    @commands.command(aliases=["volu"])
    async def volume(self, ctx, volume: int):
        """
        Change the current player volume.

        ARGUMENTS
            volume - the volume value (from 0 to 100)

        RETURN VALUE
            The new volume value as an integer.
        """
        volume = int(volume)
        async with self.__get_player(ctx) as player:
            player.volume = volume
        if ctx.display:
            await ctx.send(f"\U0001F4E2 Volume is now at **{volume}%**.")
        return volume

    @commands.command(aliases=["curr"])
    async def current(self, ctx):
        """
        Show information about the current track.

        RETURN VALUE
            The current track URL as a string.
        """
        async with self.__get_player(ctx) as player:
            current = player.current
            if ctx.display:
                await ctx.send(
                    "\u25B6 Playing **{title}** by {uploader} now."
                    "\n{webpage_url}".format(**current)
                )
            return export_entry(current)

    @commands.command(aliases=["remo"])
    async def remove(self, ctx, offset: int):
        """
        Remove a track from the queue.

        ARGUMENTS
            offset - offset of the track to remove

        RETURN VALUE
            The removed track URL as a string.
        """
        offset = int(offset)
        async with self.__get_player(ctx) as player:
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
    # pylint: disable=unused-private-member
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
                player = MusicPlayer(ctx, self.extractor, access_code)
                log.info(
                    "Created a MusicPlayer instance with "
                    "access code %s for Channel ID %s",
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
    # pylint: disable=unused-private-member
    async def __ensure_voice_or_fail(self, ctx):
        """Ensure that the sender is in a voice channel, or throw
        an exception that will prevent the command from executing."""

        if ctx.voice_client is None:
            raise commands.CommandError("You are not connected to a voice channel.")

    @current.before_invoke
    @previous.before_invoke
    @queue.before_invoke
    @remove.before_invoke
    @skip.before_invoke
    # pylint: disable=unused-private-member
    async def __ensure_voice_and_non_empty_queue(self, ctx):
        """Ensure that the sender is in a voice channel, a MusicPlayer
        for that channel exists and the queue is not empty."""

        await self.__ensure_voice_or_fail(ctx)
        if self.__get_player(ctx).is_empty():
            raise commands.CommandError("The queue is empty!")
