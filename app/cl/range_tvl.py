from cl.constants.tokenType import Token_Type, weth_address
from cl.sqrt_price_math import get_amount0_delta, get_amount1_delta, token_amounts_from_current_price


def range_tvl(tokens, pool, liquidity):
    token0 = tokens[pool['token0']['id']]
    token1 = tokens[pool['token1']['id']]

    # get range delta
    pool_type = token0['type'] * token1['type']
    range_delta = 0
    # case: LSD and WETH
    if pool_type == -1:
        range_delta = 50  # +-0.5%

    # case: STABLE-STABLE
    elif pool_type == 9:
        range_delta = 25  # +-0.25%
    
    # case: LST-LST
    elif pool_type == 1:
        range_delta = 50 # +-0.5%

    # case: STABLE-LOOSE_STABLE
    elif pool_type >= 4:
        range_delta = 75  # +-0.75%

    # case: all other cases
    else:
        range_delta = 750  # +-7.5% (15%)

    [position_token0_amount, position_token1_amount] = token_amounts_from_current_price(pool['sqrtPrice'], range_delta, liquidity)
    position_usd = (position_token0_amount * token0['price'] / 10**token0['decimals']) + (position_token1_amount * token1['price'] / 10**token1['decimals'])

    return position_usd
