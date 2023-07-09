from acme_bot.music.extractor import add_expire_time


def test_add_expire_time_with_youtube_query(youtube_entry_query):
    assert "expire" not in youtube_entry_query

    add_expire_time(youtube_entry_query)
    assert "expire" in youtube_entry_query
    assert youtube_entry_query["expire"] == 1523355910


def test_add_expire_time_with_soundcloud(soundcloud_entry):
    assert "expire" not in soundcloud_entry

    add_expire_time(soundcloud_entry)
    assert "expire" in soundcloud_entry
    assert soundcloud_entry["expire"] == 1582237026


def test_add_expire_time_default():
    entry = {
        "extractor": "youtube",
        "url": "https://rr4---sn-oxup5-3ufs.googlevideo.com/videoplayback",
    }

    add_expire_time(entry)
    assert "expire" in entry


async def test_get_entries_by_urls(extractor):
    results = await extractor.get_entries_by_urls(
        [
            "https://www.youtube.com/watch?v=3SdSKZFoUa0",
            "https://www.youtube.com/playlist?list=000",
            "https://soundcloud.com/baz/foo",
        ]
    )

    assert all(t["id"] is not None for t in results)
    assert all(t["title"] is not None for t in results)
    assert all(t["uploader"] is not None for t in results)
    assert all(t["duration"] is not None for t in results)
    assert all(t["webpage_url"] is not None for t in results)
    assert all(t["extractor"] is not None for t in results)
    assert all(t["duration_string"] is not None for t in results)
    assert all(t["url"] is not None for t in results)


async def test_get_entries_by_query(extractor):
    results = await extractor.get_entries_by_query("ytsearch10:", "bar")

    assert list(t["id"] for t in results) == ["Ee_uujKuJM0", "FNKPYhXmzo0"]
    assert all(t["uploader"] == "bar" for t in results)
    assert all(t["extractor"] == "youtube" for t in results)
    assert all(t["duration_string"] is not None for t in results)
    assert all(t["url"] is not None for t in results)


async def test_update_entry(extractor):
    entry = {"webpage_url": "https://www.youtube.com/watch?v=3SdSKZFoUa0"}
    assert "expire" not in entry

    await extractor.update_entry(entry)
    assert "expire" in entry
    assert entry["expire"] == 1523355910
