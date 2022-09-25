from subprocess import run


def build():
    with open(
        "acme_bot/version_info/commit.txt", mode="w", encoding="utf-8"
    ) as info_file:
        run(
            ["git", "show", "--no-patch", "--no-notes", "--pretty=%h %cs", "HEAD"],
            stdout=info_file,
        )


if __name__ == "__main__":
    build()
