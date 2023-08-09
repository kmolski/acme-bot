"""Pydantic models for MusicPlayer's remote control messages."""
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

from typing import Literal, Union

from pydantic import BaseModel, RootModel


class RemoteCommand:
    """Template method for remote control commands."""

    op: str
    code: int

    async def run(self, player):
        """Run the remote command on the player."""
        raise NotImplementedError()


class PauseCommand(RemoteCommand, BaseModel):
    """Remote command to pause the player."""

    op: Literal["pause"]

    async def run(self, player):
        player.pause()


class StopCommand(RemoteCommand, BaseModel):
    """Remote command to stop the player."""

    op: Literal["stop"]

    async def run(self, player):
        player.stop()


class ResumeCommand(RemoteCommand, BaseModel):
    """Remote command to resume the player."""

    op: Literal["resume"]

    async def run(self, player):
        await player.resume()


class RemoteCommandModel(RootModel):
    """Root model for remote control commands."""

    root: Union[PauseCommand, StopCommand, ResumeCommand]
