async def test_run_command_handles_invalid_json(test_client):
    async with test_client:
        await test_client.send_str("garbage")


async def test_run_command_handles_invalid_command(test_client):
    async with test_client:
        await test_client.send_str(
            """
            {
                "command": "null",
                "args": []
            }
            """
        )


async def test_run_command_handles_nonexistent_player(test_client):
    async with test_client:
        await test_client.send_str(
            """
            {
                "op": "resume",
                "code": 1234
            }
            """
        )


async def test_run_command_handles_command_error(test_client):
    async with test_client:
        await test_client.send_str(
            """
            {
                "op": "resume",
                "code": 123456
            }
            """
        )


async def test_run_command_pauses_on_pause_command(test_client, voice_client):
    assert voice_client.paused is False

    async with test_client:
        await test_client.send_str(
            """
            {
                "op": "pause",
                "code": 123456
            }
            """
        )
    assert voice_client.paused is True


async def test_run_command_resumes_on_resume_command(test_client, voice_client):
    await voice_client.pause()

    async with test_client:
        await test_client.send_str(
            """
            {
                "op": "resume",
                "code": 123456
            }
            """
        )
    assert voice_client.paused is False


async def test_run_command_clears_queue_on_clear_command(test_client, voice_client):
    voice_client.queue.append({"id": 123})

    async with test_client:
        await test_client.send_str(
            """
            {
                "op": "clear",
                "code": 123456
            }
            """
        )
    assert len(voice_client.queue) == 0


async def test_run_command_sets_loop_on_loop_command(test_client, voice_client):
    async with test_client:
        await test_client.send_str(
            """
            {
                "op": "loop",
                "enabled": false,
                "code": 123456
            }
            """
        )
    assert voice_client.loop is False


async def test_run_command_sets_volume_on_volume_command(test_client, voice_client):
    async with test_client:
        await test_client.send_str(
            """
            {
                "op": "volume",
                "value": 42,
                "code": 123456
            }
            """
        )
    assert voice_client.volume == 42


async def test_remove_command_deletes_existing_entry_at_offset(
    test_client, voice_client, youtube_playlist
):
    voice_client.queue.extend(youtube_playlist)

    async with test_client:
        await test_client.send_str(
            """
            {
                "op": "remove",
                "offset": 0,
                "id": "Ee_uujKuJM0",
                "code": 123456
            }
            """
        )
    assert [entry.identifier for entry in voice_client.queue] == ["FNKPYhXmzo0"]


async def test_remove_command_does_not_delete_if_id_isnt_matching(
    test_client, voice_client, youtube_playlist
):
    voice_client.queue.extend(youtube_playlist)

    async with test_client:
        await test_client.send_str(
            """
            {
                "op": "remove",
                "offset": 0,
                "id": "FNKPYhXmzo0",
                "code": 123456
            }
            """
        )
    assert [e.identifier for e in voice_client.queue] == [
        "Ee_uujKuJM0",
        "FNKPYhXmzo0",
    ]


async def test_move_command_moves_to_existing_entry_at_offset(
    test_client, voice_client, youtube_playlist
):
    voice_client.queue.extend(youtube_playlist)

    async with test_client:
        await test_client.send_str(
            """
            {
                "op": "move",
                "offset": 1,
                "id": "FNKPYhXmzo0",
                "code": 123456
            }
            """
        )
    assert voice_client.current.identifier == "FNKPYhXmzo0"


async def test_move_command_does_not_move_if_id_isnt_matching(
    test_client, voice_client, youtube_playlist
):
    voice_client.queue.extend(youtube_playlist)

    async with test_client:
        await test_client.send_str(
            """
            {
                "op": "move",
                "offset": 1,
                "id": "Ee_uujKuJM0",
                "code": 123456
            }
            """
        )
    assert voice_client.current is None


async def test_prev_command_moves_to_previous_entry(
    test_client, voice_client, youtube_playlist
):
    voice_client.current = youtube_playlist[0]
    voice_client.queue.extend(youtube_playlist[1:])

    async with test_client:
        await test_client.send_str(
            """
            {
                "op": "prev",
                "code": 123456
            }
            """
        )
    assert voice_client.current.identifier == "FNKPYhXmzo0"


async def test_skip_command_moves_to_next_entry(
    test_client, voice_client, youtube_playlist
):
    voice_client.current = youtube_playlist[0]
    voice_client.queue.extend(youtube_playlist[1:])

    async with test_client:
        await test_client.send_str(
            """
            {
                "op": "skip",
                "code": 123456
            }
            """
        )
    assert voice_client.current.identifier == "FNKPYhXmzo0"


async def test_observer_update_sends_player_state(test_client, voice_client):
    async with test_client:
        await test_client.send_str(
            """
            {
                "op": "volume",
                "value": 42,
                "code": 123456
            }
            """
        )
        assert await test_client.receive_str() == (
            '{"loop":true,"volume":42,"position":0,'
            '"state":"idle","queue":[],"current":null}'
        )
