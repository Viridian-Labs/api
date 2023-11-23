import json

import requests
from app.cl.constants.tokenType import (Token_Type, token_type_dict,
                                        weth_address)
from app.settings import CACHE, DEFAULT_TOKEN_ADDRESS, LOGGER


cl_subgraph_url = (
    "https://graph.equilibrefinance.com/subgraphs/name/equilibre/"
    "cl/graphql"
)

urls = [cl_subgraph_url]


def get_prices():
    """
    Fetch prices from cache
    """
    prices = CACHE.get("cl_subgraph_prices")
    return prices if prices else {}


def process_tokens(tokens):
    """
    Process token data with prices and types.
    """
    prices = get_prices()
    for token in tokens:
        token["price"] = prices.get(token["symbol"], 0)
        token_type = token_type_dict.get(token["symbol"], Token_Type["OTHERS"])
        if token_type == Token_Type["OTHERS"]:
            if "USD" in token["symbol"]:
                token_type = Token_Type["LOOSE_STABLE"]
            elif token["id"] == weth_address:
                token_type = Token_Type["WETH"]
            elif token["id"] == DEFAULT_TOKEN_ADDRESS:
                token_type = Token_Type["VARA"]
        token["type"] = token_type
    return tokens


def try_subgraph(urls, query):
    """
    Attempt to query the subgraph and return the response.
    """
    for url in urls:
        try:
            response = requests.post(url, json={"query": query}, timeout=10)
            if response.status_code == 200:
                return response
        except requests.RequestException as e:
            LOGGER.error(f"Request to subgraph failed: {e}")
    return None


def get_cl_subgraph_tokens():
    """
    Fetch tokens from the subgraph.
    If an error occurs, fall back to loading cached tokens.
    """
    skip = 0
    limit = 100
    tokens = []

    while True:
        query = (
            f"{{ tokens(skip: {skip}, first: {limit}) "
            f"{{ id name symbol decimals }} }}"
        )

        response = try_subgraph(urls, query)

        if response and response.status_code == 200:
            new_tokens = response.json().get("data", {}).get("tokens", [])
            if not new_tokens:
                break
            tokens.extend(new_tokens)

            if len(new_tokens) < limit:
                break
            else:
                skip += limit
        else:
            LOGGER.warning("Error in subgraph tokens")
            return load_cached_tokens()

    tokens = process_tokens(tokens)
    CACHE.set(
        "cl_subgraph_tokens", json.dumps(tokens), timeout=86400
    )  # cache for 1 day
    return tokens


def load_cached_tokens():
    """Load tokens from cache if available, or raise an error."""
    cl_subgraph_tokens = CACHE.get("cl_subgraph_tokens")
    if cl_subgraph_tokens is not None:
        return json.loads(cl_subgraph_tokens)
    else:
        return []


def get_cl_subgraph_pools():
    """
    Fetches pool data from the subgraph.
    If an error occurs, attempts to return cached data.
    """
    try:
        pools = fetch_pools_from_subgraph()
        CACHE.set("cl_subgraph_pools", json.dumps(pools))
        return pools
    except Exception as e:
        LOGGER.warning(f"Error in get_cl_subgraph_pools: {e}")
        return load_cached_pools()


def fetch_pools_from_subgraph():
    """
    Continuously fetches pools from the subgraph
    until all are retrieved or an error occurs.
    """
    skip = 0
    limit = 100
    pools = []

    while True:
        query = build_pool_query(skip, limit)

        try:
            response = try_subgraph(urls, query)

            if response and response.status_code == 200:
                new_pools = response.json().get("data", {}).get("pools", [])
                if not new_pools:
                    break
                pools.extend(new_pools)

                if len(new_pools) < limit:
                    break
                else:
                    skip += limit
            else:
                LOGGER.error("Error in subgraph pools")
                break
        except requests.exceptions.Timeout:
            LOGGER.error("Timeout in cl_subgraph_pools")
            break
        except Exception as e:
            LOGGER.error(f"Error in cl_subgraph_pools: {e}")
            break

    if not pools:
        raise ValueError("No pools fetched from subgraph")

    return pools


def load_cached_pools():
    """
    Loads pools from cache if available, or raises an error.
    """
    cl_subgraph_pools = CACHE.get("cl_subgraph_pools") or []
    if cl_subgraph_pools:
        return json.loads(cl_subgraph_pools)
    else:
        return []


def build_pool_query(skip, limit):
    """
    Builds the GraphQL query for fetching pool data.
    """
    return f"""
        {{
            pools(skip: {skip}, limit: {limit}) {{
                id
                token0 {{
                    id
                    symbol
                    decimals
                    tokenDayData(first:7 orderBy:date orderDirection:desc){{
                        date
                        priceUSD
                    }}
                }}
                token1 {{
                    id
                    symbol
                    decimals
                    tokenDayData(first:7 orderBy:date orderDirection:desc){{
                        date
                        priceUSD
                    }}
                }}
                feeTier
                liquidity
                sqrtPrice
                tick
                tickSpacing
                totalValueLockedUSD
                totalValueLockedToken0
                totalValueLockedToken1
                gauge {{
                    id
                    rewardTokens
                    isAlive
                    bVaraRatio
                }}
                feeDistributor {{
                    id
                    rewardTokens
                }}
                poolDayData(first:7 orderBy:date orderDirection:desc){{
                    date
                    feesUSD
                    tvlUSD
                    liquidity
                    high
                    low
                    volumeToken0
                    volumeToken1
                }}
            }}
        }}
    """
