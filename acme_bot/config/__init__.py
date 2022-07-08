"""Configuration management"""
import logging
from dataclasses import dataclass
from os import environ
from os.path import dirname, join
from typing import Callable, Any

from dotenv import load_dotenv


@dataclass
class ConfigProperty:
    """Configuration property loaded from environment variables or config files"""
    ALL = {}

    key: str
    description: str
    required: bool
    constructor: Callable[[str], Any]

    @classmethod
    def assert_required(cls):
        """Assert that all required config properties are set."""
        missing = [p for p in cls.ALL.values() if p.required and p.key not in environ]
        if missing:
            raise ValueError(
                "Required config properties are missing: "
                f"[{', '.join(p.key for p in missing)}]"
                "Please provide them using a config file or environment variables."
            )

    def __post_init__(self):
        ConfigProperty.ALL[self.key] = self

    def __call__(self):
        return self.constructor(environ[self.key])


DISCORD_TOKEN = ConfigProperty("DISCORD_TOKEN", "Discord API token", True, str)
COMMAND_PREFIX = ConfigProperty("COMMAND_PREFIX", "Command prefix", True, str)
LOG_LEVEL = ConfigProperty("LOG_LEVEL", "Log message level", True, logging.getLevelName)


def load_config(config_path=None):
    """Load configuration from the default and user-specified config files."""
    load_dotenv(join(dirname(__file__), "default.conf"))
    if config_path is not None:
        load_dotenv(config_path)

    ConfigProperty.assert_required()
