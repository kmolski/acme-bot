"""Track queue implementation for the music player."""
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


class MusicQueue:
    """Music queue that keeps track of the current entry and loops."""

    def __init__(self):
        self.loop = True
        self._next_offset = 1
        self.__index = 0
        self.__playlist = []

    @property
    def current(self):
        """Return the current track."""
        return self.__playlist[self.__index]

    def append(self, new_elem):
        """Add a single new element to the queue."""
        self.__playlist.append(new_elem)

    def extend(self, elem_list):
        """Append an iterable of new elements to the queue."""
        self.__playlist.extend(elem_list)

    def on_first(self):
        """Return True if the current element is the first one."""
        return self.__index == 0

    def is_empty(self):
        """Return True if the queue is empty."""
        return not self.__playlist

    def should_stop(self):
        """Return True if the current element is the last one and looping is off."""
        return self.is_empty() or (
            self.__index + self._next_offset >= len(self.__playlist) and not self.loop
        )

    def split_view(self):
        """Return the queue head, tail and split offset."""
        return (
            self.__playlist[self.__index :],
            self.__playlist[: self.__index],
            len(self.__playlist) - self.__index,
        )

    def clear(self):
        """Remove all elements from the queue."""
        self.__playlist.clear()
        self.__index = 0  # Set the index to 0, as there is nothing in the queue

    def next(self):
        """Return the next track based on the offset."""
        if self.is_empty():
            raise IndexError("queue index out of range")

        self.__index = (self.__index + self._next_offset) % len(self.__playlist)
        self._next_offset = 1  # Reset next_offset to the default value of 1
        return self.current

    def pop(self, offset):
        """Remove the entry at `offset` from the queue."""
        if self.is_empty():
            raise IndexError("queue index out of range")

        return self.__playlist.pop((self.__index + offset) % len(self.__playlist))
