from yarl import URL

from acme_bot.music.ui import remote_embed


def test_remote_embed_has_valid_link():
    token = "e2329439f3f046bf9FD6045BCCCB154DE2329439F3F046bf9fd6045bcccb154d"
    remote_id = "e2329439f3f046bf9fd6045bcccb154d"
    access_code = 123456
    embed = remote_embed(
        URL("https://example.com/?rcs=foo"), token, remote_id, access_code
    )
    assert (
        embed.url
        == f"https://example.com/?rcs=foo&ac={access_code}&rt={token}&rid={remote_id}"
    )
