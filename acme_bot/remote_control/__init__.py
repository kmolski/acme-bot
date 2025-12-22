"""Remote music player control over WebSockets."""

#  Copyright (C) 2025  Krzysztof Molski
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

import logging
from asyncio import Lock, run_coroutine_threadsafe
from random import choices
from string import hexdigits

from aiohttp import WSMsgType, web
from discord.ext import commands
from pydantic import ValidationError

from acme_bot.autoloader import CogFactory, autoloaded
from acme_bot.config.properties import MUSIC_REMOTE_PORT
from acme_bot.music import MusicModule
from acme_bot.music.schema import PlayerModel
from acme_bot.remote_control.schema import RemoteCommandModel

log = logging.getLogger(__name__)


def bearer_auth_factory(token):
    """Middleware for bearer token authentication."""

    expected_value = f"acme-bot.bearer.{token}"

    @web.middleware
    async def bearer_auth(request, handler):
        values = request.headers.getall("Sec-WebSocket-Protocol", [])
        if not any(expected_value in val for val in values):
            raise web.HTTPUnauthorized()
        return await handler(request)

    return bearer_auth


class MusicPlayerObserver:
    """Observer class for communicating MusicPlayer changes to clients."""

    def __init__(self, player, ws, loop):
        self.__player = player
        self.__ws = ws
        self.__loop = loop

    def send_update(self):
        """Send a state update to the WebSocket client."""
        player_state = PlayerModel.serialize(self.__player)
        run_coroutine_threadsafe(self.__ws.send_str(player_state), self.__loop)

    async def close(self):
        """Close the WebSocket connection."""
        await self.__ws.close()


@autoloaded
class RemoteControlModule(commands.Cog, CogFactory):
    """Remote music player control over WebSockets."""

    TOKEN_LENGTH = 32

    def __init__(self, bot, app, runner):
        self.__lock = Lock()
        self.__players = {}

        self.__bot = bot
        self.__app = app
        self.__app.add_routes([web.get("/{access_code:\\d+}", self._handle_ws)])
        self.__runner = runner

    @classmethod
    def is_available(cls):
        if not MusicModule.is_available():
            log.info("Cannot load RemoteControlModule: MusicModule not available")
            return False

        return True

    @classmethod
    async def create_cog(cls, bot):
        token = "".join(choices(hexdigits, k=cls.TOKEN_LENGTH))
        app = web.Application(middlewares=[bearer_auth_factory(token)])
        runner = web.AppRunner(app)
        cog = cls(bot, app, runner)
        await runner.setup()
        server = web.TCPSite(runner, port=MUSIC_REMOTE_PORT())
        await server.start()
        bot.dispatch("acme_bot_remote_token", token)
        return cog

    async def cog_unload(self):
        await self.__runner.cleanup()

    @commands.Cog.listener("on_acme_bot_player_created")
    async def _register_player(self, player, access_code):
        async with self.__lock:
            self.__players[access_code] = player

    @commands.Cog.listener("on_acme_bot_player_deleted")
    async def _delete_player(self, player, access_code):
        async with self.__lock:
            for observer in player.observers:
                await observer.close()
            del self.__players[access_code]

    async def _handle_ws(self, request):
        ws = web.WebSocketResponse(protocols=["acme-bot"])
        await ws.prepare(request)
        log.info("Listening for remote commands from %s", ws.get_extra_info("peername"))

        access_code = int(request.match_info["access_code"])
        player = self.__players[access_code]
        observer = MusicPlayerObserver(player, ws, self.__bot.loop)
        player.observers.append(observer)

        async for message in ws:
            if message.type == WSMsgType.TEXT:
                await self._run_command(player, message.data)
            else:
                log.error("Message type is not TEXT: %s", message)
        return ws

    async def _run_command(self, player, message):
        log.debug("Received message: %s", message)
        try:
            command = RemoteCommandModel.model_validate_json(message).root
            async with self.__lock:
                await command.run(player)
        except KeyError as exc:
            log.debug("Invalid access code: '%s'", exc.args[0])
        except (ValidationError, ValueError) as exc:
            log.exception("Invalid command: %s", message, exc_info=exc)
        except (commands.CommandError, IndexError) as exc:
            log.exception("Command failed: %s", message, exc_info=exc)
