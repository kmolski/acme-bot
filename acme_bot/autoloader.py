"""Automatic cog loading and dependency injection using decorators."""

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


log = logging.getLogger(__name__)


class CogFactory:
    """Factory method implementation for discord.py cogs."""

    @classmethod
    def is_available(cls):
        """Check if the cog can be loaded."""
        return True

    @classmethod
    async def create_cog(cls, bot):
        """Create a cog instance. Dependencies on other cogs should be injected here."""
        raise NotImplementedError()

    @classmethod
    async def load(cls, bot):
        """Create a cog instance and add it to the bot."""
        if cls.is_available():
            cog_instance = await cls.create_cog(bot)
            await bot.add_cog(cog_instance)


__AUTOLOAD_MODULES = []


def autoloaded(cls):
    """Register the cog as an automatically loadable module."""
    __AUTOLOAD_MODULES.append(cls)
    log.debug("Class registered with @autoloaded: '%s'", cls.__name__)
    return cls


def get_autoloaded_cogs():
    """Get all cogs registered as automatically loadable modules."""
    return __AUTOLOAD_MODULES
