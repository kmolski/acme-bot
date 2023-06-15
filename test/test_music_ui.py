from acme_bot.music.player import PlayerState


async def test_confirm_add_has_add_and_cancel_buttons(confirm_add_tracks_view):
    assert [b.label for b in confirm_add_tracks_view._children] == [
        "Add to queue",
        "Cancel",
    ]


async def test_confirm_add_adds_to_queue(
    confirm_add_tracks_view,
    fake_player,
    youtube_playlist,
    stub_interaction,
    fake_message,
):
    await confirm_add_tracks_view.add_to_queue.callback(stub_interaction)

    assert fake_message.view is None
    assert fake_player.get_tracks() == (youtube_playlist, [])
    assert fake_player.state == PlayerState.PLAYING
    assert fake_player.playing == youtube_playlist[0]


async def test_confirm_add_to_nonempty_queue(
    confirm_add_tracks_view,
    fake_player,
    youtube_playlist,
    stub_interaction,
    fake_message,
):
    track = youtube_playlist[1]
    fake_player.append(track)
    await fake_player.start_player(track)
    await confirm_add_tracks_view.add_to_queue.callback(stub_interaction)

    assert fake_message.view is None
    assert fake_player.get_tracks() == ([track] + youtube_playlist, [])
    assert fake_player.state == PlayerState.PLAYING
    assert fake_player.playing == track


async def test_confirm_add_cancels(
    confirm_add_tracks_view,
    fake_player,
    youtube_playlist,
    stub_interaction,
    fake_message,
):
    await confirm_add_tracks_view.cancel.callback(stub_interaction)

    assert fake_message.view is None
    assert fake_player.get_tracks() == ([], [])
    assert fake_player.state == PlayerState.IDLE


async def test_select_has_track_and_cancel_buttons(select_track_view):
    assert [b.label for b in select_track_view._children] == ["1", "2", "Cancel"]


async def test_select_adds_to_queue(
    select_track_view,
    fake_player,
    youtube_playlist,
    stub_interaction,
    fake_message,
):
    await select_track_view._children[1].callback(stub_interaction)
    track = youtube_playlist[1]

    assert fake_message.view is None
    assert fake_player.get_tracks() == ([track], [])
    assert fake_player.state == PlayerState.PLAYING
    assert fake_player.playing == track


async def test_select_to_nonempty_queue(
    select_track_view,
    fake_player,
    youtube_playlist,
    stub_interaction,
    fake_message,
):
    track = youtube_playlist[1]
    fake_player.append(track)
    await fake_player.start_player(track)
    await select_track_view._children[0].callback(stub_interaction)
    new = youtube_playlist[0]

    assert fake_message.view is None
    assert fake_player.get_tracks() == ([track, new], [])
    assert fake_player.state == PlayerState.PLAYING
    assert fake_player.playing == track


async def test_select_cancels(
    select_track_view, player, youtube_playlist, stub_interaction, fake_message
):
    await select_track_view._children[-1].callback(stub_interaction)

    assert fake_message.view is None
    assert player.get_tracks() == ([], [])
    assert player.state == PlayerState.IDLE
