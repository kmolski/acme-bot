"""Music command UI interactions based on discord.py View."""

#  Copyright (C) 2023-2025  Krzysztof Molski
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

from discord import ui, ButtonStyle, Embed

EMBED_COLOR = 0xFF0000


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
        if self.__player.current is not None:
            self.__player.queue.append(self.__results[0])
        else:
            await self.__player.play(self.__results[0])
        self.__player.queue.extend(self.__results[1:])
        self.__player.notify()
        await interaction.message.edit(
            content=f"\u2795 {len(self.__results)} tracks added to the queue.",
            view=None,
        )

    @ui.button(label="Cancel", emoji="\U0001f6ab", style=ButtonStyle.secondary)
    async def cancel(self, interaction, _):
        """Cancel adding tracks to the player."""
        await interaction.message.edit(
            content="\U0001f6ab *Action canceled.*", view=None
        )


class SelectTrack(VerifiedView):
    """Select menu view for the play/play-snd command."""

    def __init__(self, user, player, return_queue, results):
        super().__init__(user, self.ACTION_TIMEOUT)

        self.__player = player
        self.__return_queue = return_queue

        for index, new in enumerate(results, start=1):
            self.add_select_button(index, new)
        self.add_cancel_button()

    def add_select_button(self, index, new):
        """Create a button that adds the given track to the player."""

        async def button_pressed(interaction):
            if self.__player.current is not None:
                self.__player.queue.append(new)
            else:
                await self.__player.play(new)
            self.__player.notify()
            await interaction.message.edit(
                content=f"\u2795 **{new.title}** by {new.author} added to the queue.",
                view=None,
            )
            await self.__return_queue.put(new)

        button = ui.Button(label=str(index), style=ButtonStyle.secondary)
        button.callback = button_pressed
        self.add_item(button)

    def add_cancel_button(self):
        """Cancel adding tracks to the player."""

        async def button_pressed(interaction):
            await interaction.message.edit(
                content="\U0001f6ab *Action canceled.*", view=None
            )

        button = ui.Button(
            label="Cancel", emoji="\U0001f6ab", style=ButtonStyle.secondary
        )
        button.callback = button_pressed
        self.add_item(button)


def current_track_embed(current):
    """Create an embed describing the current track."""
    embed = Embed(
        title=f"\u25b6\ufe0f Now playing: {current.title}",
        description=f"by {current.author}",
        color=EMBED_COLOR,
        url=current.uri,
    )
    if current.artwork_url is not None:
        embed.set_thumbnail(url=current.artwork_url)
    return embed


def remote_embed(base_url, remote_id, access_code):
    """Create an embed with a link to the remote control application."""
    url = base_url % {"rid": remote_id, "ac": access_code}
    embed = Embed(
        title="\u27a1\ufe0f Click here to access the web player.",
        color=EMBED_COLOR,
        url=url,
    )
    return embed
