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


class Observable:
    """An observable object with a single observer."""

    def __init__(self):
        self.observer = None

    def notify(self):
        """Notify the observer about a change to the observable."""
        if self.observer is not None:
            self.observer.update(self)


class MusicQueue(Observable):
    """Music queue that keeps track of the current entry and loops."""

    def __init__(self):
        super().__init__()
        self.loop = True
        self.__index = 0
        self.__playlist = []

    @property
    def current(self):
        """Return the current track."""
        return self.__playlist[self.__index]

    def get(self, offset):
        """Return the track at the given offset."""
        return self.__playlist[self.__next_index(offset)]

    def append(self, new_elem):
        """Add a single new element to the queue."""
        self.__playlist.append(new_elem)
        self.notify()

    def extend(self, elem_list):
        """Append an iterable of new elements to the queue."""
        self.__playlist.extend(elem_list)
        self.notify()

    def is_empty(self):
        """Return True if the queue is empty."""
        return not self.__playlist

    def get_tracks(self):
        """Return the queue head and tail."""
        return (
            self.__playlist[self.__index :],
            self.__playlist[: self.__index],
        )

    def _clear(self):
        """Remove all elements from the queue."""
        self.__playlist.clear()
        self.__index = 0  # Index of zero will point at the first appended track

    def _next(self, offset):
        """Return the next track based on the offset."""
        if self.is_empty():
            raise IndexError("queue index out of range")

        self.__index = self.__next_index(offset)
        return self.current

    def _should_stop(self, offset):
        """Return True if the current element is the last one and looping is off."""
        return self.is_empty() or (
            self.__index + offset >= len(self.__playlist) and not self.loop
        )

    def _pop(self, offset):
        """Remove the entry at `offset` from the queue."""
        if self.is_empty():
            raise IndexError("queue index out of range")

        return self.__playlist.pop(self.__next_index(offset))

    def __next_index(self, offset):
        return (self.__index + offset) % len(self.__playlist)
