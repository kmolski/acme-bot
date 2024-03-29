#  Copyright (C) 2022-2023  Krzysztof Molski
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

from subprocess import run


def build():
    with open(
        "acme_bot/version_info/commit.txt", mode="w", encoding="utf-8"
    ) as info_file:
        run(
            ["git", "show", "--no-patch", "--no-notes", "--pretty=%h %cs", "HEAD"],
            stdout=info_file,
            check=True,
        )


if __name__ == "__main__":
    build()
