import pytest
from discord.ext import commands

from acme_bot.music.player import PlayerState


def test_access_code_returns_passed_value(player):
    assert player.access_code == 123456


def test_channel_id_returns_ctx_voice_id(player):
    assert player.channel_id == 123456789


def test_state_returns_default_state(player):
    assert player.state == PlayerState.IDLE


def test_volume_returns_default_volume(player):
    assert player.volume == 100


def test_volume_setter_rejects_values_out_of_range(player):
    with pytest.raises(commands.CommandError):
        player.volume = -10
    with pytest.raises(commands.CommandError):
        player.volume = 1337


def test_volume_setter_accepts_valid_values(player, observer):
    player.volume = 50
    assert player.volume == 50
    assert observer.data is player


def test_clear_resets_state_and_queue(player_with_tracks, fake_voice_client, observer):
    player_with_tracks.pause()
    assert fake_voice_client.stopped is False
    assert player_with_tracks.is_empty() is False
    assert player_with_tracks.state == PlayerState.PAUSED

    player_with_tracks.clear()
    assert fake_voice_client.stopped is True
    assert player_with_tracks.is_empty() is True
    assert player_with_tracks.state == PlayerState.IDLE
    assert observer.data is player_with_tracks


def test_move_stops_client(player, fake_voice_client, observer):
    assert fake_voice_client.stopped is False

    player.move(10)
    assert fake_voice_client.stopped is True
    assert observer.data is player


def test_pause_sets_state_and_pauses_voice_client(player, fake_voice_client, observer):
    assert player.state == PlayerState.IDLE
    assert fake_voice_client.paused is False

    player.pause()
    assert player.state == PlayerState.PAUSED
    assert fake_voice_client.paused is True
    assert observer.data is player


def test_remove_pops_track_from_queue(player_with_tracks, youtube_playlist, observer):
    removed = player_with_tracks.remove(1)
    assert removed is youtube_playlist[1]
    assert observer.data is player_with_tracks


def test_remove_stops_after_removing_current_track(
    player_with_tracks, youtube_playlist, fake_voice_client
):
    removed = player_with_tracks.remove(0)
    assert removed is youtube_playlist[0]
    assert fake_voice_client.stopped is True


def test_remove_stops_after_removing_last_track(
    player_with_tracks, youtube_playlist, fake_voice_client
):
    assert player_with_tracks.remove(1) is youtube_playlist[1]

    removed = player_with_tracks.remove(0)
    assert removed is youtube_playlist[0]
    assert player_with_tracks.state == PlayerState.IDLE


async def test_resume_when_paused_succeeds(player_with_tracks, fake_voice_client):
    player_with_tracks.pause()
    assert fake_voice_client.paused is True
    assert player_with_tracks.state == PlayerState.PAUSED

    await player_with_tracks.resume()
    assert fake_voice_client.paused is False
    assert player_with_tracks.state == PlayerState.PLAYING


async def test_resume_when_idle_fails(player_with_tracks):
    with pytest.raises(commands.CommandError):
        await player_with_tracks.resume()


def test_stop_sets_voice_client_state(player, fake_voice_client, observer):
    assert player.state == PlayerState.IDLE
    assert fake_voice_client.stopped is False

    player.stop()
    assert player.state == PlayerState.STOPPED
    assert fake_voice_client.stopped is True
    assert observer.data is player


async def test_disconnect_sets_voice_client_state(player, fake_voice_client, observer):
    assert player.state == PlayerState.IDLE
    assert fake_voice_client.disconnected is False

    await player.disconnect()
    assert player.state == PlayerState.STOPPED
    assert fake_voice_client.disconnected is True
    assert observer.data is player
