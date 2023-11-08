from asyncio import get_running_loop, sleep, AbstractEventLoop, Queue
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field

import pytest

from acme_bot.music import MusicModule
from acme_bot.music.extractor import MusicExtractor
from acme_bot.music.player import MusicPlayer, PlayerState
from acme_bot.music.queue import MusicQueue
from acme_bot.music.ui import ConfirmAddTracks, SelectTrack
from acme_bot.remote_control import RemoteControlModule
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
    name: str = "Test Channel"
    ctx: object | None = None
    members: list[object] = field(default_factory=list)

    async def connect(self):
        if self.ctx is not None:
            self.ctx.voice_client = FakeVoiceClient([], None)


@dataclass
class StubVoice:
    """Stub discord.py voice object."""

    channel: StubChannel = field(default_factory=StubChannel)


@dataclass
class StubUser:
    """Stub discord.py user account object."""

    id: int = 987654321
    name: str = "Test User"
    voice: StubVoice = field(default_factory=StubVoice)


@dataclass
class FakeBot:
    """Stub discord.py bot instance object."""

    loop: AbstractEventLoop
    events: list[object] = field(default_factory=list)

    def dispatch(self, event, *args):
        self.events.append((event, *args))


@dataclass
class FakeVoiceClient:
    """Fake discord.py voice client object."""

    played_tracks: list[object]
    source: object | None
    stopped: bool = False
    paused: bool = False
    disconnected: bool = False
    channel: StubChannel = field(default_factory=StubChannel)

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
class StubFile:
    """Fake discord.py file object."""

    filename: str = "stub_file"
    content: bytes = b"Hello, world!\xf0\x28\x8c\xbc"

    async def read(self):
        return self.content


@dataclass
class FakeMessage:
    """Fake discord.py message object."""

    content: str = ""
    view: object = None
    delete_after: float | None = None
    reactions: list[str] = field(default_factory=list)
    attachments: list[StubFile] = field(default_factory=list)

    async def edit(self, *, content=None, delete_after=None, view=None):
        if content is not None:
            self.content = content
        if delete_after is not None:
            self.delete_after = delete_after
        if view is not None:
            self.view = view

    async def add_reaction(self, reaction):
        self.reactions.append(reaction)
        await sleep(0.1)

    def add_attachment(self, attachment):
        self.attachments.append(attachment)
        return self


class AsyncList(list):
    """Python list with an async interator interface."""

    async def __aiter__(self):
        for item in self:
            yield item


class AsyncContextManager:
    """Object with an async context manager."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False


@dataclass
class FakeAmqpMessage:
    """Fake aio_pika message object."""

    body: bytes = b""

    def process(self):
        return AsyncContextManager()


@dataclass
class FakeContext:
    """Fake discord.py context for testing modules that interact with the text chat."""

    tts: list[bool]
    messages: list[str]
    views: list[object]
    embeds: list[object]
    hist: AsyncList[object]
    references: list[object]
    delete_after: list[float]
    files: list[str | None]

    bot: FakeBot
    voice_client: FakeVoiceClient | None

    display: bool = True
    author: StubUser = field(default_factory=StubUser)
    message: FakeMessage = field(default_factory=FakeMessage)

    def history(self, **_):
        return self.hist

    def typing(self):
        return AsyncContextManager()

    async def send(
        self,
        content="",
        *,
        tts=False,
        file=None,
        delete_after=None,
        reference=None,
        embed=None,
        view=None
    ):
        self.messages.append(content)
        self.tts.append(tts)
        self.files.append(file)
        self.delete_after.append(delete_after)
        self.references.append(reference)
        self.embeds.append(embed)
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

    message: FakeMessage = field(default_factory=FakeMessage)


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
            "thumbnail": "https://i.ytimg.com/vi/Ee_uujKuJM0/hqdefault.jpg",
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
def stub_user():
    return StubUser()


@pytest.fixture
async def fake_bot():
    return FakeBot(get_running_loop())


@pytest.fixture
def fake_voice_client():
    return FakeVoiceClient([], None)


@pytest.fixture
def fake_ctx(fake_bot, fake_message, fake_voice_client):
    return FakeContext(
        [],
        [],
        [],
        [],
        AsyncList(),
        [],
        [],
        [],
        fake_bot,
        fake_voice_client,
    )


@pytest.fixture
def fake_ctx_history(fake_bot, stub_file_message, fake_voice_client):
    return FakeContext(
        [],
        [],
        [],
        [],
        AsyncList([stub_file_message]),
        [],
        [],
        [],
        fake_bot,
        fake_voice_client,
    )


@pytest.fixture
def fake_ctx_no_voice(fake_bot, fake_message):
    return FakeContext(
        [],
        [],
        [],
        [],
        AsyncList(),
        [],
        [],
        [],
        fake_bot,
        None,
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
def stub_file():
    return StubFile()


@pytest.fixture
def stub_file_message(stub_file):
    return FakeMessage().add_attachment(stub_file)


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
async def remote_control_module(fake_bot, player):
    cog = RemoteControlModule(fake_bot, None)
    await cog._register_player(player)
    return cog


@pytest.fixture
def shell_module():
    return ShellModule()


@pytest.fixture
def music_module(fake_bot, extractor, player_with_tracks):
    cog = MusicModule(fake_bot, extractor)
    cog._MusicModule__players[StubChannel.id] = player_with_tracks
    cog._MusicModule__access_codes.add(player_with_tracks.access_code)
    return cog
