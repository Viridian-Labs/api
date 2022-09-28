# Velodrome Finance HTTP API 🚲💨🕸️

Velodrome Finance HTTP API is used by our app to fetch tokens and liquidity
pool pairs.

Please make sure you have [Docker](https://docs.docker.com/install/) first.

To build the image, run:
```
$ docker build ./ -t velodrome/api
```

Next, make a copy of the `env.example` file, and update the relevant variables.

Finally, to start the container, run:
```
$ docker run --rm --env-file=env.example.copy -v $(pwd):/app -p 3001:3001 -w /app -it velodrome/api
```

To run the syncer (refreshes data from chain) process, run:
```
$ docker run --rm --env-file=env.example.copy -v $(pwd):/app -p 3001:3001 -w /app -it velodrome/api sh -c 'python -m app.pairs.syncer'
```

## Running locally
This project is set up with [`poetry`](https://python-poetry.org/docs/) and Python 3.9.14. We recommend installing
[`pyenv`](https://github.com/pyenv/pyenv) to easily manage different Python versions.

Installing dependencies:

    poetry install

This will spawn and use a virtual environment in `.venv` and install the dependencies defined in `poetry.lock`
(or `pyproject.toml`) if the lock file was missing (which should not happen).

When adding new dependencies, one should run:

    poetry add package@version