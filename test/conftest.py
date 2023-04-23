from asyncio import get_running_loop
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Optional

import pytest

from acme_bot.music import MusicExtractor
from acme_bot.music.queue import MusicQueue


@pytest.fixture
def queue():
    return MusicQueue()


@pytest.fixture
def queue_with_tracks():
    queue = MusicQueue()
    queue.extend(["one", "two"])
    return queue


@pytest.fixture
def youtube_entry_query():
    return {
        "id": "3SdSKZFoUa0",
        "title": "baz",
        "uploader": "moo",
        "duration": 5178,
        "webpage_url": "https://www.youtube.com/watch?v=3SdSKZFoUa0",
        "extractor": "youtube",
        "duration_string": "1:26:18",
        "url": (
            "https://rr3---sn-oxup5-f5fz.googlevideo.com/videoplayback"
            + "?expire=1523355910"
        ),
    }


@pytest.fixture
def youtube_playlist():
    return [
        {
            "id": "Ee_uujKuJM0",
            "title": "foo",
            "uploader": "bar",
            "duration": 182,
            "webpage_url": "https://www.youtube.com/watch?v=Ee_uujKuJM0",
            "extractor": "youtube",
            "duration_string": "3:02",
            "url": (
                "https://rr3---sn-oxup5-3ufs.googlevideo.com/videoplayback"
                + "?expire=1582257033"
            ),
        },
        {
            "id": "FNKPYhXmzo0",
            "title": "boo",
            "uploader": "bar",
            "duration": 546,
            "webpage_url": "https://www.youtube.com/watch?v=FNKPYhXmzo0",
            "extractor": "youtube",
            "duration_string": "9:06",
            "url": (
                "https://rr4---sn-oxup5-3ufs.googlevideo.com/videoplayback"
                + "?expire=1582257034"
            ),
        },
    ]


@pytest.fixture
def soundcloud_entry():
    return {
        "id": "682814213",
        "title": "foo",
        "uploader": "baz",
        "duration": 226.346,
        "webpage_url": "https://soundcloud.com/baz/foo",
        "extractor": "soundcloud",
        "duration_string": "3:46",
        "url": (
            "https://cf-media.sndcdn.com/gCPqnjg6U9c1.128.mp3?Policy=eyJTdGF0ZW1lbn"
            + "QiOiBbeyJSZXNvdXJjZSI6ICIqOi8vY2YtbWVkaWEuc25kY2RuLmNvbS9nQ1BxbmpnNlU5"
            + "YzEuMTI4Lm1wMyoiLCAiQ29uZGl0aW9uIjogeyJEYXRlTGVzc1RoYW4iOiB7IkFXUzpFcG"
            + "9jaFRpbWUiOiAxNTgyMjM3MDI2fX19XX0_"
        ),
    }


@pytest.fixture
async def stub_extractor(youtube_entry_query, youtube_playlist, soundcloud_entry):
    stub_config = {
        "https://www.youtube.com/watch?v=3SdSKZFoUa0": youtube_entry_query,
        "https://www.youtube.com/playlist?list=000": {"entries": youtube_playlist},
        "https://soundcloud.com/baz/foo": soundcloud_entry,
    }
    executor = ProcessPoolExecutor(
        initializer=MusicExtractor.init_downloader,
        initargs=(StubYoutubeDL, stub_config),
    )
    return MusicExtractor(executor, get_running_loop())


@pytest.fixture
def fake_ctx():
    return FakeContext([], [], [])


@dataclass
class StubYoutubeDL:
    """Stub YoutubeDL object for testing modules using the yt-dlp library."""

    responses: dict[str, object]

    def extract_info(self, url, **_):
        try:
            return self.responses[url]
        except KeyError:
            return None


@dataclass
class FakeContext:
    """Fake discord.py context for testing modules that interact with the text chat."""

    messages: list[str]
    files: list[Optional[str]]
    tts: list[bool]

    async def send(self, content, *, tts=False, file=None):
        self.messages.append(content)
        self.files.append(file)
        self.tts.append(tts)
