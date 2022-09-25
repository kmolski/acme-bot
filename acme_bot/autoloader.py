"""Automatic cog loading & dependency injection using decorators."""


class CogFactory:
    """Factory method implementation for discord.py cogs."""

    @classmethod
    def is_available(cls):
        """Check if the cog can be loaded."""
        return True

    @classmethod
    def create_cog(cls, bot):
        """Create a cog instance. Dependencies on other cogs should be injected here."""
        raise NotImplementedError()

    @classmethod
    async def load(cls, bot):
        """Create a cog instance and add it to the bot."""
        cog_instance = cls.create_cog(bot)
        await bot.add_cog(cog_instance)


__AUTOLOAD_MODULES = []


def autoloaded(cls):
    """Register the cog as an automatically loadable module."""
    __AUTOLOAD_MODULES.append(cls)
    return cls


def get_autoloaded_cogs():
    """Get all cogs registered as automatically loadable modules."""
    return __AUTOLOAD_MODULES
