"""Remote music player control using an AMQP message broker."""
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

import logging
from asyncio import Lock

import aio_pika
from aiormq.tools import censor_url
from discord.ext import commands
from pydantic import ValidationError

from acme_bot.autoloader import CogFactory, autoloaded
from acme_bot.config.properties import RABBITMQ_URI
from acme_bot.music import MusicModule
from acme_bot.remote_control.schema import RemoteCommandModel

log = logging.getLogger(__name__)


@autoloaded
class RemoteControlModule(commands.Cog, CogFactory):
    """Remote music player control using an AMQP message broker."""

    def __init__(self, bot, connection):
        self.__lock = Lock()
        self.__players = {}

        self.__bot = bot
        self.__connection = connection

    @classmethod
    def is_available(cls):
        if not MusicModule.is_available():
            log.info("Cannot load RemoteControlModule: MusicModule not available")
            return False

        if RABBITMQ_URI.get() is None:
            log.info("Cannot load RemoteControlModule: RABBITMQ_URI is not set")
            return False

        return True

    @classmethod
    async def create_cog(cls, bot):
        connection = await aio_pika.connect_robust(RABBITMQ_URI())
        ext_control = cls(bot, connection)
        return ext_control

    async def cog_load(self):
        self.__connection.reconnect_callbacks.add(self.__handle_command_stream)
        self.__bot.loop.create_task(self.__handle_command_stream())

    async def cog_unload(self):
        await self.__connection.close()

    @commands.Cog.listener("on_acme_bot_player_created")
    async def _register_player(self, player):
        async with self.__lock:
            self.__players[player.access_code] = player

    @commands.Cog.listener("on_acme_bot_player_deleted")
    async def _delete_player(self, player):
        async with self.__lock:
            del self.__players[player.access_code]

    async def _run_command(self, message):
        log.debug("Received message: %s", message)
        try:
            command = RemoteCommandModel.model_validate_json(message).root
            async with self.__lock, self.__players[command.code] as player:
                await command.run(player)
        except KeyError as exc:
            log.debug("Invalid access code: '%s'", exc.args[0])
        except (ValidationError, ValueError) as exc:
            log.exception("Invalid command: %s", message, exc_info=exc)
        except (commands.CommandError, IndexError) as exc:
            log.exception("Command failed: %s", message, exc_info=exc)

    async def __handle_command_stream(self, *_):
        log.info("Connected to AMQP broker at '%s'", censor_url(self.__connection.url))
        async with self.__connection:
            channel = await self.__connection.channel()
            exchange = await channel.declare_exchange(
                "acme_bot_remote", aio_pika.ExchangeType.FANOUT, durable=True
            )
            queue = await channel.declare_queue(auto_delete=True)
            await queue.bind(exchange)
            async with queue.iterator() as message_stream:
                async for msg in message_stream:
                    async with msg.process():
                        await self._run_command(msg.body)
