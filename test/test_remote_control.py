import asyncio

from conftest import FakeAmqpMessage

from acme_bot.music.player import PlayerState


async def test_run_command_handles_invalid_json(remote_control_module):
    message = FakeAmqpMessage(b"garbage")
    await remote_control_module._run_command(message)


async def test_run_command_handles_invalid_command(remote_control_module):
    message = FakeAmqpMessage(
        b"""
        {
            "command": "null",
            "args": []
        }
        """
    )
    await remote_control_module._run_command(message)


async def test_run_command_handles_nonexistent_player(remote_control_module):
    message = FakeAmqpMessage(
        b"""
        {
            "op": "resume",
            "code": 1234
        }
        """
    )
    await remote_control_module._run_command(message)


async def test_run_command_handles_command_error(remote_control_module):
    message = FakeAmqpMessage(
        b"""
        {
            "op": "resume",
            "code": 123456
        }
        """
    )
    await remote_control_module._run_command(message)


async def test_run_command_pauses_on_pause_command(
    remote_control_module, player, fake_voice_client
):
    assert player.state == PlayerState.IDLE
    assert fake_voice_client.paused is False

    message = FakeAmqpMessage(
        b"""
        {
            "op": "pause",
            "code": 123456
        }
        """
    )
    await remote_control_module._run_command(message)
    assert player.state == PlayerState.PAUSED
    assert fake_voice_client.paused is True


async def test_run_command_stops_on_stop_command(
    remote_control_module, player, fake_voice_client
):
    assert player.state == PlayerState.IDLE
    assert fake_voice_client.stopped is False

    message = FakeAmqpMessage(
        b"""
        {
            "op": "stop",
            "code": 123456
        }
        """
    )
    await remote_control_module._run_command(message)
    assert player.state == PlayerState.STOPPED
    assert fake_voice_client.stopped is True


async def test_run_command_resumes_on_resume_command(
    remote_control_module, player, fake_voice_client
):
    player.pause()

    message = FakeAmqpMessage(
        b"""
        {
            "op": "resume",
            "code": 123456
        }
        """
    )
    await remote_control_module._run_command(message)
    assert player.state == PlayerState.PLAYING
    assert fake_voice_client.paused is False


async def test_run_command_clears_queue_on_clear_command(
    remote_control_module, player, fake_voice_client
):
    player.append({"id": 123})
    message = FakeAmqpMessage(
        b"""
        {
            "op": "clear",
            "code": 123456
        }
        """
    )
    await remote_control_module._run_command(message)
    assert player.is_empty() is True
    assert player.state == PlayerState.IDLE


async def test_run_command_sets_loop_on_loop_command(
    remote_control_module, player, fake_voice_client
):
    message = FakeAmqpMessage(
        b"""
        {
            "op": "loop",
            "enabled": false,
            "code": 123456
        }
        """
    )
    await remote_control_module._run_command(message)
    assert player.loop is False


async def test_run_command_sets_volume_on_volume_command(
    remote_control_module, player, fake_voice_client
):
    message = FakeAmqpMessage(
        b"""
        {
            "op": "volume",
            "value": 42,
            "code": 123456
        }
        """
    )
    await remote_control_module._run_command(message)
    assert player.volume == 42


async def test_remove_command_deletes_existing_entry_at_offset(
    remote_control_module, player, youtube_playlist
):
    player.extend(youtube_playlist)
    player._next(1)
    message = FakeAmqpMessage(
        b"""
        {
            "op": "remove",
            "offset": 0,
            "id": "FNKPYhXmzo0",
            "code": 123456
        }
        """
    )
    await remote_control_module._run_command(message)
    head, tail = player.get_tracks()
    assert [entry["id"] for entry in tail] == ["Ee_uujKuJM0"]
    assert head == []


async def test_remove_command_does_not_delete_if_id_isnt_matching(
    remote_control_module, player, youtube_playlist
):
    player.extend(youtube_playlist)
    message = FakeAmqpMessage(
        b"""
        {
            "op": "remove",
            "offset": 0,
            "id": "FNKPYhXmzo0",
            "code": 123456
        }
        """
    )
    await remote_control_module._run_command(message)
    head, tail = player.get_tracks()
    assert [entry["id"] for entry in head] == ["Ee_uujKuJM0", "FNKPYhXmzo0"]
    assert tail == []


async def test_move_command_moves_to_existing_entry_at_offset(
    remote_control_module, player, youtube_playlist, soundcloud_entry
):
    player.extend(youtube_playlist)
    player.append(soundcloud_entry)
    player._next(1)
    message = FakeAmqpMessage(
        b"""
        {
            "op": "move",
            "offset": 1,
            "id": "682814213",
            "code": 123456
        }
        """
    )
    await remote_control_module._run_command(message)
    assert player._next(player._MusicPlayer__next_offset)["id"] == "682814213"


async def test_move_command_does_not_move_if_id_isnt_matching(
    remote_control_module, player, youtube_playlist, soundcloud_entry
):
    player.extend(youtube_playlist)
    player.append(soundcloud_entry)
    message = FakeAmqpMessage(
        b"""
        {
            "op": "move",
            "offset": 0,
            "id": "682814213",
            "code": 123456
        }
        """
    )
    await remote_control_module._run_command(message)
    assert player._next(player._MusicPlayer__next_offset)["id"] == "FNKPYhXmzo0"


async def test_observer_close_closes_channel(player_observer, amqp_exchange):
    await player_observer.close()
    assert amqp_exchange.channel.closed is True


async def test_observer_consume_empty_message_triggers_notify(
    player_observer, player, observer
):
    await player_observer.consume(FakeAmqpMessage(b""))
    assert observer.data is player


async def test_observer_consume_other_message_does_not_notify(
    player_observer, player, observer
):
    await player_observer.consume(FakeAmqpMessage("foo"))
    assert observer.data is None


async def test_observer_update_sends_player_state(
    player_observer, player, amqp_exchange
):
    player.observer = player_observer
    player.volume = 58
    await asyncio.sleep(0.001)
    assert (
        amqp_exchange.messages[0].body
        == b'{"loop":true,"volume":58,"state":"idle","queue":[]}'
    )
