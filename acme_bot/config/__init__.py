"""Configuration management"""
import logging
from dataclasses import dataclass
from os import environ
from os.path import dirname, join
from typing import Any
from collections.abc import Callable

from dotenv import load_dotenv


@dataclass
class ConfigProperty:
    """Configuration property loaded from environment variables or config files"""

    key: str
    constructor: Callable[[str], Any]

    def __call__(self):
        try:
            return self.constructor(environ[self.key])
        except KeyError:
            logging.critical(
                "Required config property is missing: %s. "
                "Please provide it using a config file or environment variable.",
                self.key,
            )
            raise


COMMAND_PREFIX = ConfigProperty("COMMAND_PREFIX", str)
DISCORD_TOKEN = ConfigProperty("DISCORD_TOKEN", str)
LOG_LEVEL = ConfigProperty("LOG_LEVEL", logging.getLevelName)
RABBITMQ_URI = ConfigProperty("RABBITMQ_URI", str)


def load_config(config_path=None):
    """Load configuration from the default and user-specified config files."""
    if config_path is not None:
        load_dotenv(config_path)
    load_dotenv(join(dirname(__file__), "default.conf"))
