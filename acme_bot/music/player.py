"""This module provides a music player for the bot."""
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

from asyncio import run_coroutine_threadsafe
from enum import Enum, auto
from re import match
from subprocess import PIPE
from threading import Semaphore, Thread
from time import time

import logging

import discord
from discord.ext import commands

from acme_bot.music.queue import MusicQueue


log = logging.getLogger(__name__)


class FFmpegAudioSource(discord.FFmpegPCMAudio):
    """Error handling wrapper for discord.py FFmpegPCMAudio."""

    __SUCCESSFUL_RETURN_CODES = [-9, 0]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def cleanup(self):
        proc = self._process
        super().cleanup()

        if proc and proc.returncode not in self.__SUCCESSFUL_RETURN_CODES:
            msg = (
                f"ffmpeg (PID {proc.pid}) terminated with"
                f" return code of {proc.returncode}"
            )
            log.error(msg)
            raise ChildProcessError(msg)


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
    """Redirect log messages from FFMPEG stderr to the module logger."""
    # These log messages are expected and can be filtered out
    rejects = ["Error in the pull function", "Will reconnect at"]
    # Alas, we need to perform this access to get the FFMPEG process
    # pylint: disable=protected-access
    process = source.original._process

    while True:
        line = process.stderr.readline()
        if line:
            level, message, module = parse_log_entry(line.decode(errors="replace"))
            # Redirect to the bot's log only if the message is not in the rejects
            if all(r not in message for r in rejects):
                log.log(level, "In ffmpeg module '%s': %s", module, message)
        else:
            log.debug("Log processing for ffmpeg process %s finished", process.pid)
            return


class PlayerState(Enum):
    """This enum represents the current state of MusicPlayer."""

    IDLE = auto()
    PLAYING = auto()
    PAUSED = auto()
    STOPPED = auto()


class MusicPlayer(MusicQueue):
    """This class provides a music player with a queue and some common controls."""

    FFMPEG_OPTIONS = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": "-vn -af dynaudnorm -hide_banner -loglevel +level",
    }

    def __init__(self, ctx, downloader, access_code):
        super().__init__()
        self.__ctx = ctx
        self.__sem = Semaphore()
        self.__state = PlayerState.IDLE
        self.__volume = 1.0
        self.__downloader = downloader

        self.access_code = access_code

    def __enter__(self):
        self.__sem.acquire()
        return self

    def __exit__(self, *_):
        self.__sem.release()
        return False

    @property
    def channel_id(self):
        """Provides external access to the player's voice channel ID."""
        return self.__ctx.voice_client.channel.id

    @property
    def state(self):
        """Provides external access to the state field."""
        return self.__state

    def clear(self):
        """Stop the player and clear the playlist."""
        self._clear()
        self.__state = PlayerState.IDLE
        self.__ctx.voice_client.stop()
        self._clear()

    def move(self, new_offset):
        """Moves to the track pointed at by the offset."""
        self.next_offset = new_offset
        if self.__ctx.voice_client.is_playing():
            self.__ctx.voice_client.stop()

    def pause(self):
        """Pauses the player."""
        self.__state = PlayerState.PAUSED
        self.__ctx.voice_client.pause()

    def remove(self, offset):
        """Removes a track from the player's queue."""
        removed = self._pop(offset)
        if offset == 0:  # If the current track got removed, start playing the next one.
            self.next_offset = 0
            self.__ctx.voice_client.stop()
        if self.is_empty():  # If the queue is now empty, stop the player.
            self.__state = PlayerState.IDLE
            self.__ctx.voice_client.stop()
        return removed

    async def resume(self):
        """Resumes the player."""
        if self.__state == PlayerState.PAUSED:
            self.__state = PlayerState.PLAYING
            self.__ctx.voice_client.resume()
            return "\u25B6 Playing **{title}** by {uploader}.".format(**self.current())
        if self.__state == PlayerState.STOPPED:
            self.__state = PlayerState.PLAYING
            await self.start_player(self.current())
        else:
            raise commands.CommandError("This player is not paused!")

    def set_volume(self, volume):
        """Sets the volume of the player."""
        if 0 <= volume <= 100:
            self.__volume = volume / 100
            if source := self.__ctx.voice_client.source:
                source.volume = self.__volume
        else:
            raise commands.CommandError("Incorrect volume value!")

    async def start_player(self, current):
        """Async function used for starting the player."""
        # Update the entry if it would expire during playback
        if time() + current["duration"] > current["expire"]:
            await self.__downloader.update_entry(current)

        audio = discord.PCMVolumeTransformer(
            FFmpegAudioSource(current["url"], **self.FFMPEG_OPTIONS, stderr=PIPE),
            volume=self.__volume,
        )

        # Start the log parser thread
        log_parser = Thread(target=process_ffmpeg_logs, args=[audio], daemon=True)
        log_parser.start()
        log.debug("Started ffmpeg log processing thread")

        self.__state = PlayerState.PLAYING

        self.__ctx.voice_client.play(audio, after=self.__play_next)
        await self.__ctx.send(
            "\u25B6 Playing **{title}** by {uploader}.".format(**current)
        )

    def stop(self):
        """Stop the player."""
        self.__state = PlayerState.STOPPED
        self.__ctx.voice_client.stop()

    async def disconnect(self):
        """Disconnect the player from its voice channel."""
        self.__state = PlayerState.STOPPED
        await self.__ctx.voice_client.disconnect()

    def __play_next(self, err):
        """Executed after the track is done playing, plays the next song or stops."""
        with self.__sem:
            if err:
                log.error(err)
                return
            # Stop the if player loop is off and it played the last song in queue
            if self.should_stop() and self.__state == PlayerState.PLAYING:
                self.__state = PlayerState.STOPPED
                run_coroutine_threadsafe(
                    self.__ctx.send("The queue is empty, resume to keep playing."),
                    self.__ctx.bot.loop,
                )
            # Advance the queue if it's not empty
            if self.__state in (PlayerState.PLAYING, PlayerState.PAUSED):
                current = self._next()
                run_coroutine_threadsafe(
                    self.start_player(current), self.__ctx.bot.loop
                )
