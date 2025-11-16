from aiohttp import web
from asyncio import get_running_loop, sleep, AbstractEventLoop
from dataclasses import dataclass, field
from multidict import CIMultiDict
from uuid import uuid4

import lavalink
import pytest

from acme_bot.music import MusicModule
from acme_bot.remote_control import (
    RemoteControlModule,
    bearer_auth_factory,
)
from acme_bot.remote_control.rmq import RmqControlModule, RmqMusicPlayerObserver
from acme_bot.shell import ShellModule
from acme_bot.textutils import send_pages


@dataclass
class StubTrack:
    """Stub lavalink.AudioTrack object."""

    identifier: str
    title: str
    author: str
    duration: int = 0
    uri: str = ""


@dataclass
class StubGuild:
    """Stub discord.py guild object."""

    id: int = 123456789

    async def change_voice_state(
        self, *, channel=None, self_mute=False, self_deaf=False
    ):
        pass


@dataclass
class StubChannel:
    """Stub discord.py voice channel object."""

    id: int = 123456789
    name: str = "Test Channel"
    ctx: object | None = None
    members: list[object] = field(default_factory=list)
    guild: StubGuild = field(default_factory=StubGuild)

    async def connect(self, *, cls):
        self.ctx.voice_client = cls(self.ctx.bot, self.ctx.guild)
        self.ctx.voice_client.cleanup = lambda: None


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
class MockBot:
    """Mock discord.py bot instance object."""

    loop: AbstractEventLoop
    music_module: object = None
    events: list[object] = field(default_factory=list)

    def dispatch(self, event, *args):
        self.events.append((event, *args))

    def get_cog(self, name):
        return self.music_module


@dataclass
class FakePlayerManager:
    """Fake lavalink.PlayerManager object."""

    players: dict[object, object] = field(default_factory=dict)

    def create(self, guild_id):
        self.players[guild_id] = MockVoiceClient([], [], [])

    def get(self, channel_id):
        return self.players[channel_id]

    async def destroy(self, guild_id):
        del self.players[guild_id]


@dataclass
class StubLavalink:
    """Stub lavalink.Client object."""

    player_manager: FakePlayerManager

    def add_event_hook(self, obj):
        pass


@dataclass
class MockVoiceClient:
    """Mock lavalink.DefaultPlayer object."""

    queue: list[StubTrack]
    played_tracks: list[object]
    observers: list[object]
    current: StubTrack = None
    loop: bool = True
    position_timestamp: int = 0
    volume: int = 100
    paused: bool = False
    is_connected: bool = True
    channel: StubChannel = field(default_factory=StubChannel)

    @property
    def channel_id(self):
        return self.channel.id

    @channel_id.setter
    def channel_id(self, value):
        self.channel.id = value

    def notify(self):
        for observer in self.observers:
            observer.send_update()

    async def disconnect(self, force=False):
        self.is_connected = False

    async def play(self, track=None, **_):
        if self.loop == lavalink.DefaultPlayer.LOOP_QUEUE and self.current:
            self.queue.append(self.current)
        self.playing = True
        self.paused = False
        if not track and self.queue:
            self.current = self.queue.pop(0)
        else:
            self.current = track

    async def skip(self):
        await self.play()

    async def stop(self):
        self.current = None

    def set_loop(self, loop):
        self.loop = loop

    async def set_pause(self, pause):
        self.paused = pause

    async def set_volume(self, volume):
        self.volume = volume


@dataclass
class StubFile:
    """Stub discord.py file object."""

    filename: str = "stub_file"
    content: bytes = b"Hello, world!\xf0\x28\x8c\xbc"

    async def read(self):
        return self.content


