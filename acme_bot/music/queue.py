"""Track queue used by the MusicPlayer implementation."""
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

from random import shuffle


class MusicQueue:
    """Track queue used by the MusicPlayer implementation."""

    def __init__(self):
        self.next_offset = 1
        self._loop = True
        self.__index = 0
        self.__playlist = []

    def append(self, new_elem):
        """Add a single new element to the queue."""
        self.__playlist.append(new_elem)

    def current(self):
        """Return the current track."""
        return self.__playlist[self.__index]

    def extend(self, elem_list):
        """Append a list of new elements to the queue."""
        self.__playlist.extend(elem_list)

    def on_first(self):
        """Return True if the current element is the first one."""
        return self.__index == 0

    def is_empty(self):
        """Return True if the playlist is currently empty."""
        return not self.__playlist

    def should_stop(self):
        """Return True if the current element is the last one and looping is off."""
        return self.is_empty() or (
            self.__index + self.next_offset >= len(self.__playlist) and not self._loop
        )

    def queue_data(self):
        """Return the queue split into two parts and the offset where it's split."""
        return (
            self.__playlist[self.__index :],
            self.__playlist[: self.__index],
            len(self.__playlist) - self.__index,
        )

    def shuffle(self):
        """Randomly shuffle the elements of the queue."""
        shuffle(self.__playlist)

    def _clear(self):
        """Remove all elements from the queue."""
        self.__playlist.clear()
        self.__index = 0  # Set the index to 0, as there is nothing in the queue

    def _next(self):
        """Returns the next entry based on the offset."""
        self.__index = (self.__index + self.next_offset) % len(self.__playlist)
        self.next_offset = 1  # Reset next_offset to the default value of 1
        return self.current()

    def _pop(self, offset):
        """Remove the entry at `offset` from the current track."""
        return self.__playlist.pop((self.__index + offset) % len(self.__playlist))
