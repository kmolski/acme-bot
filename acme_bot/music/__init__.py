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

import logging
import string
from asyncio import Queue, Lock
from concurrent.futures import ProcessPoolExecutor
from itertools import chain
from random import choices
from shutil import which

from discord import Embed
from discord.ext import commands
from yt_dlp import YoutubeDL

from acme_bot.autoloader import CogFactory, autoloaded
from acme_bot.config.properties import MUSIC_EXTRACTOR_MAX_WORKERS
from acme_bot.music.extractor import MusicExtractor
from acme_bot.music.player import MusicPlayer
from acme_bot.music.ui import ConfirmAddTracks, SelectTrack

log = logging.getLogger(__name__)


def display_entry(entry):
    """Display an entry with the duration in MM:SS format."""
    return "{}. **{title}** - {uploader} - {duration_string}".format(
        entry[0], **entry[1]
    )


def assemble_menu(header, entries):
    """Create a menu with the given header and information about the queue entries."""
    menu = header
    for entry in enumerate(entries, start=1):
        menu += f"\n{display_entry(entry)}"
    return menu


def export_entry(entry):
    """Export an entry string with the URL, title and duration."""
    return "{webpage_url}    {title} - {duration_string}".format(**entry)


def export_entry_list(*iterables):
    """Export entry iterables using export_entry."""
    lines = [export_entry(entry) for entry in chain.from_iterable(iterables)]
    lines.append("")
    return "\n".join(lines)


def strip_urls(urls):
    """Strip entry strings from their title and duration, leaving the URL."""
    return (line.split()[0] for line in urls.split("\n") if line)


@autoloaded
class MusicModule(commands.Cog, CogFactory):
    """Music player commands."""

    ACCESS_CODE_LENGTH = 6
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
    EMBED_COLOR = 0xFF0000

    def __init__(self, bot, extractor):
        self.__lock = Lock()
        self.__players = {}

        self.bot = bot
        self.extractor = extractor

    @classmethod
    def is_available(cls):
        if which("ffmpeg") is None:
            log.error("Cannot load MusicModule: FFMPEG executable not found!")
            return False

        return True

    @classmethod
    async def create_cog(cls, bot):
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
        while code := int("".join(choices(string.digits, k=self.ACCESS_CODE_LENGTH))):
            if not any(player.access_code == code for player in self.__players):
                return code
        assert False

    async def __delete_player(self, player):
        del self.__players[player.channel_id]
        self.bot.dispatch("acme_bot_player_deleted", player)
        log.info(
            "Deleted the MusicPlayer instance for Channel ID %s",
            player.channel_id,
        )
        await player.disconnect()

    @commands.Cog.listener("on_voice_state_update")
    async def _quit_channel_if_empty(self, _, before, after):
        """Leave voice channels that don't contain any human users."""
        prev = before.channel
        if prev is not None and after.channel is None:
            async with self.__lock:
                if prev.id in self.__players and all(user.bot for user in prev.members):
                    log.info("Voice channel ID %s is now empty, disconnecting", prev.id)
                    player = self.__players[prev.id]
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
        if ctx.display:
            await ctx.send(
                f"\u23CF Quitting voice channel **{ctx.voice_client.channel.name}**."
            )
        async with self.__lock, self.__get_player(ctx) as player:
            player.stop()
            head, tail = player.get_tracks()
            await self.__delete_player(player)
        return export_entry_list(head, tail)

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
            results = await self.extractor.get_entries_by_query("ytsearch8:", query)

        new = Queue()
        await ctx.send_pages(
            assemble_menu("\u2049\uFE0F Choose one of the following results:", results),
            view=SelectTrack(ctx.author, self.__get_player(ctx), new, results),
            reference=ctx.message,
        )

        new_entry = await new.get()
        return export_entry(new_entry)

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
            results = await self.extractor.get_entries_by_query("scsearch8:", query)

        new = Queue()
        await ctx.send_pages(
            assemble_menu("\u2049\uFE0F Choose one of the following results:", results),
            view=SelectTrack(ctx.author, self.__get_player(ctx), new, results),
            reference=ctx.message,
        )

        new_entry = await new.get()
        return export_entry(new_entry)

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
            results = await self.extractor.get_entries_by_urls(strip_urls(url_list))

        await ctx.send(
            f"\u2705 Extracted {len(results)} tracks.",
            view=ConfirmAddTracks(ctx.author, self.__get_player(ctx), results),
            reference=ctx.message,
        )
        return export_entry_list(results)

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
            results = await self.extractor.get_entries_by_urls(strip_urls(url_list))
        if ctx.display:
            await ctx.send(f"\u2705 Extracted {len(results)} tracks.")

        return export_entry_list(results)

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
            head, tail = player.get_tracks()
            if ctx.display:
                channel_name = ctx.voice_client.channel.name
                embed = Embed(
                    title=f"\U0001F3BC Track queue for channel '{channel_name}'",
                    description=f"Total tracks: {len(head) + len(tail)}",
                    color=self.EMBED_COLOR,
                )

                entries = (head + (tail if player.loop else []))[:10]
                for entry in enumerate(entries, start=1):
                    embed.add_field(name="", value=display_entry(entry), inline=False)
                await ctx.send(embed=embed)
            return export_entry_list(head, tail)

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
            head, tail = player.get_tracks()
            player.clear()
            if ctx.display:
                await ctx.send("\u2716 Queue cleared.")
            return export_entry_list(head, tail)

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
                embed = Embed(
                    title=f"\u25B6 Now playing: {current['title']}",
                    description=f"by {current['uploader']}",
                    color=self.EMBED_COLOR,
                    url=current["webpage_url"],
                )
                if "thumbnail" in current:
                    embed.set_thumbnail(url=current["thumbnail"])
                await ctx.send(embed=embed)
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
            removed = player.remove(offset - 1 if offset >= 1 else offset)
            if ctx.display:
                await ctx.send_pages(
                    "\u2796 **{title}** by {uploader} "
                    "removed from the queue.".format(**removed)
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

                async with self.__lock:
                    access_code = self.__generate_access_code()
                    player = MusicPlayer(ctx, self.extractor, access_code)

                    self.__players[player.channel_id] = player
                    self.bot.dispatch("acme_bot_player_created", player)

                await ctx.send(
                    f"\U0001F5DD The access code for this player is {access_code}."
                )
                log.info(
                    "Created a MusicPlayer instance with "
                    "access code %s for Channel ID %s",
                    access_code,
                    player.channel_id,
                )
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
