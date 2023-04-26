"""Track extractor based on YoutubeDL and Python multiprocessing."""
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
from asyncio import gather
from base64 import b64decode
from json import loads
from os import getpid
from pathlib import PurePosixPath
from time import time
from typing import Optional
from urllib.parse import urlparse, parse_qs

import yt_dlp
from discord.ext import commands

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
                # Sometimes it's a part of the URL path, not sure that it's
                # always the case since I've only seen that happen once.
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


def filter_not_none(iterable):
    """Remove None values from `iterable`."""
    return [entry for entry in iterable if entry is not None]


class MusicExtractor:
    """Track extractor based on YoutubeDL and Python multiprocessing."""

    __ALLOWED_URL_EXTRACTORS = (
        "youtube:playlist",
        "youtube:tab",
        "soundcloud:playlist",
        "soundcloud:set",
    )
    __DOWNLOADER: Optional[yt_dlp.YoutubeDL] = None

    def __init__(self, executor, loop):
        self.__executor = executor
        self.__loop = loop

    @classmethod
    def _extract_in_subprocess(cls, url):
        return cls.__DOWNLOADER.extract_info(url, download=False)

    @classmethod
    def init_downloader(cls, constructor, *args):
        """Initialize the YoutubeDL instance for the current worker process."""
        cls.__DOWNLOADER = constructor(*args)
        log.info("Created the YoutubeDL instance for worker (PID %s)", getpid())

    def shutdown_executor(self):
        """Clean up the executor associated with this MusicExtractor."""
        log.info("Shutting down ProcessPoolExecutor for MusicExtractor")
        self.__executor.shutdown(cancel_futures=True)

    async def get_entries_by_urls(self, url_list):
        """Extract the track entries from the given URLs."""
        futures = [
            self.__loop.run_in_executor(
                self.__executor, self._extract_in_subprocess, url
            )
            for url in url_list
        ]
        results = []

        for result in await gather(*futures):
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
        results = await self.__loop.run_in_executor(
            self.__executor, self._extract_in_subprocess, provider + query
        )

        if not results or not results["entries"]:
            raise commands.CommandError("No tracks found for the provided query!")
        return filter_not_none(results["entries"])

    async def update_entry(self, entry):
        """Update a track entry in-place with a new URL and expiration time."""
        result = await self.__loop.run_in_executor(
            self.__executor, self._extract_in_subprocess, entry["webpage_url"]
        )

        if not result or (result["extractor"] not in ("youtube", "soundcloud")):
            raise commands.CommandError("Incorrect track URL!")
        add_expire_time(result)  # Add the expiration time to the entry
        entry.update(result)  # Update the entry in-place
