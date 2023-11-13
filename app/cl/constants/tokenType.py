# Not using enum because it's not json serializable
Token_Type = {
    "VARA": -10,
    "LSD": -1,
    "NEAD": -2,
    "OTHERS": 0,
    "WETH": 1,
    "LOOSE_STABLE": 2,
    "STABLE": 3,
}

token_type_dict = {
    "gDAI": Token_Type['LOOSE_STABLE'],
    "LUSD": Token_Type['LOOSE_STABLE'],
    "ERN": Token_Type['LOOSE_STABLE'],
    "stERN": Token_Type['LOOSE_STABLE'],
    "DOLA": Token_Type['LOOSE_STABLE'],
    "MAI": Token_Type['LOOSE_STABLE'],
    "GRAI": Token_Type['LOOSE_STABLE'],
    "jEUR": Token_Type["LOOSE_STABLE"],
    "STAR": Token_Type["LOOSE_STABLE"],

    "USDC": Token_Type['STABLE'],
    "USDC.e": Token_Type['STABLE'],
    "USDT": Token_Type['STABLE'],
    "FRAX": Token_Type['STABLE'],
    "DAI": Token_Type['STABLE'],

    "frxETH": Token_Type['LSD'],
    "sfrxETH": Token_Type['LSD'],
    "stETH": Token_Type['LSD'],
    "wstETH": Token_Type["LSD"],
    "swETH": Token_Type["LSD"],    
}

weth_address = "0x1a35EE4640b0A3B87705B0A4B45D227Ba60Ca2ad".lower()
vara_address = "0xE1da44C0dA55B075aE8E2e4b6986AdC76Ac77d73".lower()
