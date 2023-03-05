from os import environ

import pytest

from acme_bot.config import load_config
from acme_bot.config.properties import *


EXAMPLE_PROP_NAME = "EXAMPLE_PROP_NAME"
EXAMPLE_PROP = ConfigProperty(EXAMPLE_PROP_NAME, str)


def test_load_config_default_file():
    load_config()

    COMMAND_PREFIX()
    LOG_LEVEL()


def test_load_config_user_file():
    load_config("test/data/test.conf")

    DISCORD_TOKEN()
    RABBITMQ_URI()


def test_config_property_call_present():
    value = "example prop value"
    environ[EXAMPLE_PROP.env_name] = value

    assert EXAMPLE_PROP() == value


def test_config_property_call_missing():
    del environ[EXAMPLE_PROP.env_name]

    with pytest.raises(KeyError):
        EXAMPLE_PROP()


def test_config_property_get_present():
    value = "example prop value"
    environ[EXAMPLE_PROP.env_name] = value

    assert EXAMPLE_PROP.get() == value


def test_config_property_get_default():
    value = "example prop default"
    del environ[EXAMPLE_PROP.env_name]

    assert EXAMPLE_PROP.get(default=value) == value
