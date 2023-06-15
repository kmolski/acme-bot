"""Music command UI interactions based on discord.py View."""
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

from discord import ui, ButtonStyle

from acme_bot.music.extractor import add_expire_time
from acme_bot.music.player import PlayerState


class VerifiedView(ui.View):
    """Generic view with interaction user verification."""

    ACTION_TIMEOUT = 60.0

    def __init__(self, user, timeout):
        super().__init__(timeout=timeout)
        self.__user = user

    async def interaction_check(self, interaction, /):
        return interaction.user == self.__user


class ConfirmAddTracks(VerifiedView):
    """Confirm/cancel menu view for the play-url command."""

    def __init__(self, user, player, results):
        super().__init__(user, self.ACTION_TIMEOUT)
        self.__player = player
        self.__results = results

    @ui.button(label="Add to queue", emoji="\u2795", style=ButtonStyle.primary)
    async def add_to_queue(self, interaction, _):
        """Confirm adding tracks to the player."""
        await interaction.message.edit(
            content=f"\u2795 {len(self.__results)} tracks added to the queue.",
            view=None,
        )

        async with self.__player as player:
            for track in self.__results:
                add_expire_time(track)
            player.extend(self.__results)

            if player.state == PlayerState.IDLE:
                await player.start_player(self.__results[0])

    @ui.button(label="Cancel", emoji="\U0001F6AB", style=ButtonStyle.secondary)
    async def cancel(self, interaction, _):
        """Cancel adding tracks to the player."""
        await interaction.message.edit(
            content="\U0001F6AB *Action canceled.*", view=None
        )


class SelectTrack(VerifiedView):
    """Select menu view for the play/play-snd command."""

    def __init__(self, user, player, return_queue, results):
        super().__init__(user, timeout=self.ACTION_TIMEOUT)

        self.__player = player
        self.__return_queue = return_queue

        for index, new in enumerate(results, start=1):
            self.add_select_button(index, new)
        self.add_cancel_button()

    def add_select_button(self, index, new):
        """Create a button that adds the given track to the player."""

        async def button_pressed(interaction):
            add_expire_time(new)
            await interaction.message.edit(
                content="\u2795 **{title}** by {uploader} added to the queue.".format(
                    **new
                ),
                view=None,
            )

            async with self.__player as player:
                player.append(new)

                if player.state == PlayerState.IDLE:
                    await player.start_player(new)
            await self.__return_queue.put(new)

        button = ui.Button(label=str(index), style=ButtonStyle.secondary)
        button.callback = button_pressed
        self.add_item(button)

    def add_cancel_button(self):
        """Cancel adding tracks to the player."""

        async def button_pressed(interaction):
            await interaction.message.edit(
                content="\U0001F6AB *Action canceled.*", view=None
            )

        button = ui.Button(
            label="Cancel", emoji="\U0001F6AB", style=ButtonStyle.secondary
        )
        button.callback = button_pressed
        self.add_item(button)
