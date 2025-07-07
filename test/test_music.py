import pytest
from discord.ext import commands

from conftest import StubChannel, StubVoice, FakeVoiceClient


async def test_loop_sets_player_loop(fake_ctx, fake_voice_client, music_module):
    result = await music_module.loop(music_module, fake_ctx, False)
    assert fake_ctx.voice_client.loop is False
    assert result is False


async def test_pause_sets_player_pause(fake_ctx, fake_voice_client, music_module):
    await music_module.pause(music_module, fake_ctx)
    assert fake_voice_client.paused is True


async def test_resume_unsets_player_pause(fake_ctx, fake_voice_client, music_module):
    await fake_voice_client.pause()
    await music_module.resume(music_module, fake_ctx)
    assert fake_voice_client.paused is False


async def test_volume_sets_player_volume(fake_ctx, fake_voice_client, music_module):
    await music_module.volume(music_module, fake_ctx, 50)
    assert fake_voice_client.volume == 50


async def test_volume_throws_on_string_argument(fake_ctx, music_module):
    with pytest.raises(commands.CommandError):
        await music_module.volume(music_module, fake_ctx, "foo")


async def test_remove_throws_on_string_argument(fake_ctx, music_module):
    with pytest.raises(commands.CommandError):
        await music_module.remove(music_module, fake_ctx, "foo")


async def test_quit_channel_if_empty_sends_event(
    fake_ctx, fake_bot, fake_voice_client, music_module
):
    before = StubVoice(StubChannel())
    after = StubVoice(None)
    music_module._MusicModule__players[before.channel.id] = fake_voice_client
    music_module._MusicModule__access_codes[before.channel.id] = 123456
    await music_module._quit_channel_if_empty(None, before, after)

    event = fake_bot.events[0]
    assert event[0] == "acme_bot_player_deleted"
    assert event[1] == fake_voice_client
    assert event[2] == 123456


async def test_ensure_voice_or_join_sends_event(
    fake_ctx_no_voice, fake_bot, music_module
):
    fake_ctx_no_voice.author.voice.channel.ctx = fake_ctx_no_voice
    await music_module._ensure_voice_or_join(fake_ctx_no_voice)

    event = fake_bot.events[0]
    assert event[0] == "acme_bot_player_created"
    assert isinstance(event[1], FakeVoiceClient)


async def test_ensure_voice_or_join_throws(fake_ctx_no_voice, music_module):
    fake_ctx_no_voice.author.voice = None
    with pytest.raises(commands.CommandError):
        await music_module._ensure_voice_or_join(fake_ctx_no_voice)


async def test_ensure_voice_or_fail_throws(fake_ctx_no_voice, music_module):
    fake_ctx_no_voice.author.voice = None
    with pytest.raises(commands.CommandError):
        await music_module._ensure_voice_or_fail(fake_ctx_no_voice)


async def test_ensure_voice_and_non_empty_queue_throws(
    fake_ctx, fake_voice_client, music_module
):
    with pytest.raises(commands.CommandError):
        await music_module._ensure_voice_and_non_empty_queue(fake_ctx)
