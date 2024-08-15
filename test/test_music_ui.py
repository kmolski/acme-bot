from yarl import URL

from acme_bot.music.ui import remote_embed


def test_remote_embed_has_valid_link():
    remote_id = "e2329439f3f046bf9fd6045bcccb154d"
    access_code = 123456
    embed = remote_embed(URL("https://example.com/?rcs=foo"), remote_id, access_code)
    assert embed.url == f"https://example.com/?rcs=foo&rid={remote_id}&ac={access_code}"
