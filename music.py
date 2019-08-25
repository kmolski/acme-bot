"""This module provides music playback functionality to the bot."""
from asyncio import run_coroutine_threadsafe
from concurrent import futures
from math import ceil
from random import shuffle

import youtube_dl

import discord
from discord.ext import commands

youtube_dl.utils.bug_reports_message = lambda: ""


class MusicQueue:
    def __init__(self):
        self.__index = 0
        self.__offset = 1
        self.__playlist = []

    @property
    def current(self):
        return self.__playlist[self.__index]

    @property
    def index(self):
        return self.__index

    @property
    def next(self):
        self.__index = (self.__index + self.__offset) % len(self.__playlist)
        self.__offset = 1
        return self.__playlist[self.__index]

    @property
    def on_last(self):
        return self.__playlist and self.__index >= len(self.__playlist) - 1

    @property
    def playlist(self):
        return self.__playlist

    def add(self, elem):
        self.__playlist.append(elem)

    def clear(self):
        self.__playlist.clear()
        self.__index = 0

    def pop(self, offset):
        return self.__playlist.pop((self.__index + offset) % len(self.__playlist))

    def set_offset(self, new_offset):
        self.__offset = new_offset

    def shuffle(self):
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

    def __init__(self, event_loop, voice_client, text_channel):
        super().__init__()
        self.__event_loop = event_loop
        self.__voice_client = voice_client
        self.__text_channel = text_channel
        self.__stopped = False
        self.__volume = 1.0
        self.loop = True

    @property
    def stopped(self):
        return self.__stopped

    @property
    def volume(self):
        return self.__volume

    @volume.setter
    def volume(self, volume):
        if volume in range(0, 101):
            self.__volume = volume / 100
        if self.__voice_client.source:
                self.__voice_client.source.volume = volume / 100
        else:
            raise commands.CommandError("Incorrect volume value!")

    def move(self, offset):
        self.set_offset(offset)
        if self.__voice_client.is_playing():
            self.__voice_client.stop()

    def stop(self):
        self.__stopped = True
        self.__voice_client.stop()

    def remove(self, offset):
        elem = self.pop(offset)
        if offset == 0:
            self.set_offset(0)
            self.__voice_client.stop()
        return elem

    async def resume(self):
        if self.__voice_client.is_paused():
            self.__voice_client.resume()
            await self.__text_channel.send(
                "\u25B6 Playing **{title}** by {uploader}.".format(**self.current)
            )
        elif self.__stopped:
            self.__stopped = False
            await self.start_playing(self.current)
        else:
            raise commands.CommandError("This player is not paused!")

    def get_queue_info(self):
        entry_list = "\U0001F3BC Current queue:"
        for index, entry in enumerate(self.playlist[self.index :]):
            entry_list += format_queue_entry(index, entry)
        if not self.loop and self.index != 0:
            entry_list += "\n------------------------------------\n"
        for index, entry in enumerate(
            self.playlist[: self.index], start=len(self.playlist) - self.index
        ):
            entry_list += format_queue_entry(index, entry)
        return entry_list

    def get_queue_ids(self):
        id_list = ""
        for entry in self.playlist[self.index :]:
            id_list += "{id}\n".format(**entry)
        for entry in self.playlist[: self.index]:
            id_list += "{id}\n".format(**entry)
        return id_list

    def __play_next(self, err):
        if err:
            # TODO: Proper logging!
            print("ERROR: Playback ended with {}!".format(err))
            return
        if self.on_last and not self.loop:
            self.__stopped = True
            run_coroutine_threadsafe(
                self.__text_channel.send("The queue is empty, resume to keep playing."),
                self.__event_loop,
            ).result()

        if not self.__stopped:
            run_coroutine_threadsafe(
                self.start_playing(self.next), self.__event_loop
            ).result()

    async def start_playing(self, current):
        audio = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(current["url"], **self.FFMPEG_OPTIONS),
            volume=self.__volume,
        )

        # TODO: Handle FFMPEG errors gracefully
        self.__voice_client.play(audio, after=self.__play_next)
        await self.__text_channel.send(
            "\u25B6 Playing **{title}** by {uploader}.".format(**current)
        )


