# Equilibre Finance HTTP API 🚲💨🕸️

[![Latest tag](https://github.com/equilibre-finance/api/actions/workflows/tag-ci.yml/badge.svg)](https://github.com/equilibre-finance/api/actions/workflows/tag-ci.yml)

Equilibre Finance HTTP API is used by our app to fetch tokens and liquidity
pool pairs.

Please make sure you have [Docker](https://docs.docker.com/install/) first.

Next, make a copy of the `env.example` file, and update the relevant variables.

Finally, to start the services run:

    docker compose up

This will start three services:
- `api`: the backend
- `sync`: the service that is constantly syncing information on pairs from the chain
- A redis instance

## Running locally
This project is set up with [`poetry`](https://python-poetry.org/docs/) and Python 3.9.14. We recommend installing
[`pyenv`](https://github.com/pyenv/pyenv) to easily manage different Python versions.

**Note**: Make sure you update your `.env` file to point to localhost (i.e: redis url)

Installing dependencies:

    poetry install

Running the API (after the previous command)

    api-start

Running the syncing process (needed for scraping data from the chain)

    api-sync

This will spawn and use a virtual environment in `.venv` and install the dependencies defined in `poetry.lock`
(or `pyproject.toml`) if the lock file was missing (which should not happen).

When adding new dependencies, one should run:

    poetry add package@version

Certainly! Below is a concise explanation in Markdown format:

---

### **Price Strategy Overview**

The price strategy is designed to fetch the most accurate and reliable token prices by utilizing a combination of internal and external sources. It works by sequentially evaluating these sources based on a predefined order until a valid price is found.

#### **How the Strategy Works:**

This strategy ensures the reliability and accuracy of token prices by systematically evaluating multiple sources and allowing for flexible configuration of source order and token inclusion.

1. **Determine Source Order:**
   - The strategy first determines whether to prioritize internal or external sources based on the `GET_PRICE_INTERNAL_FIRST` configuration.
   - If `True`, it will first attempt to fetch prices from internal sources before moving to external ones, and vice versa.

2. **Fetch Prices:**
   - The strategy iterates over the sources in the determined order.
   - It attempts to fetch the price from each source until a valid price is obtained.
   - If a source fails to provide a valid price, the strategy moves to the next one in the sequence.

3. **Update and Finalize:**
   - Once a valid price is found, the strategy updates the token’s price and finalizes the update.
   - If no valid price is found after evaluating all sources, the token’s price remains unchanged.

#### **Configuration Options:**
- **`GET_PRICE_INTERNAL_FIRST`:**
   - Determines the initial source type to be considered.
   - Configurable to either `True` or `False`.

- **`INTERNAL_PRICE_ORDER` and `EXTERNAL_PRICE_ORDER`:**
   - Define the sequence in which the respective internal and external sources are evaluated.
   - Can be customized to prioritize specific sources based on reliability and speed.

- **`IGNORED_TOKEN_ADDRESSES`:**
   - Lists the addresses of tokens to be excluded during price fetching.
   - Useful for omitting unreliable or irrelevant tokens.

