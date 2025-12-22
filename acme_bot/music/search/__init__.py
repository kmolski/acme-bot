"""Music player commands."""

#  Copyright (C) 2025  Krzysztof Molski
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
import os

import mutagen
import psycopg
from discord.ext import commands

from acme_bot.autoloader import CogFactory, autoloaded
from acme_bot.config.properties import MUSIC_SEARCH_DB_URL, MUSIC_SEARCH_PATH

log = logging.getLogger(__name__)


@autoloaded
class TrackSearch(commands.Cog, CogFactory):
    def __init__(self):
        pass

    @classmethod
    def is_available(cls):
        if MUSIC_SEARCH_DB_URL.get() is None or MUSIC_SEARCH_PATH.get() is None:
            return False

        return True

    @classmethod
    async def create_cog(cls, bot):
        return cls()

    async def cog_load(self):
        with psycopg.connect(str(MUSIC_SEARCH_DB_URL())) as conn:
            with conn.cursor() as cur:
                for root, _, files in os.walk(MUSIC_SEARCH_PATH()):
                    for file in files:
                        if file.lower().endswith((".mp3", ".flac", ".m4a")):
                            full_path = str(os.path.join(root, file))
                            self._process_file(cur, full_path)
            conn.commit()

    async def cog_unload(self):
        pass

    def _process_file(self, cursor, filepath):
        try:
            metadata = self._extract_metadata(filepath)
            sql = """
                INSERT INTO track (path, title, artist, album)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (path)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    artist = EXCLUDED.artist,
                    album = EXCLUDED.album;
            """
            cursor.execute(
                sql,
                (
                    filepath,
                    metadata.get("title"),
                    metadata.get("artist"),
                    metadata.get("album"),
                ),
            )
            log.info("Updated metadata for %s, %s", filepath, metadata)
        except Exception as e:
            log.exception("Failed to index %s", filepath, exc_info=e)

    def _extract_metadata(self, filepath):
        tags = {}
        try:
            audio = mutagen.File(filepath, easy=True)
            if audio:
                tags["title"] = audio.get("title", [None])[0]
                tags["artist"] = audio.get("artist", [None])[0]
                tags["album"] = audio.get("album", [None])[0]
        except Exception:
            pass
        return tags
