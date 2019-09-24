"""This module provides music playback functionality to the bot."""
from asyncio import run_coroutine_threadsafe
from concurrent import futures
from functools import partial
from math import ceil
from random import shuffle
from threading import Lock

import youtube_dl

import discord
from discord.ext import commands

youtube_dl.utils.bug_reports_message = lambda: ""


class MusicQueue:
    def __init__(self):
        self.next_offset = 1
        self.__index = 0
        self.__playlist = []
        self.__lock = Lock()

    def add(self, elem):
        with self.__lock:
            self.__playlist.append(elem)

    def clear(self):
        with self.__lock:
            self.__playlist.clear()
            self.__index = 0

    def current(self):
        with self.__lock:
            return self.__playlist[self.__index]

    def next(self):
        with self.__lock:
            self.__index = (self.__index + self.next_offset) % len(self.__playlist)
            self.next_offset = 1
            return self.__playlist[self.__index]

    def on_first(self):
        with self.__lock:
            return self.__index == 0

    def on_rollover(self):
        with self.__lock:
            return (
                self.__playlist
                and self.next_offset == 1
                and self.__index >= len(self.__playlist) - 1
            )

    def pop(self, offset):
        with self.__lock:
            return self.__playlist.pop((self.__index + offset) % len(self.__playlist))

    def queue_data(self):
        with self.__lock:
            return (
                self.__playlist[self.__index :],
                self.__playlist[: self.__index],
                len(self.__playlist) - self.__index,
            )

    def shuffle(self):
        with self.__lock:
            shuffle(self.__playlist)


def format_queue_entry(index, entry):
    duration = ceil(entry["duration"])
    minutes, seconds = duration // 60, duration % 60
    return "\n{}. **{title}** - {uploader} - {}:{:02}".format(
        index, minutes, seconds, **entry
    )


class MusicPlayer(MusicQueue):
    FFMPEG_OPTIONS = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": "-vn -af dynaudnorm",
    }

    def __init__(self, ctx):
        super().__init__()
        self.__ctx = ctx
        self.__lock = Lock()
        self.__stopped = False
        self.__volume = 1.0
        self.loop = True

    def is_busy(self):
        with self.__lock:
            return (
                self.__ctx.voice_client.is_playing()
                or self.__ctx.voice_client.is_paused()
                or self.__stopped
            )

    def move(self, new_offset):
        with self.__lock:
            self.next_offset = new_offset
            if self.__ctx.voice_client.is_playing():
                self.__ctx.voice_client.stop()

    def set_volume(self, volume):
        with self.__lock:
            if volume in range(0, 101):
                self.__volume = volume / 100
                if self.__ctx.voice_client.source:
                    self.__ctx.voice_client.source.volume = volume / 100
            else:
                raise commands.CommandError("Incorrect volume value!")

    def stop(self):
        with self.__lock:
            self.__stopped = True
            self.__ctx.voice_client.stop()

    def remove(self, offset):
        with self.__lock:
            elem = self.pop(offset)
            if offset == 0:
                self.next_offset = 0
                self.__ctx.voice_client.stop()
            return elem

    async def resume(self):
        with self.__lock:
            if self.__ctx.voice_client.is_paused():
                self.__ctx.voice_client.resume()
                return "\u25B6 Playing **{title}** by {uploader}.".format(
                    **self.current()
                )
            if self.__stopped:
                self.__stopped = False
                await self.start_playing(self.current())
            else:
                raise commands.CommandError("This player is not paused!")

    def get_queue_info(self):
        entry_list = "\U0001F3BC Current queue:"
        head, tail, split = self.queue_data()
        for index, entry in enumerate(head):
            entry_list += format_queue_entry(index, entry)
        if not self.loop and not self.on_first():
            entry_list += "\n------------------------------------\n"
        for index, entry in enumerate(tail, start=split):
            entry_list += format_queue_entry(index, entry)
        return entry_list

    def get_queue_urls(self):
        url_list = ""
        head, tail, _ = self.queue_data()
        for entry in head:
            url_list += "{webpage_url}\n".format(**entry)
        for entry in tail:
            url_list += "{webpage_url}\n".format(**entry)
        return url_list

    def __play_next(self, err):
        if err:
            # TODO: Proper logging!
            print(f"ERROR: Playback ended with {err}!")
            return
        if self.on_rollover() and not self.loop and not self.__stopped:
            self.__stopped = True
            run_coroutine_threadsafe(
                self.__ctx.send("The queue is empty, resume to keep playing."),
                self.__ctx.bot.loop,
            ).result()
        current = self.next()
        if not self.__stopped:
            run_coroutine_threadsafe(
                self.start_playing(current), self.__ctx.bot.loop
            ).result()

    async def start_playing(self, current):
        audio = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(current["url"], **self.FFMPEG_OPTIONS),
            volume=self.__volume,
        )
        # TODO: Handle FFMPEG errors gracefully
        self.__ctx.voice_client.play(audio, after=self.__play_next)
        await self.__ctx.send(
            "\u25B6 Playing **{title}** by {uploader}.".format(**current)
        )


