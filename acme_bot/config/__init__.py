"""Configuration management using environment variables and config files."""
import logging
from collections.abc import Callable
from dataclasses import dataclass
from os import environ
from os.path import dirname, join
from typing import Any

from dotenv import load_dotenv
from yarl import URL


def load_config(config_path=None):
    """Load configuration from the default and user-specified config files."""
    if config_path is not None:
        load_dotenv(config_path)
    load_dotenv(join(dirname(__file__), "default.conf"))


@dataclass
class ConfigProperty:
    """Config property loaded from environment variables and config files."""

    env_name: str
    constructor: Callable[[str], Any]

    def __call__(self):
        try:
            return self.constructor(environ[self.env_name])
        except KeyError:
            logging.critical(
                "Required config property is missing: %s. "
                "Please provide it using a config file or environment variable.",
                self.env_name,
            )
            raise

    def get(self, *, default=None):
        """Return the property value, or `default` if the property is not specified."""
        if env_value := environ.get(self.env_name):
            return self.constructor(env_value)

        return default


# Credentials
DISCORD_TOKEN = ConfigProperty("DISCORD_TOKEN", str)
RABBITMQ_URI = ConfigProperty("RABBITMQ_URI", URL)

# Command subsystem
COMMAND_PREFIX = ConfigProperty("COMMAND_PREFIX", str)

# Logging subsystem
LOG_LEVEL = ConfigProperty("LOG_LEVEL", logging.getLevelName)
