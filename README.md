# acme-bot

Discord bot with Unix shell-inspired commands and music playback features.

Commands
--------

A full list of commands is available [here](docs/commands.md) or through the `help` command.

Setup instructions with Docker
-----------

### Build & run Docker container (requires a RabbitMQ instance)

1. Adjust configuration in `acme_bot/config/default.conf`
2. Run the following in the project directory:

    ```console
    $ docker build . -t acme-bot:latest
    $ docker run -d --name <CONTAINER NAME> \
          -e DISCORD_TOKEN=<DISCORD API TOKEN> \
          -e RABBITMQ_URI=<RABBITMQ INSTANCE URI> \
          acme-bot:latest -c <CONFIG FILE>
    ```

Setup instructions
-----------

### Prerequisites

To use this method, the [Poetry](https://python-poetry.org) build tool is required.

### Configure & run

1. Copy the config file from `acme_bot/config/default.conf` and edit it
2. Run the following in the project directory:

    ```console
    $ poetry install
    $ poetry run acme-bot -c <CONFIG FILE>
    ```

Dependencies
------------

License
-------

[GNU Affero General Public License v3](https://opensource.org/licenses/AGPL-3.0)
