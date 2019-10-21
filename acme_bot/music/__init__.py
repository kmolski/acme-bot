"""This module provides the music playback capability to the bot."""
from concurrent import futures
import logging

from discord.ext import commands

from .downloader import MusicDownloader, add_expire_time
from .player import MusicPlayer


def assemble_menu(header, entries):
    """This function creates a menu with the given header
    and information about the queue entries."""
    menu = header
    for index, entry in enumerate(entries):
        menu += "\n{}. **{title}** - {uploader}".format(index, **entry)
    return menu


def pred_select(ctx, results):
    """This function creates a predicate function for use
    with wait_for and selections from a list."""

    def pred(msg):
        return (
            msg.channel == ctx.channel
            and msg.author == ctx.author
            and msg.content.isnumeric()
            and int(msg.content) in range(0, len(results))
        )

    return pred


def pred_confirm(ctx, menu_msg):
    """This function creates a predicate function for use
    with wait_for and confirmations."""

    def pred(resp, user):
        return (
            resp.message.id == menu_msg.id
            and user == ctx.author
            and resp.emoji in ("\u2714", "\u274C")
        )

    return pred


class MusicModule(commands.Cog):
    """This module is responsible for playing music and managing playlists."""

    def __init__(self, bot):
        self.bot = bot
        self.downloader = MusicDownloader(bot.loop)
        self.__players = {}

    def __get_player(self, ctx):
        """Returns a MusicPlayer instance for the channel in the current context."""
        return self.__players[ctx.voice_client.channel.id]

    @commands.command()
    async def join(self, ctx, *, display=True):
        """Makes the bot join the user's current voice channel."""
        if display:
            await ctx.send(
                f"\u27A1 Joining voice channel **{ctx.voice_client.channel.name}**."
            )

    @commands.command()
    async def leave(self, ctx, *, display=True):
        """Removes the bot from the user's current voice channel."""
        self.__get_player(ctx).stop()
        del self.__players[ctx.voice_client.channel.id]
        logging.info(
            "Deleted the MusicPlayer instance for channel %s.",
            ctx.voice_client.channel.id,
        )
        await ctx.voice_client.disconnect()
        if display:
            await ctx.send("\u23CF Quitting the voice channel.")

    @commands.command()
    async def play(self, ctx, *query, display=True):
        """Searches for and plays a track from YouTube."""
        query = " ".join(query)
        async with ctx.typing():
            # Get video list for query
            results = await self.downloader.get_entries_by_query("ytsearch10:", query)
            # Assemble and display menu
            menu_msg = await ctx.send(
                assemble_menu("\u2049 Choose one of the following results:", results)
            )

        try:
            response = await self.bot.wait_for(
                "message", check=pred_select(ctx, results), timeout=30.0
            )
        except futures.TimeoutError:
            await menu_msg.edit(content="\u231B *Action expired.*")
            return

        new = results[int(response.content)]
        add_expire_time(new)  # Update the entry with its expiration time

        player = self.__get_player(ctx)
        player.append(new)  # Add the new entry to the player's queue

        if not player.is_busy():
            # If the player is not playing, paused or stopped, start playing
            await player.start_playing(new)
        elif display:
            await ctx.send(
                "\u2795 **{title}** by {uploader} added to the queue.".format(**new)
            )

        return new["webpage_url"]

    @commands.command(name="play-snd")
    async def play_snd(self, ctx, *query, display=True):
        """Searches for and plays a track from Soundcloud."""
        query = " ".join(query)
        async with ctx.typing():
            # Get video list for query
            results = await self.downloader.get_entries_by_query("scsearch10:", query)
            # Assemble and display menu
            menu_msg = await ctx.send(
                assemble_menu("\u2049 Choose one of the following results:", results)
            )

        try:
            response = await self.bot.wait_for(
                "message", check=pred_select(ctx, results), timeout=30.0
            )
        except futures.TimeoutError:
            await menu_msg.edit(content="\u231B *Action expired.*")
            return

        new = results[int(response.content)]
        add_expire_time(new)  # Update the entry with its expiration time

        player = self.__get_player(ctx)
        player.append(new)  # Add the new entry to the player's queue

        if not player.is_busy():
            # If the player is not playing, paused or stopped, start playing
            await player.start_playing(new)
        elif display:
            await ctx.send(
                "\u2795 **{title}** by {uploader} added to the queue.".format(**new)
            )

        return new["webpage_url"]

    @commands.command(name="play-url")
    async def play_url(self, ctx, url_list, *, display=True):
        """Plays a YouTube/Soundcloud track from the given URL."""
        url_list = str(url_list)
        async with ctx.typing():
            # Get the tracks from the given URL list
            results = await self.downloader.get_entries_by_urls(url_list.split())
            # Assemble and display menu
            menu_msg = await ctx.send(
                assemble_menu("\u2049 Do you want to add this to the queue?", results)
            )
            # Add the reactions used to confirm or cancel the action
            await menu_msg.add_reaction("\u2714")
            await menu_msg.add_reaction("\u274C")

        try:
            response, _ = await self.bot.wait_for(
                "reaction_add", check=pred_confirm(ctx, menu_msg), timeout=30.0
            )
        except futures.TimeoutError:
            await menu_msg.edit(content="\u231B *Action expired.*")
            return

        if response.emoji == "\u274C":
            await menu_msg.edit(content="\u274C *Action cancelled.*")
            return

        await menu_msg.delete()
        message = ""
        player = self.__get_player(ctx)
        player.extend(results)  # Add the new entries to the player's queue

        for elem in results:
            add_expire_time(elem)  # Update the new entry with its expiration time
            if player.is_busy():
                message += "\n**{title}** by {uploader}".format(**elem)
            else:
                # If the player is not playing, paused or stopped, start playing
                await player.start_playing(elem)

        if message and display:
            await ctx.send("\u2795 Videos added to the queue: " + message)

        return url_list

    @commands.command()
    async def back(self, ctx, offset: int = 1, **_):
        """Plays the previous video from the queue."""
        self.__get_player(ctx).move(-offset)

    @commands.command()
    async def forward(self, ctx, offset: int = 1, **_):
        """Plays the next video from the queue."""
        self.__get_player(ctx).move(offset)

    @commands.command()
    async def loop(self, ctx, should_loop: bool, *, display=True):
        """Sets looping behaviour of the player."""
        self.__get_player(ctx).loop = should_loop
        msg = "on" if should_loop else "off"
        if display:
            await ctx.send(f"\U0001F501 Playlist loop {msg}.")
        return msg

    @commands.command()
    async def pause(self, ctx, *, display=True):
        """Pauses the player."""
        self.__get_player(ctx).pause()
        if display:
            await ctx.send("\u23F8 Paused.")

    @commands.command()
    async def queue(self, ctx, *, display=True):
        """Displays the queue contents."""
        player = self.__get_player(ctx)
        if display:
            await ctx.send(player.get_queue_info())
        return player.get_queue_urls()

    @commands.command()
    async def resume(self, ctx, *, display=True):
        """Resumes the player."""
        msg = await self.__get_player(ctx).resume()
        if msg and display:
            await ctx.send(msg)

    @commands.command()
    async def shuffle(self, ctx, *, display=True):
        """Shuffles the queue contents."""
        self.__get_player(ctx).shuffle()
        if display:
            await ctx.send("\U0001F500 Queue shuffled.")

    @commands.command()
    async def clear(self, ctx, *, display=True):
        """Deletes the queue contents."""
        player = self.__get_player(ctx)
        player.stop()
        player.clear()
        if display:
            await ctx.send("\u2716 Queue cleared.")

    @commands.command()
    async def stop(self, ctx, *, display=True):
        """Stops the player."""
        self.__get_player(ctx).stop()
        if display:
            await ctx.send("\u23F9 Stopped.")

    @commands.command()
    async def volume(self, ctx, volume: int, *, display=True):
        """Changes the volume of the player."""
        self.__get_player(ctx).set_volume(volume)
        if display:
            await ctx.send(f"\U0001F4E2 Volume is now at **{volume}%**.")
        return str(volume)

    @commands.command()
    async def current(self, ctx, *, display=True):
        """Displays information about the current track."""
        current = self.__get_player(ctx).current()
        if display:
            await ctx.send(
                "\u25B6 Playing **{title}** by {uploader} now.\n{webpage_url}".format(
                    **current
                )
            )
        return current["webpage_url"]

    @commands.command()
    async def remove(self, ctx, offset: int, *, display=True):
        """Removes a track from the queue."""
        removed = self.__get_player(ctx).remove(offset)
        if display:
            await ctx.send(
                "\u2796 **{title}** by {uploader} removed from the playlist.".format(
                    **removed
                )
            )
        return removed["webpage_url"]

    @join.before_invoke
    @play.before_invoke
    @play_snd.before_invoke
    @play_url.before_invoke
    @volume.before_invoke
    async def ensure_voice_or_join(self, ctx):
        """Ensures that the author of the message is in a voice channel,
        otherwise joins the author's voice channel.
        """
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
                logging.info(
                    "Created a MusicPlayer instance for channel %s.",
                    ctx.voice_client.channel.id,
                )
                self.__players[ctx.voice_client.channel.id] = MusicPlayer(ctx, self)
            else:
                raise commands.CommandError("You are not connected to a voice channel.")

    @back.before_invoke
    @clear.before_invoke
    @current.before_invoke
    @forward.before_invoke
    @leave.before_invoke
    @loop.before_invoke
    @pause.before_invoke
    @queue.before_invoke
    @remove.before_invoke
    @resume.before_invoke
    @shuffle.before_invoke
    @stop.before_invoke
    async def ensure_voice_or_fail(self, ctx):
        """Ensures that the author of the message is in a voice channel,
        otherwise throws an exception that prevents the command from executing.
        """
        if ctx.voice_client is None:
            raise commands.CommandError("You are not connected to a voice channel.")
