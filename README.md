# Equilibre Finance HTTP API 🚲💨🕸️

[![Latest tag](https://github.com/equilibre-finance/api/actions/workflows/tag-ci.yml/badge.svg)](https://github.com/equilibre-finance/api/actions/workflows/tag-ci.yml)

The Equilibre Finance HTTP API facilitates the fetching of tokens, liquidity pool pairs, and other associated data for our application.

Ensure you have [Docker](https://docs.docker.com/install/) installed before proceeding.

1. Copy the `env.example` file and rename it to `.env`, then update the relevant variables.
2. If this is your first time running the project, build the Docker image using the command:
    ```bash
    docker compose build
    ```
3. To start the services, run:
    ```bash
    docker compose up
    ```

This command initiates three services:
- `api`: The backend service
- `sync`: Constantly syncs information on pairs from the chain
- A Redis instance

## **Price Strategy Overview**

The Price Strategy is crafted to fetch the most precise and dependable token prices by harnessing both internal and external data sources. It evaluates these sources in a sequential manner based on a predefined order until a valid price is discovered.

### **How the Strategy Works:**

1. **Source Classification**:
   - Two primary data sources are utilized: internal contracts and external data from reliable APIs like Coingecko, DeFiLlama, and Debank.
   - Configure `GET_PRICE_INTERNAL_FIRST=True` in the `.env` file to prioritize internal prices for a more accurate pricing from your chain. The script searches contracts initially using token pairs and configurable internal routes. If no price is found, the external data source is utilized, searching for liquidity on relative pairs and liquidity staked addresses.
   - Note: Internal source fetching may have a longer sync time.

2. **Determine Source Order**:
   - Based on `GET_PRICE_INTERNAL_FIRST` configuration, the strategy prioritizes either internal or external sources.
   - The order of function calls when fetching data internally or externally can be determined using `INTERNAL_PRICE_ORDER` and `EXTERNAL_PRICE_ORDER`.

3. **Fetch Prices**:
   - Iterates over the sources in the determined order, attempting to fetch the price from each source until a valid price is obtained.

4. **Update and Finalize**:
   - Once a valid price is found, the strategy updates the token’s price and finalizes the update.

### **Configuration Options:**

Configuration options are set in the `.env` file. The following options are available:

- `GET_PRICE_INTERNAL_FIRST`: A boolean (`True` or `False`) to determine whether to check prices internally before looking at external sources.
- `DEFAULT_DECIMAL`: The default number of decimal places for tokens.
- `IGNORED_TOKEN_ADDRESSES`: List the addresses of tokens to be excluded during price fetching.
- `WEB3_PROVIDER_URI`: The URI of the Web3 provider which is used to interact with the Ethereum blockchain.
- `REDIS_URL`: The URL of your Redis server.
- `TOKEN_CACHE_EXPIRATION`: The expiration time (in seconds) for the token cache.
- `PAIR_CACHE_EXPIRATION`: The expiration time (in seconds) for the pair cache.
- `VARA_CACHE_EXPIRATION`: The expiration time (in seconds) for the VARA cache.
- `SUPPLY_CACHE_EXPIRATION`: The expiration time (in seconds) for the supply cache.
- `WEB3_PROVIDER_URI`: The URI of the Web3 provider which is used to interact with the Ethereum blockchain.
- `LOG_VERBOSE`: Set the logging level. Options include `DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL`.
- `LOG_SAVE`: Set to `1` to save the logs to `app.log` file, or `0` to disable logging to file.
- `DEFAULT_DECIMAL`: Set the default decimal places for tokens.
- `ROUTER_ADDRESS`, `FACTORY_ADDRESS`, `VOTER_ADDRESS`, `GAUGE_ADDRESS`, `VE_ADDRESS`, `REWARDS_DIST_ADDRESS`, `WRAPPED_BRIBE_FACTORY_ADDRESS`, `TREASURY_ADDRESS`, `DEFAULT_TOKEN_ADDRESS`, `NATIVE_TOKEN_ADDRESS`, `STABLE_TOKEN_ADDRESS`, `ROUTE_TOKEN_ADDRESSES`: These are various contract addresses used in the application. Each address serves a different purpose within the app, and they are essential for the app's functionality.
- `EXTERNAL_PRICE_ORDER`: A comma-separated list of functions that dictate the order in which external price data sources are queried.
- `INTERNAL_PRICE_ORDER`: A comma-separated list of functions that dictate the order in which internal price data sources are queried.
- `AXELAR_BLUECHIPS_ADDRESSES`: A comma-separated list of Axelar token addresses.
- `BLUECHIP_TOKEN_ADDRESSES`: A comma-separated list of Bluechip token addresses.

These configurations control how the application fetches price data, which is crucial for accurate financial calculations.

Ensure to review and set the configurations in the `.env` file as per your requirements before running the application.

---
