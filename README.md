# acme-bot

[![Python build status](https://github.com/kmolski/acme-bot/actions/workflows/wheel_build.yml/badge.svg)](https://github.com/kmolski/acme-bot/actions/workflows/wheel_build.yml)
[![Docker build status](https://github.com/kmolski/acme-bot/actions/workflows/docker_build.yml/badge.svg)](https://github.com/kmolski/acme-bot/actions/workflows/docker_build.yml)
[![License](docs/license.svg)](https://opensource.org/license/agpl-v3)

Discord bot with music playback and Unix shell-inspired commands.
This bot is _self-hosted_, which means you'll need to create
the Discord bot user and host an instance yourself.

Usage
-----

Use commands by writing their name followed by any number of arguments:
```
!play-url https://www.youtube.com/watch?v=dQw4w9WgXcQ

!play darude sandstorm
```

For a short description of the extended shell syntax, read the [syntax overview](docs/shell_syntax.md).

A full list of commands is available [here](docs/commands.md) or through the `!help` command.

Getting started
---------------

1. Create a new application in the [Discord Developer Portal](https://discord.com/developers/applications)
2. Enable "Message Content Intent" in the "Bot" section
3. Click "Reset Token" and "Copy" to copy your API token
4. Enable the following permissions in the "Installation" section:
   - "Attach Files"
   - "Connect"
   - "Embed Links"
   - "Manage Messages"
   - "Read Message History"
   - "Send Messages"
   - "Speak"

5. Use the install link to add the bot to your server
6. [Setup your Lavalink instance](https://lavalink.dev/getting-started/index.html#running-lavalink)

### Configuring and running acme-bot

| Environment variable    | Default value | Description                                                        |
|-------------------------|---------------|--------------------------------------------------------------------|
| `DISCORD_TOKEN`         | _(none)_      | Discord API token.                                                 |
| `LAVALINK_URI`          | _(none)_      | Lavalink connection URI. _(optional)_                              |
| `RABBITMQ_URI`          | _(none)_      | RabbitMQ connection URI. _(optional)_                              |
| `COMMAND_PREFIX`        | `!`           | Command prefix for the bot instance.                               |
| `LOG_LEVEL`             | `INFO`        | Level of log messages to display.                                  |
| `LIVEPROBE_ENABLE`      | `0`           | Enables a TCP liveness probe on port 3000. (value: 0/1)            |
| `MUSIC_REMOTE_BASE_URL` | _(none)_      | Base URL of the acme-bot-remote frontend application. _(optional)_ |

#### Docker

```console
$ docker run -d \
      -e DISCORD_TOKEN=<Discord API token> \
      -e LAVALINK_URI=<Lavalink instance URI> \
      -e RABBITMQ_URI=<RabbitMQ URI, optional> \
      ghcr.io/kmolski/acme-bot:latest
```

#### Standalone executable

To use this method, [Poetry](https://python-poetry.org) has to be installed on your system.

```console
$ git clone https://github.com/kmolski/acme-bot.git && cd acme-bot
# copy acme_bot/config/default.conf to local.conf, set your own values
$ poetry install
$ poetry run acme-bot -c <configuration file>
```