@dataclass
class MockMessage:
    """Mock discord.py message object."""

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
class MockContext:
    """Mock discord.py context for testing modules that interact with the text chat."""

    tts: list[bool]
    messages: list[str]
    views: list[object]
    embeds: list[object]
    hist: AsyncList[object]
    references: list[object]
    files: list[str | None]

    bot: MockBot
    voice_client: MockVoiceClient = None

    display: bool = True
    author: StubUser = field(default_factory=StubUser)
    message: MockMessage = field(default_factory=MockMessage)
    guild: StubChannel = field(default_factory=StubChannel)

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

    message: MockMessage = field(default_factory=MockMessage)


@dataclass
class MockObserver:
    """Mock observer object for remote control."""

    update_called: bool = False

    async def send_update(self):
        self.update_called = True

    async def close(self):
        pass


@pytest.fixture
def youtube_playlist():
    return [
        StubTrack("Ee_uujKuJM0", "foo", "bar"),
        StubTrack("FNKPYhXmzo0", "boo", "bar"),
    ]


@pytest.fixture
def stub_user():
    return StubUser()


@pytest.fixture
async def mock_bot():
    return MockBot(get_running_loop())


@pytest.fixture
async def fake_player_manager():
    return FakePlayerManager()


@pytest.fixture
async def stub_lavalink(fake_player_manager):
    return StubLavalink(fake_player_manager)


@pytest.fixture
def voice_client(mock_ctx):
    return mock_ctx.voice_client


@pytest.fixture
async def mock_ctx(music_module, mock_message):
    ctx = MockContext(
        [],
        [],
        [],
        [],
        AsyncList(),
        [],
        [],
        music_module.bot,
    )
    ctx.author.voice.channel.ctx = ctx
    await music_module._ensure_voice_or_join(ctx)
    return ctx


@pytest.fixture
async def mock_ctx_history(music_module, stub_file_message):
    ctx = MockContext(
        [],
        [],
        [],
        [],
        AsyncList([stub_file_message]),
        [],
        [],
        music_module.bot,
    )
    ctx.author.voice.channel.ctx = ctx
    await music_module._ensure_voice_or_join(ctx)
    return ctx


@pytest.fixture
def mock_ctx_no_voice(mock_bot, mock_message):
    return MockContext(
        [],
        [],
        [],
        [],
        AsyncList(),
        [],
        [],
        mock_bot,
    )


@pytest.fixture
def observer():
    return MockObserver()


@pytest.fixture
def mock_message():
    return MockMessage()


@pytest.fixture
def stub_file():
    return StubFile()


@pytest.fixture
def stub_file_message(stub_file):
    return MockMessage().add_attachment(stub_file)


@pytest.fixture
def stub_interaction(mock_message):
    return StubInteraction(mock_message)


@pytest.fixture
def app():
    token = "A" * 64
    return web.Application(middlewares=[bearer_auth_factory(token)])


@pytest.fixture
async def test_client(aiohttp_client, remote_control_module, app):
    client = await aiohttp_client(app)
    token = f"acme-bot.bearer.{'A' * 64}"
    headers = CIMultiDict([("Sec-WebSocket-Protocol", f"acme-bot,{token}")])
    return await client.ws_connect("/123456", headers=headers)


@pytest.fixture
async def remote_control_module(mock_bot, voice_client, app):
    cog = RemoteControlModule(mock_bot, app, None)
    await cog._register_player(voice_client, 123456)
    return cog


@pytest.fixture
async def rmq_control_module(mock_bot, voice_client):
    cog = RmqControlModule(mock_bot, None)
    await cog._register_player(voice_client, 123456)
    return cog


@pytest.fixture
def shell_module():
    return ShellModule()


@pytest.fixture
def music_module(mock_bot, stub_lavalink):
    cog = MusicModule(mock_bot, stub_lavalink)
    mock_bot.music_module = cog
    return cog


@pytest.fixture
def amqp_channel():
    return FakeAmqpChannel()


@pytest.fixture
def amqp_exchange(amqp_channel):
    return FakeAmqpExchange(amqp_channel)


@pytest.fixture
async def rmq_player_observer(amqp_exchange, voice_client):
    return RmqMusicPlayerObserver(
        amqp_exchange, voice_client, uuid4(), get_running_loop()
    )
