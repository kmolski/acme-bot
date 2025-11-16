import pytest
from discord import VoiceProtocol
from discord.ext import commands

from conftest import StubChannel, StubVoice


async def test_loop_sets_player_loop(mock_ctx, music_module):
    result = await music_module.loop(music_module, mock_ctx, False)
    assert mock_ctx.voice_client.loop is False
    assert result is False


async def test_pause_sets_player_pause(mock_ctx, voice_client, music_module):
    await music_module.pause(music_module, mock_ctx)
    assert voice_client.paused is True


async def test_resume_unsets_player_pause(mock_ctx, voice_client, music_module):
    await voice_client.pause()
    await music_module.resume(music_module, mock_ctx)
    assert voice_client.paused is False


async def test_volume_sets_player_volume(mock_ctx, voice_client, music_module):
    await music_module.volume(music_module, mock_ctx, 50)
    assert voice_client.volume == 50


async def test_volume_throws_on_string_argument(mock_ctx, music_module):
    with pytest.raises(commands.CommandError):
        await music_module.volume(music_module, mock_ctx, "foo")


async def test_remove_throws_on_string_argument(mock_ctx, music_module):
    with pytest.raises(commands.CommandError):
        await music_module.remove(music_module, mock_ctx, "foo")


async def test_quit_channel_if_empty_sends_event(
    mock_ctx, mock_bot, voice_client, music_module
):
    before = StubVoice(StubChannel())
    after = StubVoice(None)
    music_module._MusicModule__players[before.channel.id] = voice_client
    music_module._MusicModule__access_codes[before.channel.id] = 123456
    await music_module._quit_channel_if_empty(None, before, after)

    event = mock_bot.events[1]
    assert event[0] == "acme_bot_player_deleted"
    assert event[1] == voice_client
    assert event[2] == 123456


async def test_ensure_voice_or_join_sends_event(
    mock_ctx_no_voice, mock_bot, music_module
):
    mock_ctx_no_voice.author.voice.channel.ctx = mock_ctx_no_voice
    await music_module._ensure_voice_or_join(mock_ctx_no_voice)

    event = mock_bot.events[0]
    assert event[0] == "acme_bot_player_created"
    assert isinstance(event[1], VoiceProtocol)


async def test_ensure_voice_or_join_throws(mock_ctx_no_voice, music_module):
    mock_ctx_no_voice.author.voice = None
    with pytest.raises(commands.CommandError):
        await music_module._ensure_voice_or_join(mock_ctx_no_voice)


async def test_ensure_voice_or_fail_throws(mock_ctx_no_voice, music_module):
    mock_ctx_no_voice.author.voice = None
    with pytest.raises(commands.CommandError):
        await music_module._ensure_voice_or_fail(mock_ctx_no_voice)


async def test_ensure_voice_and_non_empty_queue_throws(
    mock_ctx, voice_client, music_module
):
    with pytest.raises(commands.CommandError):
        await music_module._ensure_voice_and_non_empty_queue(mock_ctx)
