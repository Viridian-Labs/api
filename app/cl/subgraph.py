import json
import requests

from app.settings import (CACHE, LOGGER, DEFAULT_TOKEN_ADDRESS)
from cl.constants.tokenType import token_type_dict, Token_Type, weth_address 

cl_subgraph_url = "https://graph.equilibrefinance.com/subgraphs/name/equilibre/subgraph1/graphql"
urls = [cl_subgraph_url]


def get_prices():
    prices = CACHE.get('cl_subgraph_prices')
    return prices if prices else {}

def get_cl_subgraph_tokens(debug):
    # get tokens from subgraph
    skip = 0
    limit = 100
    tokens = []
    while True:
        query = f"{{ tokens(skip: {skip}, limit: {limit}) {{ id name symbol decimals }} }}"

        try:
            response = try_subgraph(urls, query)

            if response.status_code == 200:
                new_tokens = response.json()['data']['tokens']
                tokens += new_tokens

                if len(new_tokens) < limit:
                    break
                else:
                    skip += limit
            else:
                if debug:
                    print(response.text)
                LOGGER.error("Error in subgraph tokens")
                return json.loads(CACHE.get('cl_subgraph_tokens'))
        except requests.exceptions.Timeout:
            if debug:
                print("Timeout")
            LOGGER.error("Timeout in cl_subgraph_tokens")
            return json.loads(CACHE.get('cl_subgraph_tokens'))
        except Exception as e:
            LOGGER.error("Error in cl_subgraph_tokens")
            return json.loads(CACHE.get('cl_subgraph_tokens'))

    # get tokens prices
    prices = get_prices(tokens, debug=debug)
    for token in tokens:
        token['price'] = prices[token['symbol']]

        # determine token type
        token_type = token_type_dict.get(token['symbol'], Token_Type['OTHERS'])
        if token_type == Token_Type['OTHERS']:
            if 'USD' in token['symbol']:
                token_type = Token_Type['LOOSE_STABLE']
            elif token['id'] == weth_address:
                token_type = Token_Type['WETH']
            elif token['id'] == DEFAULT_TOKEN_ADDRESS:
                token_type = Token_Type['VARA']
        token['type'] = token_type

    # cache tokens
    CACHE.set('cl_subgraph_tokens', json.dumps(tokens))

    return tokens


def get_cl_subgraph_pools(debug):
    # get pairs from subgraph
    skip = 0
    limit = 100
    pools = []
    while True:
        query = f"""
                {{pools(skip: {skip}, limit: {limit}) {{
                        id
                        token0
                            {{
                                id
                                symbol
                                decimals
                                tokenDayData(first:7 orderBy:date orderDirection:desc){{
                                    date
                                    priceUSD
                                }}
                            }}
                        token1
                            {{
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

        try:
            response = try_subgraph(urls, query)

            if response.status_code == 200:
                new_pools = response.json()['data']['pools']
                pools += new_pools

                if len(new_pools) < limit:
                    break
                else:
                    skip += limit
            else:
                if debug:
                    print(response.text)
                LOGGER.error("Error in subgraph pairs")
                return json.loads(CACHE.get('cl_subgraph_pools'))
        except requests.exceptions.Timeout:
            if debug:
                print("Timeout")
            LOGGER.error("Timeout in cl_subgraph_pools")
            return json.loads(CACHE.get('cl_subgraph_pools'))
        except Exception as e:
            LOGGER.error("Error in cl_subgraph_pools")
            return json.loads(CACHE.get('cl_subgraph_pools'))

    # cache pairs
    CACHE.set('cl_subgraph_pools', json.dumps(pools))

    return pools


def try_subgraph(urls, query, timeout=15):

    response = {}

    for i in range(len(urls)):
        try:
            response = requests.post(
                urls[i],
                json={
                    "query": query
                }, timeout=timeout)
        except Exception as e:
            LOGGER.error(f"Error in {urls[i]}")
            LOGGER.error(e)
            continue

        if (response.status_code == 200):
            return response

    return response
