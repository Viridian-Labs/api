TICK_SPACINGS = {"100": 1, "500": 10, "3000": 60, "10000": 200}

MAX_UINT256 = int(2 ** 256 - 1)
Q32 = 2 ** 32

TWO = 2
POWERS_OF_2 = [
    (128, TWO ** 128),
    (64, TWO ** 64),
    (32, TWO ** 32),
    (16, TWO ** 16),
    (8, TWO ** 8),
    (4, TWO ** 4),
    (2, TWO ** 2),
    (1, TWO ** 1),
]

MIN_TICK = int(-887272)
MAX_TICK = -MIN_TICK

MIN_SQRT_RATIO = int("4295128739")
MAX_SQRT_RATIO = int("1461446703485210103287273052203988822378723970342")


def most_significant_bit(x):
    assert x > 0, "ZERO"
    assert x <= MAX_UINT256, "MAX"

    msb = 0
    for power, min_val in POWERS_OF_2:
        if x >= min_val:
            x = x >> power
            msb += power
    return msb


def get_tick_at_sqrt_ratio(sqrt_ratio_x96):
    assert (
        sqrt_ratio_x96 >= MIN_SQRT_RATIO and sqrt_ratio_x96 < MAX_SQRT_RATIO
    ), "SQRT_RATIO"

    sqrt_ratio_x128 = sqrt_ratio_x96 << 32

    msb = most_significant_bit(sqrt_ratio_x128)

    if msb >= 128:
        r = sqrt_ratio_x128 >> (msb - 127)
    else:
        r = sqrt_ratio_x128 << (127 - msb)

    log_2 = (msb - 128) << 64

    for i in range(14):
        r = (r * r) >> 127
        f = r >> 128
        log_2 = log_2 | (f << (63 - i))
        r = r >> f

    log_sqrt10001 = log_2 * 255738958999603826347141

    tick_low = (log_sqrt10001 - 3402992956809132418596140100660247210) >> 128
    tick_high = (
        log_sqrt10001 + 291339464771989622907027621153398088495
    ) >> 128

    if tick_low == tick_high:
        return tick_low
    elif get_sqrt_ratio_at_tick(tick_high) <= sqrt_ratio_x96:
        return tick_high
    else:
        return tick_low


def mul_shift(val, mul_by):
    val = int(val)
    mul_by = int(mul_by, 16)
    result = (val * mul_by) >> 128
    return result


def get_sqrt_ratio_at_tick(tick):
    tick = int(tick)
    assert (
        tick >= MIN_TICK and tick <= MAX_TICK and isinstance(tick, int)
    ), "TICK"
    abs_tick = abs(tick)

    ratio = (
        0xFFFCB933BD6FAD37AA2D162D1A594001
        if abs_tick & 0x1 != 0
        else 0x100000000000000000000000000000000
    )

    if abs_tick & 0x2 != 0:
        ratio = mul_shift(ratio, "0xfff97272373d413259a46990580e213a")
    if abs_tick & 0x4 != 0:
        ratio = mul_shift(ratio, "0xfff2e50f5f656932ef12357cf3c7fdcc")
    if abs_tick & 0x8 != 0:
        ratio = mul_shift(ratio, "0xffe5caca7e10e4e61c3624eaa0941cd0")
    if abs_tick & 0x10 != 0:
        ratio = mul_shift(ratio, "0xffcb9843d60f6159c9db58835c926644")
    if abs_tick & 0x20 != 0:
        ratio = mul_shift(ratio, "0xff973b41fa98c081472e6896dfb254c0")
    if abs_tick & 0x40 != 0:
        ratio = mul_shift(ratio, "0xff2ea16466c96a3843ec78b326b52861")
    if abs_tick & 0x80 != 0:
        ratio = mul_shift(ratio, "0xfe5dee046a99a2a811c461f1969c3053")
    if abs_tick & 0x100 != 0:
        ratio = mul_shift(ratio, "0xfcbe86c7900a88aedcffc83b479aa3a4")
    if abs_tick & 0x200 != 0:
        ratio = mul_shift(ratio, "0xf987a7253ac413176f2b074cf7815e54")
    if abs_tick & 0x400 != 0:
        ratio = mul_shift(ratio, "0xf3392b0822b70005940c7a398e4b70f3")
    if abs_tick & 0x800 != 0:
        ratio = mul_shift(ratio, "0xe7159475a2c29b7443b29c7fa6e889d9")
    if abs_tick & 0x1000 != 0:
        ratio = mul_shift(ratio, "0xd097f3bdfd2022b8845ad8f792aa5825")
    if abs_tick & 0x2000 != 0:
        ratio = mul_shift(ratio, "0xa9f746462d870fdf8a65dc1f90e061e5")
    if abs_tick & 0x4000 != 0:
        ratio = mul_shift(ratio, "0x70d869a156d2a1b890bb3df62baf32f7")
    if abs_tick & 0x8000 != 0:
        ratio = mul_shift(ratio, "0x31be135f97d08fd981231505542fcfa6")
    if abs_tick & 0x10000 != 0:
        ratio = mul_shift(ratio, "0x9aa508b5b7a84e1c677de54f3e99bc9")
    if abs_tick & 0x20000 != 0:
        ratio = mul_shift(ratio, "0x5d6af8dedb81196699c329225ee604")
    if abs_tick & 0x40000 != 0:
        ratio = mul_shift(ratio, "0x2216e584f5fa1ea926041bedfe98")
    if abs_tick & 0x80000 != 0:
        ratio = mul_shift(ratio, "0x48a170391f7dc42444e8fa2")

    if tick > 0:
        ratio = MAX_UINT256 // ratio

    return (ratio // Q32) + 1 if ratio % Q32 > 0 else ratio // Q32
