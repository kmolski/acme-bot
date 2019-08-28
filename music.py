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
    def on_first(self):
        return self.__index == 0

    @property
    def on_rollover(self):
        return (
            self.__playlist
            and self.__offset == 1
            and self.__index >= len(self.__playlist) - 1
        )

    @property
    def queue_data(self):
        return (
            self.__playlist[self.__index :],
            self.__playlist[: self.__index],
            len(self.__playlist) - self.__index,
        )

    def add(self, elem):
        self.__playlist.append(elem)

    def clear(self):
        self.__playlist.clear()
        self.__index = 0

    def next(self):
        self.__index = (self.__index + self.__offset) % len(self.__playlist)
        self.__offset = 1
        return self.__playlist[self.__index]

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
    def rollover(self):
        return not self.__stopped and not self.loop

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
        head, tail, split = self.queue_data
        for index, entry in enumerate(head):
            entry_list += format_queue_entry(index, entry)
        if not self.loop and not self.on_first:
            entry_list += "\n------------------------------------\n"
        for index, entry in enumerate(tail, start=split):
            entry_list += format_queue_entry(index, entry)
        return entry_list

    def get_queue_ids(self):
        id_list = ""
        head, tail, _ = self.queue_data
        for entry in head:
            id_list += "{id}\n".format(**entry)
        for entry in tail:
            id_list += "{id}\n".format(**entry)
        return id_list

    def __play_next(self, err):
        if err:
            # TODO: Proper logging!
            print("ERROR: Playback ended with {}!".format(err))
            return
        if self.on_rollover and not self.rollover:
            self.__stopped = True
            run_coroutine_threadsafe(
                self.__text_channel.send("The queue is empty, resume to keep playing."),
                self.__event_loop,
            ).result()
        current = self.next()
        if not self.__stopped:
            run_coroutine_threadsafe(
                self.start_playing(current), self.__event_loop
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

    def __init__(self, bot):
        super().__init__(self.FINDER_OPTIONS)
        self.loop = bot.loop

    async def get_single_entry(self, url):
        result = await self.loop.run_in_executor(
            None, lambda: self.extract_info(url, download=False)
        )
        return result

    async def get_entry_list(self, provider, query):
        results = await self.loop.run_in_executor(
            None, lambda: self.extract_info(provider + query, download=False)
        )
        return results["entries"]


class MusicModule(commands.Cog):
    """This module handles commands related to playing music."""

    def __init__(self, bot):
        self.bot = bot
        self.__downloader = MusicFinder(bot)
        self.__players = {}

    def get_player(self, ctx):
        """Returns a MusicPlayer instance for the channel in the current context."""
        return self.__players[ctx.voice_client.channel.id]

    @commands.command()
    async def leave(self, ctx, *, display=True):
        """Removes the bot from the channel in the current context."""
        self.__players.pop(ctx.voice_client.channel.id)
        await ctx.voice_client.disconnect()
        if display:
            await ctx.send("\u23CF Quitting the voice channel.")

    # Add proper error handling
    @commands.command()
    async def play(self, ctx, *query, display=True):
        """Searches for and plays a video from YouTube
        on the channel in the current context."""
        async with ctx.typing():
            query = " ".join(query)
            # Get video list for query
            results = await self.__downloader.get_entry_list("ytsearch10:", query)
            # Assemble and display menu
            menu = "\u2049 Choose one of the following results:"
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
            if display:
                await ctx.send(
                    "\u2795 **{title}** by {uploader} added to the queue.".format(
                        **current
                    )
                )
        else:
            await player.start_playing(current)

        return current["id"]

    @commands.command(name="play-snd")
    async def play_snd(self, ctx, *query, display=True):
        """Searches for and plays a video from Soundcloud
        on the channel in the current context."""
        async with ctx.typing():
            query = " ".join(query)
            # Get video list for query
            results = await self.__downloader.get_entry_list("scsearch10:", query)
            # Assemble and display menu
            menu = "\u2049 Choose one of the following results:"
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
            if display:
                await ctx.send(
                    "\u2795 **{title}** by {uploader} added to the queue.".format(
                        **current
                    )
                )
        else:
            await player.start_playing(current)

        return current["id"]

    @commands.command(name="play-url")
    async def play_url(self, ctx, url_list, *, display=True):
        """Plays a YouTube/Soundcloud track on
        the channel in the current context."""
        # TODO: This command should ask for confirmation before adding songs!
        url_list, results = str(url_list), []
        async with ctx.typing():
            for url in url_list.split():
                result = await self.__downloader.get_single_entry(url)
                if "extractor" in result and (
                    result["extractor"] == "youtube"
                    or result["extractor"] == "soundcloud"
                ):
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

        if message and display:
            await ctx.send("\u2795 Videos added to the queue: " + message)

        return url_list

    @commands.command()
    async def back(self, ctx, offset: int = -1, **_):
        """Plays the previous video from the current queue
        based on the provided offset."""
        self.get_player(ctx).move(offset)

    @commands.command()
    async def forward(self, ctx, offset: int = 1, **_):
        """Plays the next video from the current queue
        based on the provided offset."""
        self.get_player(ctx).move(offset)

    @commands.command()
    async def loop(self, ctx, should_loop: bool, *, display=True):
        """Sets looping behaviour of the current playlist."""
        self.get_player(ctx).loop = should_loop
        msg = "on" if should_loop else "off"
        if display:
            await ctx.send("\U0001F501 Playlist loop {}.".format(msg))
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
        player = self.get_player(ctx)
        if display:
            entries = player.get_queue_info()
            await ctx.send(entries)
        ids = player.get_queue_ids()
        return ids

    @commands.command()
    async def resume(self, ctx, **_):
        """Resumes the player on the channel in the current context."""
        await self.get_player(ctx).resume()

    @commands.command()
    async def shuffle(self, ctx, *, display=True):
        """Shuffles the playlist of the channel in the current context."""
        self.get_player(ctx).shuffle()
        if display:
            await ctx.send("\U0001F500 Queue shuffled.")

    @commands.command()
    async def clear(self, ctx, *, display=True):
        """Clear the playlist of the channel in the current context."""
        player = self.get_player(ctx)
        player.stop()
        player.clear()
        if display:
            await ctx.send("\u2716 Queue cleared.")

    @commands.command()
    async def stop(self, ctx, *, display=True):
        """Stops the player on the channel in the current context."""
        self.get_player(ctx).stop()
        if display:
            await ctx.send("\u23F9 Stopped.")

    @commands.command()
    async def volume(self, ctx, volume: int, *, display=True):
        """Changes the volume of the player on the channel in the current context."""
        self.get_player(ctx).volume = volume
        if display:
            await ctx.send("\U0001F4E2 Volume is now at **{}%**.".format(volume))
        return str(volume)

    @commands.command()
    async def current(self, ctx, *, display=True):
        """Displays information about the video that is being played
        in the current context."""
        current = self.get_player(ctx).current
        if display:
            await ctx.send(
                "\u25B6 Playing **{title}** by {uploader} now.\n{webpage_url}".format(
                    **current
                )
            )
        return current["id"]

    @commands.command()
    async def remove(self, ctx, offset: int, *, display=True):
        """Removes a video from the music queue."""
        removed = self.get_player(ctx).remove(offset)
        if display:
            await ctx.send(
                "\u2796 **{title}** by {uploader} removed from the playlist.".format(
                    **removed
                )
            )
        return removed["id"]

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
