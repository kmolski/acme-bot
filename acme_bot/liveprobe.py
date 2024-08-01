"""Liveness probe cog for use with Kubernetes pods."""

#  Copyright (C) 2024  Krzysztof Molski
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
from asyncio import start_server

from discord.ext import commands

from acme_bot.autoloader import CogFactory, autoloaded
from acme_bot.config.properties import LIVEPROBE_ENABLE

log = logging.getLogger(__name__)


@autoloaded
class LivenessProbeModule(commands.Cog, CogFactory):
    """Liveness probe cog for use with Kubernetes pods."""

    def __init__(self, socket):
        self.__socket = socket

    @classmethod
    def is_available(cls):
        return LIVEPROBE_ENABLE.get() or False

    @classmethod
    async def create_cog(cls, bot):
        socket = await start_server(cls._handle_conn, "::1", 3000, start_serving=False)
        return cls(socket)

    @classmethod
    async def _handle_conn(cls, _, writer):
        writer.close()
        await writer.wait_closed()

    @commands.Cog.listener("on_ready")
    async def _open_socket(self):
        await self.__socket.start_serving()

    async def cog_unload(self):
        self.__socket.close()
