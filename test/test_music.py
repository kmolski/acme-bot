import pytest
from discord.ext import commands

from acme_bot.music import MusicPlayer, export_entry_list


async def test_leave_channel_returns_tracks(
    fake_ctx, player_with_tracks, fake_bot, music_module
):
    tracks = await music_module.leave(music_module, fake_ctx)
    with pytest.raises(KeyError):
        music_module._get_player(fake_ctx)

    event = fake_bot.events[0]
    assert event[0] == "acme_bot_player_deleted"
    assert event[1] == player_with_tracks
    assert tracks == export_entry_list(player_with_tracks.get_tracks()[0])


async def test_ensure_voice_or_join_sends_event(
    fake_ctx_no_voice, fake_bot, music_module
):
    fake_ctx_no_voice.author.voice.channel.ctx = fake_ctx_no_voice
    await music_module._ensure_voice_or_join(fake_ctx_no_voice)
    assert music_module._get_player(fake_ctx_no_voice).channel_id == 123456789

    event = fake_bot.events[0]
    assert event[0] == "acme_bot_player_created"
    assert isinstance(event[1], MusicPlayer)


async def test_ensure_voice_or_join_throws(fake_ctx_no_voice, music_module):
    fake_ctx_no_voice.author.voice = None
    with pytest.raises(commands.CommandError):
        await music_module._ensure_voice_or_join(fake_ctx_no_voice)
