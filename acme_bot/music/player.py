"""This module provides a music player for the bot."""
from asyncio import run_coroutine_threadsafe
from re import match
from subprocess import PIPE
from threading import Semaphore, Thread
from time import time

import logging

import discord
from discord.ext import commands

from .queue import MusicQueue


def parse_log_entry(line):
    """This function parses a single line of the FFMPEG's stderr output
    and extracts information about the message."""
    ffmpeg_levels = {
        "panic": logging.CRITICAL,
        "fatal": logging.CRITICAL,
        "error": logging.ERROR,
        "warning": logging.WARNING,
        "info": logging.INFO,
        "verbose": logging.INFO,
        "debug": logging.DEBUG,
    }

    # This regex matches (in order) the source module's name,
    # the level and the message of the log entry.
    matches = match(r"\[([a-z]*) @ [^\]]*\] \[([a-z]*)\] (.*)", line)

    try:
        return ffmpeg_levels[matches[2]], matches[3], matches[1]
    except (IndexError, TypeError):
        return logging.WARNING, line, "unknown"


def process_ffmpeg_logs(source):
    """This function processes the FFMPEG's stderr output and redirects
    it to the bot's log accordingly."""
    # These log messages are completely normal and can be filtered out
    rejects = ["Error in the pull function", "Will reconnect at"]

    while True:
        # Alas, we need to perform this access to get the stderr of FFMPEG
        # pylint: disable=protected-access
        line = source.original._process.stderr.readline()
        if line:
            level, message, module = parse_log_entry(line.decode(errors="replace"))
            # Redirect to the bot's log only if the message is not in the rejects
            if all(r not in message for r in rejects):
                logging.log(level, "In ffmpeg module '%s': %s", module, message)
        else:
            logging.debug("Finished parsing the ffmpeg stderr output.")
            return


class MusicPlayer(MusicQueue):
    """This class provides a music player with a queue and some common controls."""

    FFMPEG_OPTIONS = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": "-vn -af dynaudnorm -hide_banner -loglevel +level",
    }

    def __init__(self, ctx, downloader):
        super().__init__()
        self.__ctx = ctx
        self.__sem = Semaphore()
        self.__stopped = False
        self.__volume = 1.0
        self.__downloader = downloader

    def __enter__(self):
        self.__sem.acquire()
        return self

    def __exit__(self, *_):
        self.__sem.release()
        return False

    def is_busy(self):
        """Checks if the player is currently playing, paused or stopped."""
        return (
            self.__ctx.voice_client.is_playing()
            or self.__ctx.voice_client.is_paused()
            or self.__stopped
        )

    def move(self, new_offset):
        """Moves to the track pointed at by the offset."""
        self.next_offset = new_offset
        if self.__ctx.voice_client.is_playing():
            self.__ctx.voice_client.stop()

    def pause(self):
        """Pauses the player, locking it in the process."""
        self.__ctx.voice_client.pause()

    def remove(self, offset):
        """Removes a track from the player's queue."""
        removed = self._pop(offset)
        # If the track that is playing got removed, start playing the next one.
        if offset == 0:
            self.next_offset = 0
            self.__ctx.voice_client.stop()
        return removed

    async def resume(self):
        """Resumes the player, even if it's stopped."""
        if self.__ctx.voice_client.is_paused():
            self.__ctx.voice_client.resume()
            return "\u25B6 Playing **{title}** by {uploader}.".format(**self.current())
        if self.__stopped:
            self.__stopped = False
            await self.start_player(self.current())
        else:
            raise commands.CommandError("This player is not paused!")

    def set_volume(self, volume):
        """Set the volume of the player."""
        if volume in range(0, 101):
            self.__volume = volume / 100
            if self.__ctx.voice_client.source:
                self.__ctx.voice_client.source.volume = volume / 100
        else:
            raise commands.CommandError("Incorrect volume value!")

    async def start_player(self, current):
        """Async function used for starting the player."""
        # Update the entry if it would expire during playback
        if time() + current["duration"] > current["expire"]:
            await self.__downloader.update_entry(current)

        audio = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(current["url"], **self.FFMPEG_OPTIONS, stderr=PIPE),
            volume=self.__volume,
        )

        # Start the log parser thread
        log_parser = Thread(target=process_ffmpeg_logs, args=[audio], daemon=True)
        log_parser.start()

        self.__ctx.voice_client.play(audio, after=self.__play_next)
        await self.__ctx.send(
            "\u25B6 Playing **{title}** by {uploader}.".format(**current)
        )

    def stop(self):
        """Stop the player."""
        self.__stopped = True
        self.__ctx.voice_client.stop()

    def __play_next(self, err):
        """Executed after the track is done playing, plays the next song or stops."""
        with self.__sem:
            if err:
                logging.error(err)
                return
            # Stop the if player loop is off and it played the last song in queue
            if self.on_rollover() and not self._loop and not self.__stopped:
                self.__stopped = True
                run_coroutine_threadsafe(
                    self.__ctx.send("The queue is empty, resume to keep playing."),
                    self.__ctx.bot.loop,
                )
            # Advance the queue whether the player is stopped or not
            current = self._next()
            if not self.__stopped:
                run_coroutine_threadsafe(
                    self.start_player(current), self.__ctx.bot.loop
                )
