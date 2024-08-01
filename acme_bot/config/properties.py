"""Properties for deployment-specific config (e.g. credentials, URLs, log levels)"""

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

from yarl import URL

from acme_bot.config import ConfigProperty

# Credentials
DISCORD_TOKEN = ConfigProperty("DISCORD_TOKEN", str)
RABBITMQ_URI = ConfigProperty("RABBITMQ_URI", URL)

# Command subsystem
COMMAND_PREFIX = ConfigProperty("COMMAND_PREFIX", str)

# Logging subsystem
LOG_LEVEL = ConfigProperty("LOG_LEVEL", logging.getLevelName)

# Liveprobe module
LIVEPROBE_ENABLE = ConfigProperty("LIVEPROBE_ENABLE", bool)

# Music module
MUSIC_REMOTE_BASE_URL = ConfigProperty("MUSIC_REMOTE_BASE_URL", URL)
MUSIC_EXTRACTOR_MAX_WORKERS = ConfigProperty("MUSIC_EXTRACTOR_MAX_WORKERS", int)
