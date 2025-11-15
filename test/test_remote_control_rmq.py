import asyncio

from conftest import FakeAmqpMessage


async def test_run_command_handles_invalid_json(rmq_control_module):
    message = FakeAmqpMessage(b"garbage")
    await rmq_control_module._run_command(message)


async def test_run_command_handles_invalid_command(rmq_control_module):
    message = FakeAmqpMessage(
        b"""
        {
            "command": "null",
            "args": []
        }
        """
    )
    await rmq_control_module._run_command(message)


async def test_run_command_handles_nonexistent_player(rmq_control_module):
    message = FakeAmqpMessage(
        b"""
        {
            "op": "resume",
            "code": 1234
        }
        """
    )
    await rmq_control_module._run_command(message)


async def test_run_command_handles_command_error(rmq_control_module):
    message = FakeAmqpMessage(
        b"""
        {
            "op": "resume",
            "code": 123456
        }
        """
    )
    await rmq_control_module._run_command(message)


async def test_run_command_pauses_on_pause_command(
    rmq_control_module, mock_voice_client
):
    assert mock_voice_client.paused is False

    message = FakeAmqpMessage(
        b"""
        {
            "op": "pause",
            "code": 123456
        }
        """
    )
    await rmq_control_module._run_command(message)
    assert mock_voice_client.paused is True


async def test_run_command_resumes_on_resume_command(
    rmq_control_module, mock_voice_client
):
    await mock_voice_client.pause()

    message = FakeAmqpMessage(
        b"""
        {
            "op": "resume",
            "code": 123456
        }
        """
    )
    await rmq_control_module._run_command(message)
    assert mock_voice_client.paused is False


async def test_run_command_clears_queue_on_clear_command(
    rmq_control_module, mock_voice_client
):
    mock_voice_client.queue.append({"id": 123})
    message = FakeAmqpMessage(
        b"""
        {
            "op": "clear",
            "code": 123456
        }
        """
    )
    await rmq_control_module._run_command(message)
    assert len(mock_voice_client.queue) == 0


async def test_run_command_sets_loop_on_loop_command(
    rmq_control_module, mock_voice_client
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
    await rmq_control_module._run_command(message)
    assert mock_voice_client.loop is False


async def test_run_command_sets_volume_on_volume_command(
    rmq_control_module, mock_voice_client
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
    await rmq_control_module._run_command(message)
    assert mock_voice_client.volume == 42


async def test_remove_command_deletes_existing_entry_at_offset(
    rmq_control_module, mock_voice_client, youtube_playlist
):
    mock_voice_client.queue.extend(youtube_playlist)
    message = FakeAmqpMessage(
        b"""
        {
            "op": "remove",
            "offset": 0,
            "id": "Ee_uujKuJM0",
            "code": 123456
        }
        """
    )
    await rmq_control_module._run_command(message)
    assert [entry.identifier for entry in mock_voice_client.queue] == ["FNKPYhXmzo0"]


async def test_remove_command_does_not_delete_if_id_isnt_matching(
    rmq_control_module, mock_voice_client, youtube_playlist
):
    mock_voice_client.queue.extend(youtube_playlist)
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
    await rmq_control_module._run_command(message)
    assert [e.identifier for e in mock_voice_client.queue] == [
        "Ee_uujKuJM0",
        "FNKPYhXmzo0",
    ]


async def test_move_command_moves_to_existing_entry_at_offset(
    rmq_control_module, mock_voice_client, youtube_playlist
):
    mock_voice_client.queue.extend(youtube_playlist)
    message = FakeAmqpMessage(
        b"""
        {
            "op": "move",
            "offset": 1,
            "id": "FNKPYhXmzo0",
            "code": 123456
        }
        """
    )
    await rmq_control_module._run_command(message)
    assert mock_voice_client.current.identifier == "FNKPYhXmzo0"


async def test_move_command_does_not_move_if_id_isnt_matching(
    rmq_control_module, mock_voice_client, youtube_playlist
):
    mock_voice_client.queue.extend(youtube_playlist)
    message = FakeAmqpMessage(
        b"""
        {
            "op": "move",
            "offset": 1,
            "id": "Ee_uujKuJM0",
            "code": 123456
        }
        """
    )
    await rmq_control_module._run_command(message)
    assert mock_voice_client.current is None


async def test_observer_close_closes_channel(rmq_player_observer, amqp_exchange):
    await rmq_player_observer.close()
    assert amqp_exchange.channel.closed is True


async def test_observer_update_sends_player_state(
    rmq_player_observer, mock_voice_client, amqp_exchange
):
    await mock_voice_client.set_volume(58)
    rmq_player_observer.send_update()
    await asyncio.sleep(0.001)
    assert amqp_exchange.messages[0].body == (
        b'{"loop":true,"volume":58,"position":0,'
        b'"state":"idle","queue":[],"current":null}'
    )
