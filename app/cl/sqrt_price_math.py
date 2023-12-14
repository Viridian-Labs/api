from math import ceil, sqrt
from typing import Tuple


def get_next_sqrt_price_from_amount0_rounding_up(
    sqrt_px96: int, liquidity: int, amount: int, add: bool
) -> int:
    if amount == 0:
        return sqrt_px96

    numerator1 = liquidity * (1 << 96)

    if add:
        product = amount * sqrt_px96
        if product // amount == sqrt_px96:
            denominator = numerator1 + product
            if denominator >= numerator1:
                return ceil(numerator1 * sqrt_px96 // denominator)

        return ceil(numerator1 / ((numerator1 // sqrt_px96) + amount))
    else:
        product = amount * sqrt_px96
        assert product // amount == sqrt_px96 and numerator1 > product
        denominator = numerator1 - product
        return ceil((numerator1 * sqrt_px96) / denominator)


def get_next_sqrt_price_from_amount1_rounding_down(
    sqrt_px96: int, liquidity: int, amount: int, add: bool
) -> int:
    if add:
        quotient = (amount * (1 << 96)) // liquidity
        return sqrt_px96 + quotient
    else:
        quotient = ceil((amount * (1 << 96)) // liquidity)
        assert sqrt_px96 > quotient
        return sqrt_px96 - quotient


def get_next_sqrt_price_from_input(
    sqrt_px96: int, liquidity: int, amount_in: int, zero_for_one: bool
) -> int:
    assert sqrt_px96 > 0 and liquidity > 0

    if zero_for_one:
        return get_next_sqrt_price_from_amount0_rounding_up(
            sqrt_px96, liquidity, amount_in, True
        )
    else:
        return get_next_sqrt_price_from_amount1_rounding_down(
            sqrt_px96, liquidity, amount_in, True
        )


def get_next_sqrt_price_from_output(
    sqrt_px96: int, liquidity: int, amount_out: int, zero_for_one: bool
) -> int:
    assert sqrt_px96 > 0 and liquidity > 0

    if zero_for_one:
        return get_next_sqrt_price_from_amount1_rounding_down(
            sqrt_px96, liquidity, amount_out, False
        )
    else:
        return get_next_sqrt_price_from_amount0_rounding_up(
            sqrt_px96, liquidity, amount_out, False
        )


def get_amount0_delta(
    sqrt_ratio_a_x96: int,
    sqrt_ratio_b_x96: int,
    liquidity: int,
    round_up: bool,
) -> int:
    if sqrt_ratio_a_x96 > sqrt_ratio_b_x96:
        sqrt_ratio_a_x96, sqrt_ratio_b_x96 = sqrt_ratio_b_x96, sqrt_ratio_a_x96

    numerator1 = liquidity * (1 << 96)
    numerator2 = sqrt_ratio_b_x96 - sqrt_ratio_a_x96

    if sqrt_ratio_a_x96 == 0:
        return 0

    assert sqrt_ratio_a_x96 > 0

    if round_up:
        return ceil(
            ceil(numerator1 * numerator2 / sqrt_ratio_b_x96) / sqrt_ratio_a_x96
        )
    else:
        return (
            numerator1 * numerator2 // sqrt_ratio_b_x96
        ) // sqrt_ratio_a_x96


def get_amount1_delta(
    sqrt_ratio_a_x96: int,
    sqrt_ratio_b_x96: int,
    liquidity: int,
    round_up: bool,
) -> int:
    if sqrt_ratio_a_x96 > sqrt_ratio_b_x96:
        sqrt_ratio_a_x96, sqrt_ratio_b_x96 = sqrt_ratio_b_x96, sqrt_ratio_a_x96

    if round_up:
        return ceil(
            (liquidity * (sqrt_ratio_b_x96 - sqrt_ratio_a_x96)) / (1 << 96)
        )
    else:
        return (liquidity * (sqrt_ratio_b_x96 - sqrt_ratio_a_x96)) // (1 << 96)


def get_signed_amount0_delta(
    sqrt_ratio_a_x96: int, sqrt_ratio_b_x96: int, liquidity: int
) -> int:
    if liquidity < 0:
        return -get_amount0_delta(
            sqrt_ratio_a_x96, sqrt_ratio_b_x96, -liquidity, False
        )
    else:
        return get_amount0_delta(
            sqrt_ratio_a_x96, sqrt_ratio_b_x96, liquidity, True
        )


def get_signed_amount1_delta(
    sqrt_ratio_a_x96: int, sqrt_ratio_b_x96: int, liquidity: int
) -> int:
    if liquidity < 0:
        return -get_amount1_delta(
            sqrt_ratio_a_x96, sqrt_ratio_b_x96, -liquidity, False
        )
    else:
        return get_amount1_delta(
            sqrt_ratio_a_x96, sqrt_ratio_b_x96, liquidity, True
        )


def token_amounts_from_current_price(
    sqrt_price: int, deviation: int, liquidity: int
) -> Tuple[int, int]:
    """
    Returns the token0 and token1 amounts around the price and deviation
    """

    sqrt_price = int(sqrt_price)
    price = (sqrt_price ** 2) / 2 ** (96 * 2)
    high_sqrt_x96 = int(sqrt(price * (10000 + deviation) / 10000) * 2 ** 96)
    low_sqrt_x96 = int(sqrt(price * (10000 - deviation) / 10000) * 2 ** 96)
    position_token0_amount = get_amount0_delta(
        high_sqrt_x96, sqrt_price, liquidity, False
    )
    position_token1_amount = get_amount1_delta(
        sqrt_price, low_sqrt_x96, liquidity, False
    )

    return (position_token0_amount, position_token1_amount)
