"""Pydantic models for MusicPlayer/MusicQueue data."""

#  Copyright (C) 2023-2024  Krzysztof Molski
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

from pydantic import BaseModel
from wavelink import QueueMode

from acme_bot.textutils import format_duration


class PlayerState(Enum):
    """State set for wavelink.Player."""

    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"
    DISCONNECTED = "disconnected"

    @classmethod
    def from_wavelink(cls, player):
        """Convert from wavelink.Player."""
        if not player.connected:
            return cls.DISCONNECTED
        if player.paused:
            return cls.PAUSED if player.position > 0 else cls.STOPPED
        if player.playing:
            return cls.PLAYING
        return cls.IDLE


class QueueEntry(BaseModel):
    """Data model for a wavelink.Queue entry."""

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
    def from_wavelink(cls, track):
        """Convert from wavelink.Playable."""
        secs = track.length // 1000
        return cls(
            id=track.identifier,
            title=track.title,
            uploader=track.author,
            duration=secs,
            webpage_url=track.uri,
            uploader_url=track.artist.url,
            duration_string=format_duration(secs),
            thumbnail=track.artwork,
            extractor=track.source,
        )


class PlayerModel(BaseModel):
    """Data model for a wavelink.Player instance."""

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
            loop=player.queue.mode == QueueMode.loop_all,
            volume=player.volume,
            position=player.position,
            state=PlayerState.from_wavelink(player),
            queue=[QueueEntry.from_wavelink(track) for track in player.queue],
            current=(
                QueueEntry.from_wavelink(player.current) if player.current else None
            ),
        )
        return model.model_dump_json(exclude={"queue": {"__all__": "url"}})
