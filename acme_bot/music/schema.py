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

from pydantic import BaseModel, RootModel
from pydantic.json_schema import SkipJsonSchema


class PlayerState(Enum):
    """State set for the MusicPlayer implementation."""

    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"
    STOPPED = "stopped"
    DISCONNECTED = "disconnected"


class PlayerModel(BaseModel):
    """Data model for a MusicPlayer instance."""

    loop: bool
    volume: int
    state: PlayerState
    queue: list["QueueEntry"]

    @classmethod
    def serialize(cls, player):
        """Serialize the MusicPlayer instance."""
        head, tail = player.get_tracks()
        model = PlayerModel(
            loop=player.loop,
            volume=player.volume,
            state=player.state,
            queue=head + tail,
        )
        return model.model_dump_json(exclude={"queue": {"__all__": "url"}})


class QueueEntry(BaseModel):
    """Data model for a MusicQueue entry."""

    id: str
    url: SkipJsonSchema[str]
    title: str
    uploader: str
    duration: int | float
    webpage_url: str
    uploader_url: str | None = None
    duration_string: str
    thumbnail: str | None = None
    extractor: str


class Playlist(BaseModel):
    """Data model for a yt-dlp playlist."""

    id: str
    entries: list[QueueEntry]
    extractor: str


class ExtractResult(RootModel):
    """Result of yt-dlp.extract_info."""

    root: Playlist | QueueEntry
