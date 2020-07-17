"""This module provides a track queue for the MusicPlayer."""
from math import ceil
from random import shuffle


def format_queue_entry(index, entry):
    """This function formats a queue entry with the duration
    in the MM:SS format."""
    # The entry duration from YTDL is not always an integer
    duration = ceil(entry["duration"])

    minutes, seconds = duration // 60, duration % 60
    return "\n{}. **{title}** - {uploader} - {}:{:02}".format(
        index, minutes, seconds, **entry
    )


class MusicQueue:
    """This class provides a queue for the MusicPlayer."""

    def __init__(self):
        self.next_offset = 1
        self._loop = True  # Sets the queue looping on/off.
        self.__index = 0
        self.__playlist = []

    def append(self, new_elem):
        """Adds a single new element to the queue."""
        self.__playlist.append(new_elem)

    def current(self):
        """Returns the current track."""
        return self.__playlist[self.__index]

    def extend(self, elem_list):
        """Appends a list of new elements to the queue."""
        self.__playlist.extend(elem_list)

    def get_queue_info(self):
        """Creates a list containing the queue's entries, their title,
        author and duration."""
        entry_list = "\U0001F3BC Current queue:"
        head, tail, split = self.queue_data()
        for index, entry in enumerate(head):
            entry_list += format_queue_entry(index, entry)
        if not self._loop and not self.on_first():
            entry_list += "\n------------------------------------\n"
        for index, entry in enumerate(tail, start=split):
            entry_list += format_queue_entry(index, entry)
        return entry_list

    def get_queue_urls(self):
        """Creates a list containing the URLs of the entries in the queue."""
        url_list = ""
        head, tail, _ = self.queue_data()
        for entry in head:
            url_list += "{webpage_url}\n".format(**entry)
        for entry in tail:
            url_list += "{webpage_url}\n".format(**entry)
        return url_list

    def on_first(self):
        """Checks whether the current element is the first one."""
        return self.__index == 0

    def is_empty(self):
        """Checks whether the playlist is empty."""
        return not self.__playlist

    def should_stop(self):
        """Checks whether the current element is the last one."""
        return (
            self.__playlist
            and self.next_offset == 1
            and self.__index >= len(self.__playlist) - 1
            and not self._loop
        )

    def queue_data(self):
        """Returns a tuple that contains the queue in two parts
        and the offset after which it's split."""
        return (
            self.__playlist[self.__index :],
            self.__playlist[: self.__index],
            len(self.__playlist) - self.__index,
        )

    def shuffle(self):
        """Shuffles the elements of the queue."""
        shuffle(self.__playlist)

    def _clear(self):
        """Removes all elements from the queue."""
        self.__playlist.clear()
        self.__index = 0  # Set the index to 0, as there is nothing in the queue

    def _next(self):
        """Returns the next entry based on the offset."""
        self.__index = (self.__index + self.next_offset) % len(self.__playlist)
        self.next_offset = 1  # Set the next_offset back to 1
        return self.__playlist[self.__index]

    def _pop(self, offset):
        """Removes an entry from the queue."""
        return self.__playlist.pop((self.__index + offset) % len(self.__playlist))
