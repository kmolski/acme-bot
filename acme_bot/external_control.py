import json
import logging
from asyncio import run_coroutine_threadsafe

import aio_pika
from discord.ext import commands

from acme_bot.config import RABBITMQ_URI
from acme_bot.music import MusicModule
from acme_bot.autoloader import CogFactory, autoloaded


@autoloaded
class ExternalControlModule(commands.Cog, CogFactory):
    def __init__(self, bot, uri, music_module):
        self.bot = bot
        self.uri = uri
        self.music_module = music_module

    @classmethod
    def is_available(cls):
        if not MusicModule.is_available():
            logging.info(
                "MusicModule could not be loaded. Disabling ExternalControlModule."
            )
            return False

        if RABBITMQ_URI.get() is None:
            logging.info(
                "RABBITMQ_URI config property not found. "
                "Disabling ExternalControlModule."
            )
            return False

        return True

    @classmethod
    def create_cog(cls, bot):
        ext_control = cls(bot, RABBITMQ_URI(), bot.get_cog(MusicModule.__name__))
        run_coroutine_threadsafe(ext_control.__process_messages(), bot.loop)
        return ext_control

    async def __process_messages(self):
        logging.info("Connecting to AMQP broker at '%s'.", self.uri)
        connection = await aio_pika.connect_robust(self.uri)
        async with connection:
            channel = await connection.channel()
            queue = await channel.declare_queue("music_player", auto_delete=True)
            async with queue.iterator() as queue_iter:
                async for message in queue_iter:
                    async with message.process():
                        logging.info("Processing message %s", message.body)

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
                            logging.exception(
                                "Exception caused by message %s:",
                                message.body,
                                exc_info=exc,
                            )