class MusicModule(commands.Cog):
    """This module handles commands related to playing music."""

    # TODO: Remove unnecessary options
    YT_DOWNLOAD_OPTIONS = {
        "format": "bestaudio/best",
        "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
        "restrictfilenames": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "ignoreerrors": True,
        "logtostderr": False,
        "quiet": True,
        "no_warnings": True,
        "default_search": "auto",
        "source_address": "0.0.0.0",
    }

    # TODO: Should probably be its own object & class.
    # Should run searches asynchronously by itself?
    YT_DOWNLOADER = youtube_dl.YoutubeDL(YT_DOWNLOAD_OPTIONS)

    def __init__(self, bot):
        self.bot = bot
        self.__players = {}

    def get_player(self, ctx):
        """Returns a MusicPlayer instance for the channel in the current context."""
        return self.__players[ctx.voice_client.channel.id]

    @commands.command()
    async def leave(self, ctx):
        """Removes the bot from the channel in the current context."""
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            self.get_player(ctx).stop()

        self.__players.pop(ctx.voice_client.channel.id)
        await ctx.voice_client.disconnect()
        await ctx.send("Quitting the voice channel.")

    # Add proper error handling
    @commands.command()
    async def play(self, ctx, *query):
        """Searches for and plays a video from YouTube
        on the channel in the current context."""
        async with ctx.typing():
            # Get video list for query
            # TODO: Run this asynchronously
            results = self.YT_DOWNLOADER.extract_info(
                "ytsearch10:" + " ".join(query), download=False
            )["entries"]
            # Assemble and display menu
            menu = "Choose one of the following results:"
            for index, entry in enumerate(results):
                menu += "\n{}. **{title}** - {uploader}".format(index, **entry)
            menu_msg = await ctx.send(menu)

        def pred(msg):
            return (
                msg.channel == ctx.channel
                and msg.author == ctx.author
                and msg.content.isnumeric()
                and int(msg.content) < 10
            )

        try:
            response = await self.bot.wait_for("message", check=pred, timeout=30.0)
        except futures.TimeoutError:
            await menu_msg.edit(content="\U0001F552 *Selection expired.*")
            raise

        current = results[int(response.content)]

        player = self.get_player(ctx)
        player.add(current)

        if (
            ctx.voice_client.is_playing()
            or ctx.voice_client.is_paused()
            or player.stopped
        ):
            await ctx.send(
                    "\u2795 **{title}** by {uploader} added to the queue.".format(
            )
        else:
            await player.start_playing(current)

    @commands.command(name="play-url")
    async def play_url(self, ctx, url_list):
        """Plays a YouTube video or playlist on
        the channel in the current context."""
        results = []
        async with ctx.typing():
            for url in url_list.split():
                # TODO: Run this asynchronously
                result = self.YT_DOWNLOADER.extract_info(url, download=False)
                if "extractor" in result and result["extractor"] == "youtube":
                    results.append(result)
                else:
                    raise ValueError("Provided URL does not lead to a video!")

        player = self.get_player(ctx)
        message = ""
        for elem in results:
            player.add(elem)
            if (
                ctx.voice_client.is_playing()
                or ctx.voice_client.is_paused()
                or player.stopped
            ):
                message += "\n**{title}** by {uploader}".format(**elem)
            else:
                await player.start_playing(elem)

            await ctx.send("\u2795 Videos added to the queue: " + message)

    @commands.command()
    async def back(self, ctx, offset: int = -1):
        """Plays the previous video from the current queue
        based on the provided offset."""
        self.get_player(ctx).move(offset)

    @commands.command()
    async def forward(self, ctx, offset: int = 1, **_):
        """Plays the next video from the current queue
        based on the provided offset."""
        self.get_player(ctx).move(offset)

    @commands.command()
    async def loop(self, ctx, loop: bool):
        """Sets looping behaviour of the current playlist."""
        self.get_player(ctx).playlist.loop = loop
        await ctx.send("Playlist loop {}.".format("on" if loop else "off"))

    @commands.command()
    async def pause(self, ctx):
        """Pauses the player on the channel in the current context."""
        ctx.voice_client.pause()
        await ctx.send("Paused.")

    @commands.command()
    async def queue(self, ctx):
        """Displays the queue of the channel in the current context."""
        await ctx.send(self.get_player(ctx).playlist.get_queue())

    @commands.command()
    async def playlist(self, ctx):
        """Displays the playlist of the channel in the current context."""
        await ctx.send(self.get_player(ctx).playlist.get_playlist())

    @commands.command()
    async def resume(self, ctx):
        """Resumes the player on the channel in the current context."""
        await self.get_player(ctx).resume()

    @commands.command()
    async def shuffle(self, ctx):
        """Shuffles the playlist of the channel in the current context."""
        self.get_player(ctx).shuffle()

    @commands.command()
    async def clear(self, ctx):
        """Clear the playlist of the channel in the current context."""
        self.get_player(ctx).stop()
        self.get_player(ctx).clear()

    @commands.command()
    async def stop(self, ctx):
        """Stops the player on the channel in the current context."""
        self.get_player(ctx).stopped = True
        ctx.voice_client.stop()
        await ctx.send("Stopped.")

    @commands.command()
    async def volume(self, ctx, volume: int):
        """Changes the volume of the player on the channel in the current context."""
        if volume in range(0, 101):
            self.get_player(ctx).volume = volume / 100
            await ctx.send("Volume is now at {}%.".format(volume))
        else:
            await ctx.send("Incorrect volume value!")

    @commands.command()
    async def current(self, ctx):
        """Displays information about the video that is being played
        in the current context."""
        await ctx.send(
            "Playing {title} by {uploader} now.\n{webpage_url}".format(
                **self.get_player(ctx).playlist.current
            )
        )

    @commands.command()
    async def remove(self, ctx, index: int):
        """Removes a video from the playlist in the current context."""
        player = self.get_player(ctx)
        if index in range(0, player.playlist.length):
            await ctx.send(
                "{title} by {uploader} removed from the playlist.".format(
                    **player.playlist.remove(index)
                )
            )
            if index == player.playlist.index:
                player.playlist.set_offset(0)
                ctx.voice_client.stop()
        else:
            await ctx.send("Incorrect playlist index!")

    @play.before_invoke
    @play_url.before_invoke
    @volume.before_invoke
    async def ensure_voice_or_join(self, ctx):
        """Ensures that the author of the message is in a voice channel,
        otherwise joins the author's voice channel.
        """
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
                self.__players[ctx.voice_client.channel.id] = MusicPlayer(
                    self.bot.loop, ctx.voice_client, ctx.message.channel
                )
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")

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
            await ctx.send("You are not connected to a voice channel.")
            raise commands.CommandError("Author not connected to a voice channel.")

    @pause.before_invoke
    @stop.before_invoke
    async def ensure_playing(self, ctx):
        """Ensures that the player for the current
        context is neither paused nor stopped.
        """
        if not ctx.voice_client.is_playing:
            await ctx.send("Nothing is being played now.")
            raise commands.CommandError("No playback in the voice channel.")
