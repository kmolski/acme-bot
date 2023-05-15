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
    assert queue.next(1) == "entries"


def test_is_empty_with_empty_queue(queue):
    assert queue.is_empty() is True


def test_is_empty_with_single_track(queue_with_tracks):
    assert queue_with_tracks.is_empty() is False


def test_should_stop_with_empty_queue(queue):
    assert queue.should_stop(1) is True


def test_should_stop_with_second_track(queue_with_tracks):
    queue_with_tracks.next(1)
    assert queue_with_tracks.should_stop(1) is False


def test_should_stop_with_loop_off(queue_with_tracks):
    queue_with_tracks.loop = False
    queue_with_tracks.next(1)
    assert queue_with_tracks.should_stop(1) is True


def test_split_view_with_empty_queue(queue):
    assert queue.split_view() == ([], [], 0)


def test_split_view_with_second_track(queue_with_tracks):
    queue_with_tracks.next(1)
    assert queue_with_tracks.split_view() == (["two"], ["one"], 1)


def test_clear_removes_tracks(queue_with_tracks):
    queue_with_tracks.clear()
    assert queue_with_tracks.is_empty() is True


def test_next_with_empty_queue_throws(queue):
    with pytest.raises(IndexError):
        queue.next(1)


def test_next_advances_the_queue(queue_with_tracks):
    result = queue_with_tracks.next(1)

    assert queue_with_tracks.current == result == "two"
    assert queue_with_tracks.split_view()[1]


def test_next_with_negative_offset_returns(queue_with_tracks):
    result = queue_with_tracks.next(-1)

    assert queue_with_tracks.current == result == "two"
    assert queue_with_tracks.split_view()[1]


def test_next_with_overflow_offset_returns(queue_with_tracks):
    result = queue_with_tracks.next(201)

    assert queue_with_tracks.current == result == "two"
    assert queue_with_tracks.split_view()[1]


def test_pop_with_empty_queue_throws(queue):
    with pytest.raises(IndexError):
        queue.pop(0)


def test_pop_removes_entries(queue_with_tracks):
    assert queue_with_tracks.pop(0) == "one"
    assert queue_with_tracks.pop(0) == "two"
    assert queue_with_tracks.is_empty() is True


def test_pop_with_negative_offset_returns(queue_with_tracks):
    assert queue_with_tracks.pop(-1) == "two"


def test_pop_with_overflow_offset_returns(queue_with_tracks):
    assert queue_with_tracks.pop(201) == "two"
