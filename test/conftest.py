from asyncio import get_running_loop, sleep, AbstractEventLoop
from dataclasses import dataclass, field
from uuid import uuid4

import pytest
import wavelink

from acme_bot.music import MusicModule
from acme_bot.remote_control import RemoteControlModule, MusicPlayerObserver
from acme_bot.shell import ShellModule
from acme_bot.textutils import send_pages


@dataclass
class StubChannel:
    """Stub discord.py voice channel object."""

    id: int = 123456789
    name: str = "Test Channel"
    ctx: object | None = None
    members: list[object] = field(default_factory=list)

    async def connect(self, *, cls):
        if self.ctx is not None:
            self.ctx.voice_client = FakeVoiceClient(FakeQueue(), None)


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


class FakeQueue(list):
    """Fake wavelink.Queue object."""

    def __init__(self):
        super().__init__()
        self.mode = wavelink.QueueMode.loop_all

    def get(self):
        return None

    @property
    def is_empty(self):
        return len(self) == 0


@dataclass
class FakeVoiceClient:
    """Fake wavelink.Player object."""

    queue: FakeQueue
    played_tracks: list[object]
    current: object = None
    position: int = 0
    volume: int = 100
    playing: bool = False
    paused: bool = False
    disconnected: bool = False
    channel: StubChannel = field(default_factory=StubChannel)

    def is_playing(self):
        return not (self.stopped or self.paused)

    async def disconnect(self):
        self.disconnected = True

    async def play(self, track, **_):
        self.played_tracks.append(track)
        self.playing = True
        self.paused = False
        self.current = track

    async def pause(self, toggle):
        self.paused = toggle

    async def set_volume(self, volume):
        self.volume = volume


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
class FakeAmqpChannel:
    """Fake aio_pika channel object."""

    closed: bool = False

    async def close(self):
        self.closed = True


@dataclass
class FakeAmqpExchange:
    """Fake aio_pika exchange object."""

    channel: FakeAmqpChannel
    messages: list[object] = field(default_factory=list)

    async def publish(self, message, key):
        self.messages.append(message)


@dataclass
class FakeContext:
    """Fake discord.py context for testing modules that interact with the text chat."""

    tts: list[bool]
    messages: list[str]
    views: list[object]
    embeds: list[object]
    hist: AsyncList[object]
    references: list[object]
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
        self, content="", *, tts=False, file=None, reference=None, embed=None, view=None
    ):
        self.messages.append(content)
        self.tts.append(tts)
        self.files.append(file)
        self.references.append(reference)
        self.embeds.append(embed)
        self.views.append(view)

    async def send_pages(self, *args, **kwargs):
        await send_pages(self, *args, **kwargs)


@dataclass
class StubInteraction:
    """Stub discord.py interaction object."""

    message: FakeMessage = field(default_factory=FakeMessage)


@dataclass
class StubObserver:
    """Stub observer object for remote control."""

    data: object = None

    def update(self, data):
        self.data = data

    async def close(self):
        pass


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
            "uploader_url": "https://example.com",
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
            "uploader_url": "https://example.com",
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
def stub_user():
    return StubUser()


@pytest.fixture
async def fake_bot():
    return FakeBot(get_running_loop())


@pytest.fixture
def fake_voice_client():
    return FakeVoiceClient(FakeQueue(), [])


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
        fake_bot,
        None,
    )


@pytest.fixture
def observer():
    return StubObserver()


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
def stub_interaction(fake_message):
    return StubInteraction(fake_message)


@pytest.fixture
async def remote_control_module(fake_bot, fake_voice_client):
    cog = RemoteControlModule(fake_bot, None)
    await cog._register_player(fake_voice_client)
    return cog


@pytest.fixture
def shell_module():
    return ShellModule()


@pytest.fixture
def music_module(fake_bot, fake_voice_client):
    cog = MusicModule(fake_bot)
    cog._MusicModule__players[StubChannel.id] = fake_voice_client
    cog._MusicModule__access_codes[123456] = fake_voice_client
    return cog


@pytest.fixture
def amqp_channel():
    return FakeAmqpChannel()


@pytest.fixture
def amqp_exchange(amqp_channel):
    return FakeAmqpExchange(amqp_channel)


@pytest.fixture
async def player_observer(amqp_exchange, fake_voice_client):
    return MusicPlayerObserver(
        amqp_exchange, fake_voice_client, uuid4(), get_running_loop()
    )
