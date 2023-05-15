from asyncio import get_running_loop
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Optional

import pytest

from acme_bot.music.extractor import MusicExtractor
from acme_bot.music.player import MusicPlayer
from acme_bot.music.queue import MusicQueue


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
class StubChannel:
    """Stub discord.py voice channel object."""

    id: int = 123456789


@dataclass
class FakeVoiceClient:
    """Stub discord.py voice client object."""

    played_tracks: list[object]
    channel: StubChannel
    source: Optional[object]
    stopped: bool = False
    paused: bool = False
    disconnected: bool = False

    def is_playing(self):
        return not (self.stopped or self.paused)

    def pause(self):
        self.paused = True

    def stop(self):
        self.stopped = True

    def resume(self):
        self.paused = False

    async def disconnect(self):
        self.disconnected = True

    def play(self, source, **_):
        self.played_tracks.append(source)


@dataclass
class FakeContext:
    """Fake discord.py context for testing modules that interact with the text chat."""

    messages: list[str]
    files: list[Optional[str]]
    tts: list[bool]

    voice_client: FakeVoiceClient

    async def send(self, content, *, tts=False, file=None):
        self.messages.append(content)
        self.files.append(file)
        self.tts.append(tts)


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
        "https://www.youtube.com/playlist?list=000": {
            "extractor": "youtube:playlist",
            "entries": youtube_playlist,
        },
        "https://www.youtube.com/watch?v=Ee_uujKuJM0": youtube_playlist[0],
        "https://soundcloud.com/baz/foo": soundcloud_entry,
        "ytsearch10:bar": {"entries": youtube_playlist},
    }
    executor = ProcessPoolExecutor(
        initializer=MusicExtractor.init_downloader,
        initargs=(StubYoutubeDL, stub_config),
    )
    return MusicExtractor(executor, get_running_loop())


@pytest.fixture
def stub_channel():
    return StubChannel()


@pytest.fixture
def fake_voice_client(stub_channel):
    return FakeVoiceClient([], stub_channel, None)


@pytest.fixture
def fake_ctx(fake_voice_client):
    return FakeContext([], [], [], fake_voice_client)


@pytest.fixture
async def player(fake_ctx, stub_extractor):
    return MusicPlayer(fake_ctx, stub_extractor, 123456)


@pytest.fixture
async def player_with_tracks(fake_ctx, stub_extractor, youtube_playlist):
    player = MusicPlayer(fake_ctx, stub_extractor, 123456)
    player.extend(youtube_playlist)
    return player
