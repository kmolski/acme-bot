"""This module provides track downloader for the MusicModule."""
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

from base64 import b64decode
from itertools import islice, chain
from json import loads
from multiprocessing import Process, Queue
from pathlib import PurePosixPath
from time import time
from urllib.parse import urlparse, parse_qs
import logging

from discord.ext import commands
import yt_dlp

yt_dlp.utils.bug_reports_message = lambda: ""

log = logging.getLogger(__name__)


def add_expire_time(entry):
    """Update the entry with its expiration time (kept as a Unix timestamp)."""
    try:
        url = urlparse(entry["url"])

        if entry["extractor"] == "youtube":
            if url.query:
                # Usually the expiration time is in the `expire` part of the query
                query = parse_qs(url.query)
                entry["expire"] = int(query["expire"][0])
            else:
                # Sometimes it's a part of the URL, not sure that it's always
                # the 5th part since I've only seen that happen once.
                path = PurePosixPath(url.path)
                entry["expire"] = int(path.parts[5])
        elif entry["extractor"] == "soundcloud":
            # The `Policy` part of the URL query contains a Base64-encoded JSON object
            # with the timestamp (Statement->Condition->DateLessThan->AWS:EpochTime)
            query = parse_qs(url.query)
            policy_b64 = query["Policy"][0].replace("_", "=")
            policy = loads(b64decode(policy_b64, altchars=b"~-"))
            entry["expire"] = int(
                policy["Statement"][0]["Condition"]["DateLessThan"]["AWS:EpochTime"]
            )
        else:
            raise commands.CommandError("Expected a YouTube/Soundcloud entry!")

    except (commands.CommandError, IndexError, KeyError, ValueError):
        # Default to 5 minutes if the expiration time cannot be found
        entry["expire"] = time() + (5 * 60)
        log.warning(
            "No expiration time found for URL, assuming 5 minutes: %s", entry["url"]
        )


def chunks(iterable, size):
    """Split `iterable` into chunks, each with `size` elements."""
    while chunk := tuple(islice(iterable, size)):
        yield chunk


def filter_not_none(iterable):
    """Remove None values from the `iterable`."""
    return [entry for entry in iterable if entry is not None]


class MusicDownloader(yt_dlp.YoutubeDL):
    """This class extracts and updates information about music tracks
    that are found by a query or by their URLs."""

    DOWNLOAD_OPTIONS = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "nocheckcertificate": True,
        "ignoreerrors": True,
        "logtostderr": False,
        "quiet": True,
        "no_warnings": True,
        "default_search": "auto",
        "source_address": "0.0.0.0",
    }

    __PROCESS_COUNT = 4
    __ALLOWED_URL_EXTRACTORS = (
        "youtube:playlist",
        "youtube:tab",
        "soundcloud:playlist",
        "soundcloud:set",
    )

    def __init__(self, loop):
        super().__init__(self.DOWNLOAD_OPTIONS)
        self.loop = loop

    def __start_extractor_process(self, url):
        """Start YoutubeDL.extract_info in a separate Python process."""
        result_queue = Queue()
        process = Process(
            target=lambda q, url: q.put(self.extract_info(url, download=False)),
            args=(result_queue, url),
        )
        process.start()
        log.debug("Started extractor process for URL %s, PID %s", url, process.pid)
        return result_queue, process

    async def get_entries_by_urls(self, url_list):
        """Extract the track entries from the given URLs."""
        # Run the extraction in parallel processes
        handles = chain.from_iterable(
            # URLs are processed in groups of `self.__PROCESS_COUNT` elements at a time
            chunks(map(self.__start_extractor_process, url_list), self.__PROCESS_COUNT)
        )
        results = []

        for result_queue, process in handles:
            result = await self.loop.run_in_executor(None, result_queue.get)
            process.join()
            log.debug("Extractor process (PID %s) finished", process.pid)

            if result is None:
                continue
            if result["extractor"] in ("youtube", "soundcloud"):
                results.append(result)
            elif result["extractor"] in self.__ALLOWED_URL_EXTRACTORS:
                results.extend(filter_not_none(result["entries"]))

        if not results:
            raise commands.CommandError("No tracks found for the provided URL list!")
        return results

    async def get_entries_by_query(self, provider, query):
        """Extract the track entries for the given search provider and query."""
        # Run the extraction in a background process
        result_queue, process = self.__start_extractor_process(provider + query)
        results = await self.loop.run_in_executor(None, result_queue.get)
        process.join()
        log.debug("Extractor process (PID %s) finished", process.pid)

        if not results or not results["entries"]:
            raise commands.CommandError("No tracks found for the provided query!")
        # Filter out None entries
        return filter_not_none(results["entries"])

    async def update_entry(self, entry):
        """Update a track entry in-place with a new URL and expiration time."""
        # Run the extraction in a background process
        result_queue, process = self.__start_extractor_process(entry["webpage_url"])
        result = await self.loop.run_in_executor(None, result_queue.get)
        process.join()
        log.debug("Extractor process (PID %s) finished", process.pid)

        if not result or (result["extractor"] not in ("youtube", "soundcloud")):
            raise commands.CommandError("Incorrect track URL!")
        add_expire_time(result)  # Add the expiration time to the entry
        entry.update(result)  # Update the entry in-place
