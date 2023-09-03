import pytest
from pydantic import ValidationError

from acme_bot.music.player import PlayerState


async def test_run_command_throws_on_invalid_json(remote_control_module):
    with pytest.raises(ValueError):
        await remote_control_module._run_command(b"garbage")


async def test_run_command_throws_on_invalid_command(remote_control_module):
    message = b"""
        {
            "command": "null",
            "args": []
        }
    """
    with pytest.raises(ValidationError):
        await remote_control_module._run_command(message)


async def test_run_command_throws_on_nonexistent_player(remote_control_module):
    message = b"""
        {
            "op": "resume",
            "code": 1234
        }
    """
    with pytest.raises(KeyError):
        await remote_control_module._run_command(message)


async def test_run_command_pauses_on_pause_command(
    remote_control_module, player, fake_voice_client
):
    assert player.state == PlayerState.IDLE
    assert fake_voice_client.paused is False

    message = b"""
        {
            "op": "pause",
            "code": 123456
        }
    """
    await remote_control_module._run_command(message)
    assert player.state == PlayerState.PAUSED
    assert fake_voice_client.paused is True


async def test_run_command_stops_on_stop_command(
    remote_control_module, player, fake_voice_client
):
    assert player.state == PlayerState.IDLE
    assert fake_voice_client.stopped is False

    message = b"""
        {
            "op": "stop",
            "code": 123456
        }
    """
    await remote_control_module._run_command(message)
    assert player.state == PlayerState.STOPPED
    assert fake_voice_client.stopped is True


async def test_run_command_resumes_on_resume_command(
    remote_control_module, player, fake_voice_client
):
    player.pause()

    message = b"""
        {
            "op": "resume",
            "code": 123456
        }
    """
    await remote_control_module._run_command(message)
    assert player.state == PlayerState.PLAYING
    assert fake_voice_client.paused is False