from asyncio import get_running_loop, sleep, AbstractEventLoop, Queue
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from typing import Optional

import pytest

from acme_bot.music.extractor import MusicExtractor
from acme_bot.music.player import MusicPlayer, PlayerState
from acme_bot.music.queue import MusicQueue
from acme_bot.music.ui import ConfirmAddTracks, SelectTrack
from acme_bot.shell import ShellModule
from acme_bot.textutils import send_pages


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
class StubUser:
    """Stub discord.py user account object."""

    id: int = 987654321
    name: str = "Test User"


@dataclass
class StubBot:
    """Stub discord.py bot instance object."""

    loop: AbstractEventLoop


@dataclass
class FakeVoiceClient:
    """Fake discord.py voice client object."""

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
class FakeMessage:
    """Fake discord.py message object."""

    content: str = ""
    reactions: list[str] = None
    delete_after: float = None
    view: object = None

    async def edit(self, *, content=None, delete_after=None, view=None):
        if content is not None:
            self.content = content
        if delete_after is not None:
            self.delete_after = delete_after
        if view is not None:
            self.view = view

    async def add_reaction(self, reaction):
        if self.reactions is None:
            self.reactions = []
        self.reactions.append(reaction)
        await sleep(0.1)


@dataclass
class FakeContext:
    """Fake discord.py context for testing modules that interact with the text chat."""

    messages: list[str]
    tts: list[bool]
    files: list[Optional[str]]
    delete_after: list[float]
    references: list[object]
    views: list[object]

    bot: StubBot
    author: StubUser
    message: FakeMessage
    voice_client: FakeVoiceClient
    display: bool = True

    async def send(
        self,
        content,
        *,
        tts=False,
        file=None,
        delete_after=None,
        reference=None,
        view=None
    ):
        self.messages.append(content)
        self.tts.append(tts)
        self.files.append(file)
        self.delete_after.append(delete_after)
        self.references.append(reference)
        self.views.append(view)

    async def send_pages(self, *args, **kwargs):
        await send_pages(self, *args, **kwargs)


class FakePlayer(MusicQueue):
    """Fake acme_bot MusicPlayer object."""

    def __init__(self):
        super().__init__()
        self.state = PlayerState.IDLE
        self.playing = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def start_player(self, playing):
        self.state = PlayerState.PLAYING
        self.playing = playing


@dataclass
class StubInteraction:
    """Stub discord.py interaction object."""

    message: FakeMessage


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
async def extractor(youtube_entry_query, youtube_playlist, soundcloud_entry):
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
def stub_user():
    return StubUser()


@pytest.fixture
async def stub_bot():
    return StubBot(get_running_loop())


@pytest.fixture
def fake_voice_client(stub_channel):
    return FakeVoiceClient([], stub_channel, None)


@pytest.fixture
def fake_ctx(stub_bot, stub_user, fake_message, fake_voice_client):
    return FakeContext(
        [], [], [], [], [], [], stub_bot, stub_user, fake_message, fake_voice_client
    )


@pytest.fixture
async def player(fake_ctx, extractor):
    return MusicPlayer(fake_ctx, extractor, 123456)


@pytest.fixture
async def player_with_tracks(fake_ctx, extractor, youtube_playlist):
    player = MusicPlayer(fake_ctx, extractor, 123456)
    player.extend(youtube_playlist)
    return player


@pytest.fixture
def fake_message():
    return FakeMessage()


@pytest.fixture
def fake_player():
    return FakePlayer()


@pytest.fixture
def stub_interaction(fake_message):
    return StubInteraction(fake_message)


@pytest.fixture
async def confirm_add_tracks_view(stub_user, fake_player, youtube_playlist):
    return ConfirmAddTracks(stub_user, fake_player, youtube_playlist)


@pytest.fixture
async def select_track_view(stub_user, fake_player, youtube_playlist):
    return SelectTrack(stub_user, fake_player, Queue(), youtube_playlist)


@pytest.fixture
def shell_module():
    return ShellModule()
