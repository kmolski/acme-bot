"""Pydantic models for MusicPlayer's remote control messages."""

#  Copyright (C) 2023-2024  Krzysztof Molski
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

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, RootModel
from wavelink import QueueMode


class RemoteCommand(BaseModel):
    """Template method for remote control commands."""

    op: str
    code: int

    async def run(self, player):
        """Run the remote command on the player."""
        raise NotImplementedError()


class PauseCommand(RemoteCommand):
    """Remote command to pause the player."""

    op: Literal["pause"]

    async def run(self, player):
        await player.pause(True)


class ResumeCommand(RemoteCommand):
    """Remote command to resume the player."""

    op: Literal["resume"]

    async def run(self, player):
        if not player.playing:
            await player.play(player.queue.get())
        await player.pause(False)


class ClearCommand(RemoteCommand):
    """Remote command to clear the player's queue."""

    op: Literal["clear"]

    async def run(self, player):
        player.queue.clear()


class LoopCommand(RemoteCommand):
    """Remote command to set the player's loop."""

    op: Literal["loop"]
    enabled: bool

    async def run(self, player):
        player.queue.mode = QueueMode.loop_all if self.enabled else QueueMode.normal


class VolumeCommand(RemoteCommand):
    """Remote command to set the player's volume."""

    op: Literal["volume"]
    value: Annotated[int, Field(strict=True, ge=0, le=100)]

    async def run(self, player):
        await player.set_volume(self.value)


class RemoveCommand(RemoteCommand):
    """Remote command to remove an entry from the queue."""

    op: Literal["remove"]
    offset: int
    id: str

    async def run(self, player):
        track = player.queue[self.offset]
        if track.identifier == self.id:
            player.queue.delete(self.offset)


class MoveCommand(RemoteCommand):
    """Remote command to play a specific entry in the queue."""

    op: Literal["move"]
    offset: int
    id: str

    async def run(self, player):
        track = player.queue[self.offset]
        if track.identifier == self.id:
            await player.play(track)


class SkipCommand(RemoteCommand):
    """Remote command to play the next track."""

    op: Literal["skip"]

    async def run(self, player):
        await player.skip(force=True)


class PrevCommand(RemoteCommand):
    """Remote command to play the previous track."""

    op: Literal["prev"]

    async def run(self, player):
        track = player.queue.peek()
        if history := player.queue.history:
            track = history[-1]
            if player.current in history:
                idx = history.index(player.current)
                track = history[idx - 1]
        await player.play(track)


class RemoteCommandModel(RootModel):
    """Root model for remote control commands."""

    root: Union[
        PauseCommand,
        ResumeCommand,
        ClearCommand,
        LoopCommand,
        VolumeCommand,
        RemoveCommand,
        MoveCommand,
        SkipCommand,
        PrevCommand,
    ] = Field(discriminator="op")
