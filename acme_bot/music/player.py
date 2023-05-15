"""Music player based on MusicQueue and discord.py FFmpegPCMAudio."""
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
from asyncio import run_coroutine_threadsafe
from enum import Enum, auto
from re import match
from subprocess import PIPE
from threading import Lock, Thread
from time import time

import discord
from discord.ext import commands

from acme_bot.music.queue import MusicQueue

__EXPECTED = [
    "Connection reset by peer",
    "Error in the pull function",
    "Will reconnect at",
]

__FFMPEG_LOG_LEVELS = {
    "panic": logging.CRITICAL,
    "fatal": logging.CRITICAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "verbose": logging.INFO,
    "debug": logging.DEBUG,
}

log = logging.getLogger(__name__)


def parse_log_entry(line):
    """Parse and convert a single line of FFMPEG log output."""
    # Matches the source module name, log level and message.
    # e.g. [http @ 0x000000000000] [error] HTTP error 404 Not Found
    matches = match(r"\[([a-z]*) @ [^\]]*\] \[([a-z]*)\] (.*)", line)

    try:
        return __FFMPEG_LOG_LEVELS[matches[2]], matches[3], matches[1]
    except (IndexError, TypeError):
        return logging.WARNING, line, "unknown"


def parse_ffmpeg_log(process):
    """Redirect log messages from FFMPEG stderr to the module logger."""
    log.debug("Log processing for ffmpeg (PID %s) started", process.pid)

    while process.stderr:
        entry = process.stderr.readline()
        if entry:
            level, message, module = parse_log_entry(entry.decode(errors="replace"))
            # Redirect to module logger only if the logged message is not expected
            if all(e not in message for e in __EXPECTED):
                log.log(level, "ffmpeg/%s: %s", module, message)
        else:
            log.debug("Log processing for ffmpeg (PID %s) finished", process.pid)
            return


class FFmpegAudioSource(discord.FFmpegPCMAudio):
    """Error handling extension for discord.py FFmpegPCMAudio."""

    __SUCCESSFUL_RETURN_CODES = [-9, 0]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        log_parser = Thread(target=parse_ffmpeg_log, args=[self._process], daemon=True)
        log_parser.start()

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


class PlayerState(Enum):
    """State set for the MusicPlayer implementation."""

    IDLE = auto()
    PLAYING = auto()
    PAUSED = auto()
    STOPPED = auto()


class MusicPlayer(MusicQueue):
    """
    Music player based on MusicQueue and discord.py FFmpegPCMAudio.

    Implements a finite state machine as defined by PlayerState.
    """

    __FFMPEG_OPTIONS = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": "-vn -af dynaudnorm -hide_banner -loglevel +level",
    }

    def __init__(self, ctx, extractor, access_code):
        super().__init__()
        self.__lock = Lock()
        self.__state = PlayerState.IDLE
        self.__volume = 1.0
        self.__next_offset = 1

        self.__ctx = ctx
        self.__extractor = extractor
        self.__access_code = access_code

    def __enter__(self):
        self.__lock.acquire()
        return self

    def __exit__(self, *_):
        self.__lock.release()
        return False

    @property
    def access_code(self):
        """Return the player's access code."""
        return self.__access_code

    @property
    def channel_id(self):
        """Return the player's voice channel ID."""
        return self.__ctx.voice_client.channel.id

    @property
    def state(self):
        """Return the current player state."""
        return self.__state

    @property
    def volume(self):
        """Return the current player volume."""
        return self.__volume * 100

    @volume.setter
    def volume(self, volume):
        """Set the volume of the player."""
        if 0 <= volume <= 100:
            self.__volume = volume / 100
            if source := self.__ctx.voice_client.source:
                source.volume = self.__volume
        else:
            raise commands.CommandError("Incorrect volume value!")

    def clear(self):
        """Stop the player and clear the playlist."""
        super().clear()
        self.__state = PlayerState.IDLE
        self.__ctx.voice_client.stop()

    def move(self, new_offset):
        """Moves to the track pointed at by the offset."""
        self.__next_offset = new_offset
        if self.__ctx.voice_client.is_playing():
            self.__ctx.voice_client.stop()

    def pause(self):
        """Pauses the player."""
        self.__state = PlayerState.PAUSED
        self.__ctx.voice_client.pause()

    def remove(self, offset):
        """Removes a track from the player's queue."""
        removed = self.pop(offset)
        if offset == 0:  # If the current track got removed, start playing the next one.
            self.__next_offset = 0
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
        elif self.__state == PlayerState.STOPPED:
            self.__state = PlayerState.PLAYING
            await self.start_player(self.current)
        else:
            raise commands.CommandError("This player is not paused!")

    async def start_player(self, current):
        """Async function used for starting the player."""
        # Update the entry if it would expire during playback
        if "expire" not in current or time() + current["duration"] > current["expire"]:
            await self.__extractor.update_entry(current)

        audio = discord.PCMVolumeTransformer(
            FFmpegAudioSource(current["url"], **self.__FFMPEG_OPTIONS, stderr=PIPE),
            volume=self.__volume,
        )

        self.__state = PlayerState.PLAYING
        self.__ctx.voice_client.play(audio, after=self.__play_next)

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
        with self.__lock:
            if err:
                log.error(err)
                return
            # Stop if queue looping is off and the last song has finished playing
            if (
                self.should_stop(self.__next_offset)
                and self.__state == PlayerState.PLAYING
            ):
                self.__state = PlayerState.STOPPED
                run_coroutine_threadsafe(
                    self.__ctx.send("The queue is empty, resume to keep playing."),
                    self.__ctx.bot.loop,
                )
            # Advance the queue if it's not empty
            if self.__state in (PlayerState.PLAYING, PlayerState.PAUSED):
                current = self.next(self.__next_offset)
                self.__next_offset = 1  # Reset next_offset to the default value of 1
                run_coroutine_threadsafe(
                    self.start_player(current), self.__ctx.bot.loop
                )
