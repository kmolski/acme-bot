"""External music player control using an AMQP message broker."""
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

import json
import logging
from asyncio import run_coroutine_threadsafe

import aio_pika
from aiormq.tools import censor_url
from discord.ext import commands

from acme_bot.config.properties import RABBITMQ_URI
from acme_bot.music import MusicModule
from acme_bot.autoloader import CogFactory, autoloaded


log = logging.getLogger(__name__)


@autoloaded
class ExternalControlModule(commands.Cog, CogFactory):
    """External music player control using an AMQP message broker."""

    def __init__(self, bot, uri, music_module):
        self.bot = bot
        self.uri = uri
        self.music_module = music_module

    @classmethod
    def is_available(cls):
        if not MusicModule.is_available():
            log.info("Cannot load ExternalControlModule: MusicModule not available")
            return False

        if RABBITMQ_URI.get() is None:
            log.info("Cannot load ExternalControlModule: RABBITMQ_URI is not set")
            return False

        return True

    @classmethod
    def create_cog(cls, bot):
        ext_control = cls(bot, RABBITMQ_URI(), bot.get_cog(MusicModule.__name__))
        run_coroutine_threadsafe(ext_control.__process_messages(), bot.loop)
        return ext_control

    # pylint: disable=unused-private-member
    async def __process_messages(self):
        connection = await aio_pika.connect_robust(self.uri)
        log.info("Connected to AMQP broker at '%s'", censor_url(self.uri))
        async with connection:
            channel = await connection.channel()
            exchange = await channel.declare_exchange(
                "acme_bot_remote", aio_pika.ExchangeType.FANOUT, durable=True
            )
            queue = await channel.declare_queue(auto_delete=True)
            await queue.bind(exchange)
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        log.info("Processing message '%s'", message.body)

                        try:
                            message_dict = json.loads(message.body)

                            operation = message_dict["op"]
                            access_code = message_dict["code"]

                            player = self.music_module.players_by_code[access_code]
                            if operation == "resume":
                                await player.resume()
                            elif operation == "pause":
                                player.pause()
                            elif operation == "stop":
                                player.stop()

                        except (json.JSONDecodeError, KeyError) as exc:
                            log.exception(
                                "Exception caused by message %s:",
                                message.body,
                                exc_info=exc,
                            )
