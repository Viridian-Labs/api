# -*- coding: utf-8 -*-

import requests
import requests.exceptions
from multicall import Call, Multicall
from walrus import BooleanField, FloatField, IntegerField, Model, TextField
from web3.auto import w3
from web3.exceptions import ContractLogicError

from app.settings import (
    AXELAR_BLUECHIPS_ADDRESSES,
    BLUECHIP_TOKEN_ADDRESSES,
    CACHE,
    DEFAULT_TOKEN_ADDRESS,
    HALT_API_PRICE_FEEDS,
    IGNORED_TOKEN_ADDRESSES,
    LOGGER,
    NATIVE_TOKEN_ADDRESS,
    ROUTE_TOKEN_ADDRESSES,
    ROUTER_ADDRESS,
    STABLE_TOKEN_ADDRESS,
    TOKENLISTS,
)


class Token(Model):
    """ERC20 token model."""

    __database__ = CACHE

    address = TextField(primary_key=True)
    name = TextField()
    symbol = TextField()
    decimals = IntegerField()
    logoURI = TextField()
    price = FloatField(default=0)
    stable = BooleanField(default=0)
    # To indicate if it's a liquid version of another token as swKAVA
    liquid_staked_address = TextField()
    # TODO: This is the timestamp of the block where the token was created
    # TODO: needed to refresh token data of not whitelisted tokens
    created_at = FloatField(default=w3.eth.get_block("latest").timestamp)

    # See: https://docs.1inch.io/docs/aggregation-protocol/api/swagger
    AGGREGATOR_ENDPOINT = "https://api.1inch.io/v4.0/10/quote"
    # See: https://docs.dexscreener.com/#tokens
    DEXSCREENER_ENDPOINT = "https://api.dexscreener.com/latest/dex/tokens/"
    # See: https://defillama.com/docs/api#operations-tag-coins
    DEFILLAMA_ENDPOINT = "https://coins.llama.fi/prices/current/"

    def defillama_price_in_stables(self):
        """Returns the price quoted from our llama defis."""
        # Peg it forever.
        if self.address == STABLE_TOKEN_ADDRESS:
            return 1.0

        chain_token = "kava:" + self.address.lower()
        res = requests.get(self.DEFILLAMA_ENDPOINT + chain_token).json()
        coins = res.get("coins", {})

        for _, coin in coins.items():
            return coin.get("price", 0)

        return 0

    def one_inch_price_in_stables(self):
        """Returns the price quoted from an aggregator in stables/USDC."""
        # Peg it forever.
        if self.address == STABLE_TOKEN_ADDRESS:
            return 1.0

        stablecoin = Token.find(STABLE_TOKEN_ADDRESS)

        res = requests.get(
            self.AGGREGATOR_ENDPOINT,
            params=dict(
                fromTokenAddress=self.address,
                toTokenAddress=stablecoin.address,
                amount=(1 * 10**self.decimals),
            ),
        ).json()

        amount = res.get("toTokenAmount", 0)

        return int(amount) / 10**stablecoin.decimals

    def dexscreener_price_in_stables(self):
        """Returns the price quoted from an aggregator in stables/USDC."""
        # Peg it forever.
        if self.address == STABLE_TOKEN_ADDRESS:
            return 1.0

        res = requests.get(self.DEXSCREENER_ENDPOINT + self.address).json()
        pairs = res.get("pairs") or []

        if len(pairs) == 0:
            return 0

        pairs_in_kava = [
            pair
            for pair in pairs
            if pair["chainId"] == "kava"
            and pair["dexId"] == "equilibre"
            and pair["quoteToken"]["address"].lower() != self.address.lower()
        ]

        if len(pairs_in_kava) == 0:
            LOGGER.debug(self.symbol)
            price = str(pairs[0].get("priceUsd") or 0).replace(",", "")
            LOGGER.debug(price)
        else:
            price = str(pairs_in_kava[0].get("priceUsd") or 0).replace(",", "")

        # To avoid this kek...
        #   ValueError: could not convert string to float: '140344,272.43'

        return float(price)

    def aggregated_price_in_stables(self):
        # LOGGER.debug("Aggregated price for %s", self.symbol)
        price = self.dexscreener_price_in_stables()
        if self.address == "0xfa9343c3897324496a05fc75abed6bac29f8a40f":
            LOGGER.debug("USDC price bad")
            return 0
        if self.address == "0x919c1c267bc06a7039e03fcc2ef738525769109c":
            LOGGER.debug("USDt price bad")
            return 0
        if price != 0 and self.address not in BLUECHIP_TOKEN_ADDRESSES:
            LOGGER.debug("Dexscreener price for %s: %s", self.symbol, price)
            return price

        try:
            price = self.defillama_price_in_stables()
            LOGGER.debug("Defillama price for %s: %s", self.symbol, price)
            return price
        except (
            requests.exceptions.HTTPError,
            requests.exceptions.JSONDecodeError,
        ):
            return price

    def chain_price_in_stables(self):
        """Returns the price quoted from our router in stables/USDC."""
        # Peg it forever.
        if self.address == STABLE_TOKEN_ADDRESS:
            return 1.0
        # LOGGER.debug("Chain price for %s", self.symbol)
        stablecoin = Token.find(STABLE_TOKEN_ADDRESS)
        LOGGER.debug("Stablecoin %s", stablecoin.symbol)
        try:
            amount, is_stable = Call(
                ROUTER_ADDRESS,
                [
                    "getAmountOut(uint256,address,address)(uint256,bool)",
                    1 * 10**self.decimals,
                    self.address,
                    stablecoin.address,
                ],
            )()
            LOGGER.debug("Chain price for %s: %s", self.symbol, amount)
        except ContractLogicError:
            LOGGER.debug("Found error getting chain price for %s", self.symbol)
            return 0

        return amount / 10**stablecoin.decimals

    def chain_price_in_stables_and_default_token(self):
        """Returns the price quoted from our router in stables/USDC
        passing through default token route or some special cases"""
        # Peg it forever.
        if self.address == STABLE_TOKEN_ADDRESS:
            return 1.0
        LOGGER.debug("Chain price NEW for %s", self.symbol)
        stablecoin = Token.find(STABLE_TOKEN_ADDRESS)
        nativecoin = Token.find(NATIVE_TOKEN_ADDRESS)
        default_token = Token.find(DEFAULT_TOKEN_ADDRESS)
        for token_address in ROUTE_TOKEN_ADDRESSES:
            token = Token.find(token_address)
            LOGGER.debug("CALC THROUGH for %s", token.symbol)
            try:
                amountA, is_stable = Call(
                    ROUTER_ADDRESS,
                    [
                        "getAmountOut(uint256,address,address)(uint256,bool)",
                        1 * 10**self.decimals,
                        self.address,
                        token_address,
                    ],
                )()
                LOGGER.debug("AmountA for %s: %s", token.symbol, amountA)

                amountB, is_stable = Call(
                    ROUTER_ADDRESS,
                    [
                        "getAmountOut(uint256,address,address)(uint256,bool)",
                        amountA,
                        token_address,
                        stablecoin.address,
                    ],
                )()
                LOGGER.debug("AmountB for %s: %s", token.symbol, amountB)

                if token_address in [
                    "0xE3F5a90F9cb311505cd691a46596599aA1A0AD7D".lower(),
                    "0x818ec0A7Fe18Ff94269904fCED6AE3DaE6d6dC0b".lower(),
                ]:
                    amountB, is_stable = Call(
                        ROUTER_ADDRESS,
                        [
                            "getAmountOut(uint256,address,address)"
                            + "(uint256,bool)",
                            amountA,
                            token_address,
                            nativecoin.address,
                        ],
                    )()
                    amountC, is_stable = Call(
                        ROUTER_ADDRESS,
                        [
                            "getAmountOut(uint256,address,address)"
                            + "(uint256,bool)",
                            amountB,
                            nativecoin.address,
                            stablecoin.address,
                        ],
                    )()

                    if amountC > 0:
                        return amountC / 10**stablecoin.decimals
                if (
                    self.symbol in ["ACS", "BNB"]
                    and token_address == default_token.address
                ):
                    continue
                if self.symbol in ["DEXI"] and token.symbol == "multiUSDC":
                    LOGGER.debug("DEXI especial case through LION")
                    lion = Token.find(
                        "0x990e157fC8a492c28F5B50022F000183131b9026"
                    )
                    amountA, is_stable = Call(
                        ROUTER_ADDRESS,
                        [
                            "getAmountOut(uint256,address,address)"
                            + "(uint256,bool)",
                            1 * 10**self.decimals,
                            self.address,
                            lion.address,
                        ],
                    )()
                    amountB, is_stable = Call(
                        ROUTER_ADDRESS,
                        [
                            "getAmountOut(uint256,address,address)"
                            + "(uint256,bool)",
                            amountA,
                            lion.address,
                            token.address,
                        ],
                    )()
                    amountC, is_stable = Call(
                        ROUTER_ADDRESS,
                        [
                            "getAmountOut(uint256,address,address)"
                            + "(uint256,bool)",
                            amountB,
                            token.address,
                            stablecoin.address,
                        ],
                    )()

                    if amountC > 0:
                        return amountC / 10**stablecoin.decimals
                if amountB > 0:
                    return amountB / 10**stablecoin.decimals
                # Special case for TVestige (calc from wKAVA)
                if token_address == nativecoin.address and self.symbol in [
                    "TV"
                ]:
                    amountA = amountA / 10**nativecoin.decimals
                    return amountA * nativecoin.price
            except ContractLogicError:
                return 0

    def chain_price_in_bluechips(self):
        """Returns the price quoted from our router in stables/USDC
        passing through a bluechip route"""
        # Peg it forever.
        if self.address == STABLE_TOKEN_ADDRESS:
            return 1.0
        # LOGGER.debug("Chain price Bluechips for %s", self.symbol)
        stablecoin = Token.find(STABLE_TOKEN_ADDRESS)
        for b in BLUECHIP_TOKEN_ADDRESSES:
            try:
                bluechip = Token.find(b)
                amountA, is_stable = Call(
                    ROUTER_ADDRESS,
                    [
                        "getAmountOut(uint256,address,address)(uint256,bool)",
                        1 * 10**self.decimals,
                        self.address,
                        bluechip.address,
                    ],
                )()
                amountB, is_stable = Call(
                    ROUTER_ADDRESS,
                    [
                        "getAmountOut(uint256,address,address)(uint256,bool)",
                        amountA,
                        bluechip.address,
                        stablecoin.address,
                    ],
                )()
                if amountB > 0:
                    return amountB / 10**stablecoin.decimals
            except ContractLogicError:
                return 0

        return 0

    def chain_price_in_liquid_staked(self):
        """Returns the price quoted from our router in stables/USDC
        passing through a liquid staked route"""
        # Peg it forever.
        if self.address == STABLE_TOKEN_ADDRESS:
            return 1.0
        # LOGGER.debug("Chain price Liquid Staked for %s", self.symbol)
        stablecoin = Token.find(STABLE_TOKEN_ADDRESS)

        try:
            liquid = Token.find(self.liquid_staked_address)
            if not liquid:
                return 0
            amountA, is_stable = Call(
                ROUTER_ADDRESS,
                [
                    "getAmountOut(uint256,address,address)(uint256,bool)",
                    1 * 10**self.decimals,
                    self.address,
                    liquid.address,
                ],
            )()
            amountB, is_stable = Call(
                ROUTER_ADDRESS,
                [
                    "getAmountOut(uint256,address,address)(uint256,bool)",
                    amountA,
                    liquid.address,
                    stablecoin.address,
                ],
            )()
        except ContractLogicError:
            return 0

        return amountB / 10**stablecoin.decimals

    def temporary_price_in_bluechips(self):
        mToken = Token.find(self.liquid_staked_address)
        if not mToken:
            return 0
        return mToken.price

    @classmethod
    def find(cls, address):
        """Loads a token from the database, of from chain if not found."""
        if address is None:
            return None

        try:
            return cls.load(address.lower())
        except KeyError:
            LOGGER.error("ERROR Fetching %s:%s...", cls.__name__, address)
            return cls.from_chain(address.lower())

    def _update_price(self):
        """Updates the token price in USD from different sources."""
        if HALT_API_PRICE_FEEDS is False or self.symbol in [
            "axlWETH",
            "TIGER",
            "SHRP",
            "xSHRAP",
            "axlWBTC",
            "axlATOM",
            "axlWETH",
        ]:
            self.price = self.aggregated_price_in_stables()

        if self.price == 0 and self.symbol not in ["BEAR", "DEXI", "ATOM"]:
            LOGGER.debug("Chain price in stables")
            self.price = self.chain_price_in_stables()
        if self.price == 0:
            # LOGGER.debug("Chain price in bluechips")
            self.price = self.chain_price_in_bluechips()
        if self.price == 0:
            # LOGGER.debug("Chain price in stables and default token")
            self.price = self.chain_price_in_stables_and_default_token()
        if self.price == 0:
            # LOGGER.debug("Chain price in liquid staked")
            self.price = self.chain_price_in_liquid_staked()
        if self.price == 0 and self.address in AXELAR_BLUECHIPS_ADDRESSES:
            # LOGGER.debug("Chain price in bluechips")
            self.price = self.temporary_price_in_bluechips()
        if self.symbol in ["bVARA"]:
            self.price = Token.find(self.liquid_staked_address.lower()).price
        LOGGER.debug("Updated price of %s:%s.", self.address, self.price)

        self.save()

    @classmethod
    def from_chain(cls, address, logoURI=None):
        address = address.lower()
        LOGGER.debug("Fetching from chain %s:%s...", cls.__name__, address)
        """Fetches and returns a token from chain."""
        token_multi = Multicall(
            [
                Call(address, ["name()(string)"], [["name", None]]),
                Call(address, ["symbol()(string)"], [["symbol", None]]),
                Call(address, ["decimals()(uint8)"], [["decimals", None]]),
            ]
        )

        data = token_multi()

        # TODO: Add a dummy logo...
        token = cls.create(address=address, **data)
        token._update_price()

        LOGGER.debug("Fetched %s:%s.", cls.__name__, address)

        return token

    @classmethod
    def from_tokenlists(cls):
        """Fetches and merges all the tokens from available tokenlists."""
        our_chain_id = w3.eth.chain_id

        for tlist in TOKENLISTS:
            try:
                res = requests.get(tlist).json()

                for token_data in res["tokens"]:
                    try:
                        # Skip tokens from other chains...
                        if token_data.get("chainId", None) != our_chain_id:
                            LOGGER.debug(
                                "Token not in chain: %s", token_data["symbol"]
                            )
                            continue
                        LOGGER.debug(
                            "Loading %s---------------------------",
                            token_data["symbol"],
                        )
                        token_data["address"] = token_data["address"].lower()

                        if token_data["address"] in IGNORED_TOKEN_ADDRESSES:
                            continue
                        if token_data["liquid_staked_address"]:
                            token_data["liquid_staked_address"] = token_data[
                                "liquid_staked_address"
                            ].lower()
                        token = cls.create(**token_data)
                        token.stable = (
                            1 if "stablecoin" in token_data["tags"][0] else 0
                        )
                        token._update_price()

                        LOGGER.debug(
                            "Loaded %s:(%s) %s with price %s.-------------",
                            cls.__name__,
                            token_data["symbol"],
                            token_data["address"],
                            token.price,
                        )
                    except Exception as error:
                        LOGGER.error(error)
                        continue
            except Exception as error:
                LOGGER.error(error)
                continue
