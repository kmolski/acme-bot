"""Remote music player control using an AMQP message broker."""

#  Copyright (C) 2022-2025  Krzysztof Molski
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
from uuid import uuid4

import aio_pika
from aiormq.tools import censor_url
from discord.ext import commands
from pydantic import ValidationError

from acme_bot.autoloader import CogFactory, autoloaded
from acme_bot.config.properties import RABBITMQ_URI
from acme_bot.music import MusicModule
from acme_bot.music.schema import PlayerModel
from acme_bot.remote_control.schema import RemoteCommandModel

log = logging.getLogger(__name__)


class RmqMusicPlayerObserver:
    """Observer class for communicating MusicPlayer changes to RabbitMQ."""

    def __init__(self, exchange, player, route, loop):
        self.__exchange = exchange
        self.__player = player
        self.__route = route
        self.__loop = loop

    def send_update(self):
        """Send a state update to all clients subscribing to the MusicPlayer."""
        player_state = PlayerModel.serialize(self.__player)
        message = aio_pika.Message(
            body=player_state.encode(),
            content_type="application/json",
            content_encoding="utf-8",
        )
        run_coroutine_threadsafe(
            self.__exchange.publish(message, self.__route), self.__loop
        )

    async def consume(self, message):
        """Process messages from a remote control client."""
        if not message.body:
            self.send_update()

    async def close(self):
        """Close the RabbitMQ channel, exchanges and queues."""
        await self.__exchange.channel.close()


@autoloaded
class RmqControlModule(commands.Cog, CogFactory):
    """Remote music player control using an AMQP message broker."""

    def __init__(self, bot, connection):
        self.__lock = Lock()
        self.__players = {}

        self.__bot = bot
        self.__uuid = uuid4()
        self.__connection = connection

    @classmethod
    def is_available(cls):
        if not MusicModule.is_available():
            log.info("Cannot load RmqControlModule: MusicModule not available")
            return False

        if RABBITMQ_URI.get() is None:
            log.info("Cannot load RmqControlModule: RABBITMQ_URI is not set")
            return False

        return True

    @classmethod
    async def create_cog(cls, bot):
        connection = await aio_pika.connect_robust(RABBITMQ_URI())
        return cls(bot, connection)

    async def cog_load(self):
        await self.__declare_command_queue()
        self.__connection.reconnect_callbacks.add(self.__declare_command_queue)
        self.__bot.dispatch("acme_bot_rmq_id", self.__uuid.hex)

    async def cog_unload(self):
        await self.__connection.close()

    @commands.Cog.listener("on_acme_bot_player_created")
    async def _register_player(self, player, access_code):
        async with self.__lock:
            self.__players[access_code] = player

    @commands.Cog.listener("on_acme_bot_player_created")
    async def _bind_player_observer(self, player, access_code):
        channel = await self.__connection.channel()
        exchange = await channel.declare_exchange(
            "acme_bot_remote_update", type=aio_pika.ExchangeType.TOPIC, durable=True
        )
        route = f"{self.__uuid.hex}.{access_code}"
        observer = RmqMusicPlayerObserver(exchange, player, route, self.__bot.loop)
        queue = await channel.declare_queue(auto_delete=True)
        await queue.bind(exchange, route)
        await queue.consume(observer.consume)
        player.observers.append(observer)

    @commands.Cog.listener("on_acme_bot_player_deleted")
    async def _delete_player(self, player, access_code):
        async with self.__lock:
            for observer in player.observers:
                await observer.close()
            del self.__players[access_code]

    # pylint: disable=duplicate-code
    async def _run_command(self, message):
        async with message.process():
            content = message.body
            log.debug("Received message: %s", content)
            try:
                command = RemoteCommandModel.model_validate_json(content).root
                async with self.__lock:
                    await command.run(self.__players[command.code])
            except KeyError as exc:
                log.debug("Invalid access code: '%s'", exc.args[0])
            except (ValidationError, ValueError) as exc:
                log.exception("Invalid command: %s", content, exc_info=exc)
            except (commands.CommandError, IndexError) as exc:
                log.exception("Command failed: %s", content, exc_info=exc)

    async def __declare_command_queue(self, *_):
        log.info("Connected to AMQP broker at '%s'", censor_url(self.__connection.url))
        channel = await self.__connection.channel()
        exchange = await channel.declare_exchange("acme_bot_remote", durable=True)
        queue = await channel.declare_queue(auto_delete=True)
        await queue.bind(exchange, routing_key=self.__uuid.hex)
        await queue.consume(self._run_command)
        log.info("Listening for remote commands with ID %s", self.__uuid.hex)
