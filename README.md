# Equilibre Finance HTTP API 

[![Latest tag](https://github.com/equilibre-finance/api/actions/workflows/tag-ci.yml/badge.svg)](https://github.com/equilibre-finance/api/actions/workflows/tag-ci.yml)

The Equilibre Finance HTTP API facilitates the fetching of tokens, liquidity pool pairs, and other associated data for our application.

Ensure you have [Docker](https://docs.docker.com/install/) installed before proceeding.

1. Copy the `env.example` file and rename it to `.env`, then update the relevant variables.
2. If this is your first time running the project, build the Docker image using the command:
    ```bash
     sudo docker build -t api:0.1 && docker compose build
    ```
3. To start the services, run:
    ```bash
    docker compose up
    ```
This command initiates three services:
- `api`: The backend service
- `sync`: Constantly syncs information on pairs from the chain
- A Redis instance

## **Overview of Price Strategy**

The Price Strategy is engineered to meticulously fetch the most accurate and reliable token prices by leveraging both internal and external data sources. It methodically assesses these sources in a predetermined sequence until a valid price is unearthed.

### **Operational Mechanics of the Strategy:**

1. **Classification of Data Sources**:
   - Primarily, two data sources are harnessed: internal contracts and external data from reputable APIs like Coingecko, DeFiLlama, and Debank.
   - Setting `GET_PRICE_INTERNAL_FIRST=True` in the `.env` file prioritizes fetching prices internally for more precise pricing derived from your blockchain. Initially, the script explores contracts utilizing token pairs and adjustable internal routes. Should no price be identified, the external data source is engaged, probing for liquidity on corresponding pairs and liquidity staked addresses.
   - Note: Fetching from internal sources may extend the synchronization time.

2. **Determining the Order of Sources**:
   - The `GET_PRICE_INTERNAL_FIRST` configuration guides the strategy in prioritizing either internal or external sources.
   - The sequence of function calls for fetching data internally or externally can be tailored using `INTERNAL_PRICE_ORDER` and `EXTERNAL_PRICE_ORDER`.

3. **Direct Source Invocation**:
   - The 'price_control' key within tokenList enables a direct function call, bypassing the standard sequence. Example:

```json
{
  "chainId": 2222,
  "name": "SHRAP",
  "symbol": "xSHRAP",
  "price_control": "chain_price_in_pairs",
}
```

   In this case, the 'chain_price_in_pairs' function is invoked to compute the price for this token, sidestepping other checks and going directly to that function call.

   Further examples illustrate utilizing different functions based on the token's configuration, like `chain_price_in_bluechips` and `chain_price_in_liquid_staked`, to derive the price, each serving a unique purpose based on the token's attributes.

### **Dissecting the Price Flow:**

The `_update_price` method orchestrates the process of updating a blockchain token's price by evaluating various conditions and harnessing different pricing information sources. Here's an elaborated breakdown of the method's flow:

- **Ignored Token Verification**:
    - If the token resides in the `IGNORED_TOKEN_ADDRESSES` list, an error is logged, and the update concludes with a price of 0.

- **Price Control Verification**:
    - If `price_control` is set for the token, it attempts to fetch the price using a method specified by `price_control`. If the method exists, it updates the price; otherwise, an error is logged, and the price is set to 0.

- **External Source Verification for Special Addresses**:
    - If the token address is in a list of special addresses (`AXELAR_BLUECHIPS_ADDRESSES` or `BLUECHIP_TOKEN_ADDRESSES`), the method fetches the price from an external source.

- **Internal or External Price Retrieval**:
    - Depending on the `GET_PRICE_INTERNAL_FIRST` flag, the method either:
        - Tries to fetch the price from internal sources first, and if unsuccessful, fetches from external sources.
        - Or fetches from both internal and external sources, updating the price with whichever source returns a valid price first.

- **Chain Price Fallback**:
    - If the price is still 0, it attempts to fetch the price using the `chain_price_in_liquid_staked()` method.

- **Temporary Price for Special Addresses**:
    - If the price is still 0 and the token address is in `AXELAR_BLUECHIPS_ADDRESSES`, it sets a temporary price using the `temporary_price_in_bluechips()` method.


### **Detailed Function Explanations:**

**External Price Fetching**:

- `get_price_external_source` method:
    - Circulates through external price getter functions defined in `EXTERNAL_PRICE_ORDER`, invoking each to fetch the price, and returning the price from the first successful fetch.

**Internal Price Fetching**:

- `get_price_internal_source` method:
    - Circulates through internal price getter methods defined in `INTERNAL_PRICE_ORDER` through `ROUTE_CONFIGURATIONS`, invoking each to fetch the price, and returning the price from the first successful fetch.

**Price Update**:

- `_update_price` method:
    - Choreographs the price updating process by deciding the fetching order (internal first or external first) based on `GET_PRICE_INTERNAL_FIRST`. Invokes either `get_price_internal_source` or `get_price_external_source` methods or both to fetch and update the price.

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

### **Cache Strategy Overview**

Our application employs a caching mechanism to optimize performance by reducing frequent data fetches. This brief overview explains the caching strategy and its configurable parameters. This caching strategy ensures efficient data access and a seamless user experience.

---

#### **Synchronization Mechanism**

The application periodically syncs data points like tokens, pairs, and VARA prices. During synchronization:

1. **Tokens**: Checks cache validity (`assets:json`). If expired, fetches and updates the token list.
2. **Pairs**: Checks cache validity (`pairs:json`). If expired, fetches and updates the pairs data using potential multi-threading.
3. **VARA Price**: Checks cache validity (`vara:json`). If expired, fetches and updates the VARA price.
4. **Circulating Supply**: Verifies cache validity (supply:string). If the cache is outdated, it fetches and updates the circulating supply.
5. **Configuration**: Verifies cache validity (volume:json). If the cache is outdated, it fetches and updates the configuration, ensuring the dexscreener data isn't calculated in every call.

The `sync` function orchestrates the synchronization, while `sync_forever` ensures continuous synchronization at intervals set by `SYNC_WAIT_SECONDS`.


Ensure to review and set the configurations in the `.env` file as per your requirements before running the application.




---
