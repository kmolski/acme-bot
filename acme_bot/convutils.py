"""Data conversion functions used by shell commands."""

#  Copyright (C) 2023  Krzysztof Molski
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


from discord.ext import commands


def to_int(value):
    """Convert a shell value (str, int, bool or None) to an integer."""
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise commands.CommandError(f"Invalid integer: {value}") from exc
