import pytest


def test_current_with_empty_queue_throws(queue):
    with pytest.raises(IndexError):
        _ = queue.current


def test_current_with_first_track_returns(queue_with_tracks):
    assert queue_with_tracks.current == "one"


def test_append_to_empty_queue(queue):
    entry = "new entry"
    queue.append(entry)

    assert queue.current is entry
    assert queue.is_empty() is False


def test_extend_with_empty_list(queue):
    queue.extend([])
    assert queue.is_empty() is True


def test_extend_empty_queue(queue):
    queue.extend(["new", "entries"])

    assert queue.current == "new"
    assert queue._next(1) == "entries"


def test_is_empty_with_empty_queue(queue):
    assert queue.is_empty() is True


def test_is_empty_with_single_track(queue_with_tracks):
    assert queue_with_tracks.is_empty() is False


def test_should_stop_with_empty_queue(queue):
    assert queue._should_stop(1) is True


def test_should_stop_with_second_track(queue_with_tracks):
    queue_with_tracks._next(1)
    assert queue_with_tracks._should_stop(1) is False


def test_should_stop_with_loop_off(queue_with_tracks):
    queue_with_tracks.loop = False
    queue_with_tracks._next(1)
    assert queue_with_tracks._should_stop(1) is True


def test_get_tracks_with_empty_queue(queue):
    assert queue.get_tracks() == ([], [])


def test_get_tracks_with_second_track(queue_with_tracks):
    queue_with_tracks._next(1)
    assert queue_with_tracks.get_tracks() == (["two"], ["one"])


def test_clear_removes_tracks(queue_with_tracks):
    queue_with_tracks._clear()
    assert queue_with_tracks.is_empty() is True


def test_next_with_empty_queue_throws(queue):
    with pytest.raises(IndexError):
        queue._next(1)


def test_next_advances_the_queue(queue_with_tracks):
    result = queue_with_tracks._next(1)

    assert queue_with_tracks.current == result == "two"
    assert queue_with_tracks.get_tracks()[1]


def test_next_with_negative_offset_returns(queue_with_tracks):
    result = queue_with_tracks._next(-1)

    assert queue_with_tracks.current == result == "two"
    assert queue_with_tracks.get_tracks()[1]


def test_next_with_overflow_offset_returns(queue_with_tracks):
    result = queue_with_tracks._next(201)

    assert queue_with_tracks.current == result == "two"
    assert queue_with_tracks.get_tracks()[1]


def test_pop_with_empty_queue_throws(queue):
    with pytest.raises(IndexError):
        queue._pop(0)


def test_pop_removes_entries(queue_with_tracks):
    assert queue_with_tracks._pop(0) == "one"
    assert queue_with_tracks._pop(0) == "two"
    assert queue_with_tracks.is_empty() is True


def test_pop_with_negative_offset_returns(queue_with_tracks):
    assert queue_with_tracks._pop(-1) == "two"


def test_pop_with_overflow_offset_returns(queue_with_tracks):
    assert queue_with_tracks._pop(201) == "two"
