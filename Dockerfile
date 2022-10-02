FROM pypy:3.9-slim-bullseye AS base

ENV POETRY_HOME=/etc/poetry
ENV POETRY_VIRTUALENVS_CREATE=false

RUN apt-get update
RUN apt-get install -y --no-install-recommends gcc g++ libssl-dev libev-dev curl
RUN apt-get clean

RUN curl -sSL https://install.python-poetry.org | python -

ENV PATH="$PATH:$POETRY_HOME/bin"

FROM base AS prod

WORKDIR /app
COPY ./ /app

RUN poetry install

EXPOSE 3000

ENTRYPOINT ["api-start"]

FROM prod AS sync

ENTRYPOINT ["api-sync"]
