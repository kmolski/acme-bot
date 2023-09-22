# acme-bot

Discord bot with music playback and Unix shell-inspired commands.

[Have a chat!](https://discordapp.com/users/596614462019207178)

User documentation
------------------

For a short description of the extended syntax, read the [syntax overview](docs/shell_syntax.md).

A full list of commands is available [here](docs/commands.md) or through the `!help` command.

Setup instructions with Docker
-----------

### Build & run Docker container

1. (Optional) Adjust configuration in `acme_bot/config/default.conf`
2. Run the following in the project directory:

    ```console
    $ docker build . -t acme-bot:latest
    $ docker run -d \
          -e DISCORD_TOKEN=<Discord API token> \
          -e RABBITMQ_URI=<RabbitMQ URI (optional)> \
          acme-bot:latest
    ```

Setup instructions
-----------

### Prerequisites

To use this method, the [Poetry](https://python-poetry.org) build tool is required.

### Configure & run

1. (Optional) Copy the config file from `acme_bot/config/default.conf` and edit it
2. Run the following in the project directory:

    ```console
    $ poetry install
    $ poetry run acme-bot [-c CONFIG_FILE]
    ```

Dependencies
------------

License
-------

[GNU Affero General Public License v3](https://opensource.org/license/agpl-v3)
