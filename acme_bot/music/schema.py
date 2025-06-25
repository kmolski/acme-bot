"""Pydantic models for MusicPlayer/MusicQueue data."""

#  Copyright (C) 2023-2025  Krzysztof Molski
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

from enum import Enum

from lavalink import DefaultPlayer
from pydantic import BaseModel

from acme_bot.textutils import format_duration


class PlayerState(Enum):
    """State set for lavalink.DefaultPlayer."""

    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"
    DISCONNECTED = "disconnected"

    @classmethod
    def from_lavalink(cls, player):
        """Convert from lavalink.DefaultPlayer."""
        if player.channel_id is None:
            return cls.DISCONNECTED
        if player.paused:
            return cls.PAUSED if player.position_timestamp > 0 else cls.STOPPED
        if player.current is not None:
            return cls.PLAYING
        return cls.IDLE


class QueueEntry(BaseModel):
    """Data model for a lavalink.Track entry."""

    id: str
    title: str
    uploader: str
    duration: int | float
    webpage_url: str
    uploader_url: str | None = None
    duration_string: str
    thumbnail: str | None = None
    extractor: str

    @classmethod
    def from_lavalink(cls, track):
        """Convert from lavalink.Track."""
        secs = track.duration // 1000
        return cls(
            id=track.identifier,
            title=track.title,
            uploader=track.author,
            duration=secs,
            webpage_url=track.uri,
            uploader_url=track.raw["artistUrl"],
            duration_string=format_duration(secs),
            thumbnail=track.artwork_url,
            extractor=track.source_name,
        )


class PlayerModel(BaseModel):
    """Data model for a lavalink.DefaultPlayer instance."""

    loop: bool
    volume: int
    position: int
    state: PlayerState
    queue: list[QueueEntry]
    current: QueueEntry | None

    @classmethod
    def serialize(cls, player):
        """Serialize the MusicPlayer instance."""
        model = PlayerModel(
            loop=player.loop == DefaultPlayer.LOOP_QUEUE,
            volume=player.volume,
            position=player.position_timestamp,
            state=PlayerState.from_lavalink(player),
            queue=[QueueEntry.from_lavalink(track) for track in player.queue],
            current=(
                QueueEntry.from_lavalink(player.current) if player.current else None
            ),
        )
        return model.model_dump_json(exclude={"queue": {"__all__": "url"}})
