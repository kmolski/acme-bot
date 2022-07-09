import json
import logging
from asyncio import run_coroutine_threadsafe

import aio_pika

from discord.ext import commands

from acme_bot import MusicModule


class ExternalControlModule(commands.Cog):
    def __init__(self, bot, uri):
        self.bot = bot
        self.music_module = bot.get_cog(MusicModule.__name__)

        run_coroutine_threadsafe(self.__respond_to_messages(uri), self.bot.loop)

    async def __respond_to_messages(self, uri):
        logging.info("Connecting to AMQP broker at '%s.'", uri)
        connection = await aio_pika.connect_robust(uri)
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
