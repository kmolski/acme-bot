import pytest
from discord.ext import commands

from acme_bot.music import MusicPlayer, export_entry_list
from acme_bot.music.player import PlayerState


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


async def test_list_urls_extracts_track_urls(fake_ctx, music_module):
    urls = await music_module.list_urls(
        music_module,
        fake_ctx,
        "https://soundcloud.com/baz/foo #comment",
        "https://www.youtube.com/watch?v=3SdSKZFoUa0",
    )
    expected = "\n".join(
        [
            "https://soundcloud.com/baz/foo    foo - 3:46",
            "https://www.youtube.com/watch?v=3SdSKZFoUa0    baz - 1:26:18",
            "",
        ]
    )
    assert urls == expected


async def test_list_urls_throws_on_empty_list(fake_ctx, music_module):
    with pytest.raises(commands.CommandError):
        await music_module.list_urls(music_module, fake_ctx)


async def test_previous_throws_on_string_argument(fake_ctx, music_module):
    with pytest.raises(commands.CommandError):
        await music_module.previous(music_module, fake_ctx, "foo")


async def test_skip_throws_on_string_argument(fake_ctx, music_module):
    with pytest.raises(commands.CommandError):
        await music_module.skip(music_module, fake_ctx, "foo")


async def test_loop_sets_player_loop(fake_ctx, player_with_tracks, music_module):
    result = await music_module.loop(music_module, fake_ctx, False)
    assert player_with_tracks.loop is False
    assert result is False


async def test_pause_sets_player_pause(fake_ctx, player_with_tracks, music_module):
    await music_module.pause(music_module, fake_ctx)
    assert player_with_tracks.state is PlayerState.PAUSED


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