class MusicFinder(youtube_dl.YoutubeDL):

    FINDER_OPTIONS = {
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

    def __init__(self, loop):
        super().__init__(self.FINDER_OPTIONS)
        self.loop = loop

    async def get_entries_by_urls(self, url_list):
        results = []
        for url in url_list:
            result = await self.loop.run_in_executor(
                None, partial(self.extract_info, url, download=False)
            )
            if result and (result["extractor"] in ("youtube", "soundcloud")):
                results.append(result)
        if not results:
            raise ValueError("No videos found for the provided URL list!")
        return results

    async def get_entries_by_query(self, provider, query):
        results = await self.loop.run_in_executor(
            None, partial(self.extract_info, provider + query, download=False)
        )
        if not results or not results["entries"]:
            raise ValueError("No videos found for the provided query!")
        return list(filter(None.__ne__, results["entries"]))


def assemble_menu(header, entries):
    menu = header
    for index, entry in enumerate(entries):
        menu += "\n{}. **{title}** - {uploader}".format(index, **entry)
    return menu


def pred_select(ctx, results):
    def pred(msg):
        return (
            msg.channel == ctx.channel
            and msg.author == ctx.author
            and msg.content.isnumeric()
            and int(msg.content) in range(0, len(results))
        )

    return pred


def pred_confirm(ctx, menu_msg):
    def pred(resp, user):
        return (
            resp.message.id == menu_msg.id
            and user == ctx.author
            and resp.emoji in ("\u2714", "\u274C")
        )

    return pred


class MusicModule(commands.Cog):
    """This module handles commands related to playing music."""

    def __init__(self, bot):
        self.bot = bot
        self.__downloader = MusicFinder(bot.loop)
        self.__players = {}

    def __get_player(self, ctx):
        """Returns a MusicPlayer instance for the channel in the current context."""
        return self.__players[ctx.voice_client.channel.id]

    @commands.command()
    async def join(self, ctx, *, display=True):
        if display:
            await ctx.send(
                f"\u27A1 Joining the voice channel **{ctx.voice_client.channel.name}**."
            )

    @commands.command()
    async def leave(self, ctx, *, display=True):
        """Removes the bot from the channel in the current context."""
        self.__players.pop(ctx.voice_client.channel.id)
        ctx.voice_client.stop()
        await ctx.voice_client.disconnect()
        if display:
            await ctx.send("\u23CF Quitting the voice channel.")

    @commands.command()
    async def play(self, ctx, *query, display=True):
        """Searches for and plays a video from YouTube
        on the channel in the current context."""
        query = " ".join(query)
        async with ctx.typing():
            # Get video list for query
            results = await self.__downloader.get_entries_by_query("ytsearch10:", query)
            # Assemble and display menu
            menu_msg = await ctx.send(
                assemble_menu("\u2049 Choose one of the following results:", results)
            )

        try:
            response = await self.bot.wait_for(
                "message", check=pred_select(ctx, results), timeout=30.0
            )
        except futures.TimeoutError:
            await menu_msg.edit(content="\u231B *Action expired.*")
            return

        new = results[int(response.content)]

        player = self.__get_player(ctx)
        player.add(new)

        if not player.is_busy():
            await player.start_playing(new)
        elif display:
            await ctx.send(
                "\u2795 **{title}** by {uploader} added to the queue.".format(**new)
            )

        return new["webpage_url"]

    @commands.command(name="play-snd")
    async def play_snd(self, ctx, *query, display=True):
        """Searches for and plays a video from Soundcloud
        on the channel in the current context."""
        query = " ".join(query)
        async with ctx.typing():
            # Get video list for query
            results = await self.__downloader.get_entries_by_query("scsearch10:", query)
            # Assemble and display menu
            menu_msg = await ctx.send(
                assemble_menu("\u2049 Choose one of the following results:", results)
            )

        try:
            response = await self.bot.wait_for(
                "message", check=pred_select(ctx, results), timeout=30.0
            )
        except futures.TimeoutError:
            await menu_msg.edit(content="\u231B *Action expired.*")
            return

        new = results[int(response.content)]

        player = self.__get_player(ctx)
        player.add(new)

        if not player.is_busy():
            await player.start_playing(new)
        elif display:
            await ctx.send(
                "\u2795 **{title}** by {uploader} added to the queue.".format(**new)
            )

        return new["webpage_url"]

    @commands.command(name="play-url")
    async def play_url(self, ctx, url_list, *, display=True):
        """Plays a YouTube/Soundcloud track on
        the channel in the current context."""
        url_list = str(url_list)
        async with ctx.typing():
            # Get video list for the URL list
            results = await self.__downloader.get_entries_by_urls(url_list.split())
            # Assemble and display menu
            menu_msg = await ctx.send(
                assemble_menu("\u2049 Do you want to add this to the queue?", results)
            )
            await menu_msg.add_reaction("\u2714")
            await menu_msg.add_reaction("\u274C")

        try:
            response, _ = await self.bot.wait_for(
                "reaction_add", check=pred_confirm(ctx, menu_msg), timeout=30.0
            )
        except futures.TimeoutError:
            await menu_msg.edit(content="\u231B *Action expired.*")
            return

        if response.emoji == "\u274C":
            await menu_msg.edit(content="\u274C *Action cancelled.*")
            return

        await menu_msg.delete()

        player = self.__get_player(ctx)
        message = ""
        for elem in results:
            player.add(elem)
            if player.is_busy():
                message += "\n**{title}** by {uploader}".format(**elem)
            else:
                await player.start_playing(elem)

        if message and display:
            await ctx.send("\u2795 Videos added to the queue: " + message)

        return url_list

    @commands.command()
    async def back(self, ctx, offset: int = 1, **_):
        """Plays the previous video from the current queue
        based on the provided offset."""
        self.__get_player(ctx).move(-offset)

    @commands.command()
    async def forward(self, ctx, offset: int = 1, **_):
        """Plays the next video from the current queue
        based on the provided offset."""
        self.__get_player(ctx).move(offset)

    @commands.command()
    async def loop(self, ctx, should_loop: bool, *, display=True):
        """Sets looping behaviour of the current playlist."""
        self.__get_player(ctx).loop = should_loop
        msg = "on" if should_loop else "off"
        if display:
            await ctx.send(f"\U0001F501 Playlist loop {msg}.")
        return msg

    @commands.command()
    async def pause(self, ctx, *, display=True):
        """Pauses the player on the channel in the current context."""
        ctx.voice_client.pause()
        if display:
            await ctx.send("\u23F8 Paused.")

    @commands.command()
    async def queue(self, ctx, *, display=True):
        """Displays the queue of the channel in the current context."""
        player = self.__get_player(ctx)
        if display:
            await ctx.send(player.get_queue_info())
        return player.get_queue_urls()

    @commands.command()
    async def resume(self, ctx, *, display=True):
        """Resumes the player on the channel in the current context."""
        msg = await self.__get_player(ctx).resume()
        if msg and display:
            await ctx.send(msg)

    @commands.command()
    async def shuffle(self, ctx, *, display=True):
        """Shuffles the playlist of the channel in the current context."""
        self.__get_player(ctx).shuffle()
        if display:
            await ctx.send("\U0001F500 Queue shuffled.")

    @commands.command()
    async def clear(self, ctx, *, display=True):
        """Clear the playlist of the channel in the current context."""
        player = self.__get_player(ctx)
        player.stop()
        player.clear()
        if display:
            await ctx.send("\u2716 Queue cleared.")

    @commands.command()
    async def stop(self, ctx, *, display=True):
        """Stops the player on the channel in the current context."""
        self.__get_player(ctx).stop()
        if display:
            await ctx.send("\u23F9 Stopped.")

    @commands.command()
    async def volume(self, ctx, volume: int, *, display=True):
        """Changes the volume of the player on the channel in the current context."""
        self.__get_player(ctx).set_volume(volume)
        if display:
            await ctx.send(f"\U0001F4E2 Volume is now at **{volume}%**.")
        return str(volume)

    @commands.command()
    async def current(self, ctx, *, display=True):
        """Displays information about the video that is being played
        in the current context."""
        current = self.__get_player(ctx).current()
        if display:
            await ctx.send(
                "\u25B6 Playing **{title}** by {uploader} now.\n{webpage_url}".format(
                    **current
                )
            )
        return current["webpage_url"]

    @commands.command()
    async def remove(self, ctx, offset: int, *, display=True):
        """Removes a video from the music queue."""
        removed = self.__get_player(ctx).remove(offset)
        if display:
            await ctx.send(
                "\u2796 **{title}** by {uploader} removed from the playlist.".format(
                    **removed
                )
            )
        return removed["webpage_url"]

    @join.before_invoke
    @play.before_invoke
    @play_snd.before_invoke
    @play_url.before_invoke
    @volume.before_invoke
    async def ensure_voice_or_join(self, ctx):
        """Ensures that the author of the message is in a voice channel,
        otherwise joins the author's voice channel.
        """
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
                self.__players[ctx.voice_client.channel.id] = MusicPlayer(ctx)
            else:
                raise commands.CommandError("You are not connected to a voice channel.")

    @back.before_invoke
    @clear.before_invoke
    @current.before_invoke
    @forward.before_invoke
    @leave.before_invoke
    @loop.before_invoke
    @pause.before_invoke
    @queue.before_invoke
    @remove.before_invoke
    @resume.before_invoke
    @shuffle.before_invoke
    @stop.before_invoke
    async def ensure_voice_or_fail(self, ctx):
        """Ensures that the author of the message is in a voice channel,
        otherwise throws an exception that prevents the command from executing.
        """
        if ctx.voice_client is None:
            raise commands.CommandError("You are not connected to a voice channel.")
