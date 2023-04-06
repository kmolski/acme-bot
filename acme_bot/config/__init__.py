"""Configuration management based on .env files and environment overrides."""
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
from collections.abc import Callable
from dataclasses import dataclass
from os import environ
from os.path import dirname, join
from typing import Any

from dotenv import load_dotenv


log = logging.getLogger(__name__)


def load_config(config_path=None):
    """Load configuration from the default and user-specified config files."""
    if config_path is not None:
        log.debug("Loading config file: '%s'", config_path)
        load_dotenv(config_path)

    log.debug("Loading config file: 'default.conf'")
    load_dotenv(join(dirname(__file__), "default.conf"))


@dataclass
class ConfigProperty:
    """Config property sourced from config files or an environment variable."""

    env_name: str
    constructor: Callable[[str], Any]

    def __call__(self):
        try:
            return self.constructor(environ[self.env_name])
        except KeyError:
            log.critical("Required config property is missing: %s", self.env_name)
            raise

    def get(self, *, default=None):
        """Return the property value, or `default` if the property is not specified."""
        if env_value := environ.get(self.env_name):
            return self.constructor(env_value)

        log.debug("No value found for %s, using default: %s", self.env_name, default)
        return default
