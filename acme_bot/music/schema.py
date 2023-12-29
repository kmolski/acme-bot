"""Pydantic models for MusicPlayer/MusicQueue data."""
#  Copyright (C) 2023  Krzysztof Molski
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

from pydantic import TypeAdapter
from typing_extensions import TypedDict


class QueueEntry(TypedDict, total=False):  # pylint: disable=too-many-ancestors
    """Data model for a MusicQueue entry."""

    id: str
    url: Annotated[str, Field(exclude=True)]
    title: str
    entries: list["QueueEntry"] | None
    uploader: str
    duration: int | float
    webpage_url: str
    uploader_url: str | None
    duration_string: str
    thumbnail: str | None
    extractor: str


QueueEntryValidator = TypeAdapter(QueueEntry)
