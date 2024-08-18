"""Music player commands."""

#  Copyright (C) 2019-2024  Krzysztof Molski
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
from itertools import chain
from random import choices

from discord import Embed
from discord.ext import commands
from wavelink import AutoPlayMode, Node, Playable, Player, Pool, QueueMode

from acme_bot.autoloader import CogFactory, autoloaded
from acme_bot.config.properties import (
    LAVALINK_URI,
    MUSIC_REMOTE_BASE_URL,
)
from acme_bot.convutils import to_int
from acme_bot.music.ui import (
    EMBED_COLOR,
    ConfirmAddTracks,
    SelectTrack,
    current_track_embed,
    remote_embed,
)
from acme_bot.textutils import format_duration

log = logging.getLogger(__name__)


def display_entry(entry):
    """Display an entry with the duration in MM:SS format."""
    index, track = entry
    duration_string = format_duration(track.length // 1000)
    return f"{index}. **{track.title}** - {track.author} - {duration_string}"


def assemble_menu(header, entries):
    """Create a menu with the given header and information about the queue entries."""
    lines = [header] + [display_entry(entry) for entry in enumerate(entries, start=1)]
    return "\n".join(lines)


def export_entry(entry):
    """Export an entry string with the URL, title and duration."""
    duration_string = format_duration(entry.length // 1000)
    return f"{entry.uri}    {entry.title} - {duration_string}\n"


def export_entry_list(queue):
    """Export entry iterables using export_entry."""
    return "".join(export_entry(entry) for entry in queue)


def strip_urls(urls):
    """Strip entry strings from their title and duration, leaving the URL."""
    return (line.split()[0] for line in urls.split("\n") if line)


@autoloaded
class MusicModule(commands.Cog, CogFactory):
    """Music player commands."""

    ACCESS_CODE_LENGTH = 6

    def __init__(self, bot):
        self.__lock = Lock()
        self.__players = {}
        self.__access_codes = {}
        self.__remote_id = None
        self.bot = bot

    @classmethod
    def is_available(cls):
        if LAVALINK_URI.get() is None:
            log.info("Cannot load MusicModule: LAVALINK_URI is not set")
            return False

        return True

    @classmethod
    async def create_cog(cls, bot):
        nodes = [
            Node(
                uri=str(LAVALINK_URI().with_user(None)),
                password=LAVALINK_URI().password,
            )
        ]
        await Pool.connect(nodes=nodes, client=bot)
        return cls(bot)

    async def cog_unload(self):
        await Pool.close()

    @commands.command()
    async def join(self, ctx):
        """Join the sender's current voice channel."""
        if ctx.display:
            await ctx.send(
                f"\u27A1\uFE0F Joining channel **{ctx.voice_client.channel.name}**."
            )

    @commands.command(aliases=["leav"])
    async def leave(self, ctx):
        """
        Leave the sender's current voice channel.

        RETURN VALUE
            The deleted track URLs as a string.
        """
        if ctx.display:
            await ctx.send(
                f"\u23CF\uFE0F Quitting channel **{ctx.voice_client.channel.name}**."
            )
        async with self.__lock:
            queue = ctx.voice_client.queue.copy()
            await self.__delete_player(ctx.voice_client)
        return export_entry_list(queue)

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
            results = await Playable.search(query, source="ytsearch:")

        new = Queue()
        await ctx.send_pages(
            assemble_menu("\u2049\uFE0F Choose one of the following results:", results),
            view=SelectTrack(ctx.author, ctx.voice_client, new, results),
            reference=ctx.message,
        )

        new_entry = await new.get()
        ctx.voice_client.notify()
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
            results = await Playable.search(query, source="scsearch:")

        new = Queue()
        await ctx.send_pages(
            assemble_menu("\u2049\uFE0F Choose one of the following results:", results),
            view=SelectTrack(ctx.author, ctx.voice_client, new, results),
            reference=ctx.message,
        )

        new_entry = await new.get()
        ctx.voice_client.notify()
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
            results = list(
                chain(*[await Pool.fetch_tracks(url) for url in strip_urls(url_list)])
            )
        await ctx.send(
            f"\u2705\uFE0F Extracted {len(results)} tracks.",
            view=ConfirmAddTracks(ctx.author, ctx.voice_client, results),
            reference=ctx.message,
        )
        ctx.voice_client.notify()
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
            results = list(
                chain(*[await Pool.fetch_tracks(url) for url in strip_urls(url_list)])
            )
        if ctx.display:
            await ctx.send(f"\u2705\uFE0F Extracted {len(results)} tracks.")
        return export_entry_list(results)

    @commands.command(aliases=["prev"])
    async def previous(self, ctx):
        """Play the previous track."""
        async with self.__lock:
            track = ctx.voice_client.queue.peek()
            if history := ctx.voice_client.queue.history:
                track = history[-1]
                if ctx.voice_client.current in history:
                    idx = history.index(ctx.voice_client.current)
                    track = history[idx - 1]
            await ctx.voice_client.play(track)
            ctx.voice_client.notify()

    @commands.command(aliases=["next"])
    async def skip(self, ctx):
        """Play the next track."""
        async with self.__lock:
            await ctx.voice_client.skip(force=True)
            ctx.voice_client.notify()

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
        async with self.__lock:
            queue = ctx.voice_client.queue
            queue.mode = QueueMode.loop_all if do_loop else QueueMode.normal
            ctx.voice_client.notify()
        if ctx.display:
            msg = "on" if do_loop else "off"
            await ctx.send(f"\U0001F501 Playlist loop {msg}.")
        return do_loop

    @commands.command(aliases=["paus"])
    async def pause(self, ctx):
        """Pause the player."""
        async with self.__lock:
            await ctx.voice_client.pause(True)
            ctx.voice_client.notify()
        if ctx.display:
            await ctx.send("\u23F8\uFE0F Paused.")

    @commands.command(aliases=["queu"])
    async def queue(self, ctx):
        """
        Show all tracks from the current queue.

        RETURN VALUE
            The track URLs as a string.
        """
        async with self.__lock:
            queue = ctx.voice_client.queue
            if ctx.display:
                channel_name = ctx.voice_client.channel.name
                embed = Embed(
                    title=f"\U0001F3BC Track queue for channel '{channel_name}'",
                    description=f"Total tracks: {len(queue)}",
                    color=EMBED_COLOR,
                )
                entries = queue[:10]
                for entry in enumerate(entries, start=1):
                    embed.add_field(name="", value=display_entry(entry), inline=False)
                await ctx.send(embed=embed)
            return export_entry_list(queue)

    @commands.command(aliases=["resu"])
    async def resume(self, ctx):
        """Resume playing the current track."""
        async with self.__lock:
            if not ctx.voice_client.playing:
                await ctx.voice_client.play(ctx.voice_client.queue.get())
            await ctx.voice_client.pause(False)
            ctx.voice_client.notify()

    @commands.command(aliases=["clea"])
    async def clear(self, ctx):
        """
        Delete all tracks from the queue.

        RETURN VALUE
            The removed track URLs as a string.
        """
        async with self.__lock:
            queue = export_entry_list(ctx.voice_client.queue)
            ctx.voice_client.queue.clear()
            ctx.voice_client.notify()
            if ctx.display:
                await ctx.send("\u2716\uFE0F Queue cleared.")
            return queue

    @commands.command(aliases=["volu"])
    async def volume(self, ctx, volume: int):
        """
        Change the current player volume.

        ARGUMENTS
            volume - the volume value (from 0 to 1000)

        RETURN VALUE
            The new volume value as an integer.
        """
        volume = to_int(volume)
        async with self.__lock:
            await ctx.voice_client.set_volume(volume)
            ctx.voice_client.notify()
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
        async with self.__lock:
            current = ctx.voice_client.current
            if current and ctx.display:
                await ctx.send(embed=current_track_embed(current))
            return export_entry(current) if current else None

    @commands.command(aliases=["remo"])
    async def remove(self, ctx, index: int):
        """
        Remove a track from the queue.

        ARGUMENTS
            index - index of the track to remove

        RETURN VALUE
            The removed track URL as a string.
        """
        index = to_int(index)
        index = index - 1 if index >= 1 else index
        async with self.__lock:
            removed = ctx.voice_client.queue[index]
            ctx.voice_client.queue.delete(index)
            ctx.voice_client.notify()
            if ctx.display:
                await ctx.send_pages(
                    f"\u2796 **{removed.title}** by {removed.author} "
                    "removed from the queue."
                )
            return export_entry(removed)

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

    @commands.Cog.listener("on_acme_bot_remote_id")
    async def _register_remote_id(self, remote_id):
        """Register the remote ID of the current instance."""
        async with self.__lock:
            self.__remote_id = remote_id
            log.debug("Registered RemoteControlModule with remote ID %s", remote_id)

    @commands.Cog.listener("on_wavelink_node_ready")
    async def _wavelink_ready(self, payload):
        log.info("Connected to Lavalink node at '%s'", payload.node.uri)

    @join.before_invoke
    @play.before_invoke
    @play_snd.before_invoke
    @play_url.before_invoke
    @volume.before_invoke
    async def _ensure_voice_or_join(self, ctx):
        """Ensure that the sender is in a voice channel,
        otherwise join the sender's voice channel."""

        if ctx.voice_client is None:
            if author_voice := ctx.author.voice:
                await author_voice.channel.connect(cls=Player)

                async with self.__lock:
                    access_code = self.__generate_access_code()
                    player = ctx.voice_client
                    player.notify = lambda: None
                    player.autoplay = AutoPlayMode.partial
                    player.queue.mode = QueueMode.loop_all

                    self.__players[player.channel.id] = player
                    self.__access_codes[player.channel.id] = access_code
                    self.bot.dispatch("acme_bot_player_created", player, access_code)

                if MUSIC_REMOTE_BASE_URL.get() is not None and self.__remote_id:
                    await ctx.send(
                        embed=remote_embed(
                            MUSIC_REMOTE_BASE_URL(), self.__remote_id, access_code
                        )
                    )
                log.info(
                    "Created MusicPlayer with access code %s for Channel ID %s",
                    access_code,
                    player.channel.id,
                )
            else:
                raise commands.CommandError("You are not connected to a voice channel.")

    @clear.before_invoke
    @current.before_invoke
    @leave.before_invoke
    @loop.before_invoke
    @pause.before_invoke
    @resume.before_invoke
    async def _ensure_voice_or_fail(self, ctx):
        """Ensure that the sender is in a voice channel, or throw
        an exception that will prevent the command from executing."""

        if ctx.voice_client is None:
            raise commands.CommandError("You are not connected to a voice channel.")

    @previous.before_invoke
    @queue.before_invoke
    @remove.before_invoke
    @skip.before_invoke
    async def _ensure_voice_and_non_empty_queue(self, ctx):
        """Ensure that the sender is in a voice channel, a MusicPlayer
        for that channel exists and the queue is not empty."""

        await self._ensure_voice_or_fail(ctx)
        async with self.__lock:
            if ctx.voice_client.queue.is_empty:
                raise commands.CommandError("The queue is empty!")

    def __generate_access_code(self):
        while code := int("".join(choices(string.digits, k=self.ACCESS_CODE_LENGTH))):
            if code not in self.__access_codes.values():
                return code
        assert False

    async def __delete_player(self, player):
        access_code = self.__access_codes.pop(player.channel.id)
        del self.__players[player.channel.id]
        log.info(
            "Deleted the MusicPlayer instance for Channel ID %s",
            player.channel.id,
        )
        await player.disconnect()
        player.notify()
        self.bot.dispatch("acme_bot_player_deleted", player, access_code)
