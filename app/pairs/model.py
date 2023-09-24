# -*- coding: utf-8 -*-

import math

from multicall import Call, Multicall
from walrus import BooleanField, FloatField, IntegerField, Model, TextField
from web3.constants import ADDRESS_ZERO

from app.assets import Token
from app.gauges import Gauge
from app.settings import (
    CACHE,
    DEFAULT_TOKEN_ADDRESS,
    FACTORY_ADDRESS,
    LOGGER,
    MULTICHAIN_TOKEN_ADDRESSES,
    VOTER_ADDRESS,
)


class Pair(Model):
    """Liquidity pool pairs model."""

    __database__ = CACHE

    address = TextField(primary_key=True)
    symbol = TextField()
    decimals = IntegerField()
    stable = BooleanField()
    total_supply = FloatField()
    reserve0 = FloatField()
    reserve1 = FloatField()
    token0_address = TextField(index=True)
    token1_address = TextField(index=True)
    gauge_address = TextField(index=True)
    tvl = FloatField(default=0)
    apr = FloatField(default=0)

    # TODO: Backwards compat. Remove once no longer needed...
    isStable = BooleanField()
    totalSupply = FloatField()

    def token_price(self):
        """LP token price.

        Uses: https://blog.alphaventuredao.io/fair-lp-token-pricing/
        """
        token0_price = Token.find(self.token0).chain_price_in_stables()
        token1_price = Token.find(self.token1).chain_price_in_stables()

        if token0_price == 0 or token1_price == 0:
            return 0

        sqrtK = math.sqrt(self.reserve0 * self.reserve1)
        sqrtP = math.sqrt(token0_price * token1_price)

        return 2 * ((sqrtK * sqrtP) / self.totalSupply)

    def syncup_gauge(self):
        """Fetches own gauges data from chain."""
        if self.gauge_address in (ADDRESS_ZERO, None):
            return

        gauge = Gauge.from_chain(self.gauge_address)
        self._update_apr(gauge)

        return gauge

    def _update_apr(self, gauge):
        """Calculates the pool TVL"""
        if self.tvl == 0:
            return

        token = Token.find(DEFAULT_TOKEN_ADDRESS)
        token_price = token.chain_price_in_stables()

        daily_apr = (gauge.reward * token_price) / self.tvl * 100

        self.apr = daily_apr * 365
        self.save()

    @classmethod
    def find(cls, address):
        """Loads a token from cache, of from chain if not found."""
        if address is None:
            return None

        try:
            return cls.load(address.lower())
        except KeyError:
            return cls.from_chain(address.lower())

    @classmethod
    def chain_addresses(cls):
        """Fetches pairs/pools from chain."""
        pairs_count = Call(FACTORY_ADDRESS, "allPairsLength()(uint256)")()

        pairs_multi = Multicall(
            [
                Call(
                    FACTORY_ADDRESS,
                    ["allPairs(uint256)(address)", idx],
                    [[idx, None]]
                )
                for idx in range(0, pairs_count)
            ]
        )

        return list(pairs_multi().values())

    @classmethod
    def from_chain(cls, address):
        """Fetches pair/pool data from chain."""
        address = address.lower()
        data = cls._fetch_pair_data_from_chain(address)
        if not data:
            return None
        
        cls._normalize_data(data)
        cls._patch_symbol(data)
        cls._cleanup_old_data(address)
        
        pair = cls.create(**data)
        LOGGER.debug("Fetched %s:(%s) %s.", cls.__name__, pair.symbol, pair.address)
        
        pair.syncup_gauge()
        return pair
    
    
    @classmethod
    def _fetch_pair_data_from_chain(cls, address):
        try:
            pair_multi = cls._prepare_multicall(address)
            data = pair_multi()
            LOGGER.debug("Loading %s:(%s) %s.", cls.__name__, data["symbol"], address)
            data["address"] = address
            return data
        except Exception as e:
            LOGGER.error("Error fetching pair data from chain for address %s: %s", address, e)
            return None
        

    @classmethod
    def _normalize_data(cls, data):
        try:
            data["total_supply"] = data["total_supply"] / (10 ** data["decimals"])
        except TypeError:
            LOGGER.error("Invalid decimals in total_supply normalization: %s", data["decimals"])
            return  
        
        token0 = Token.find(data["token0_address"])
        token1 = Token.find(data["token1_address"])
        
        try:
            data["reserve0"] = data["reserve0"] / (10 ** int(token0.decimals))
        except (TypeError, ValueError):
            LOGGER.error("Invalid decimals in reserve0 normalization: %s", token0.symbol)
            return  
        
        try:
            data["reserve1"] = data["reserve1"] / (10 ** int(token1.decimals))
        except (TypeError, ValueError):
            LOGGER.error("Invalid decimals in reserve1 normalization: %s", token1.decimals)
            return  
        
        data["gauge_address"] = data["gauge_address"].lower() if data.get("gauge_address") not in (ADDRESS_ZERO, None) else None
        data["tvl"] = cls._tvl(data, token0, token1)
        data["isStable"] = data["stable"]
        data["totalSupply"] = data["total_supply"]


    @classmethod
    def _patch_symbol(cls, data):
        if data["token0_address"] in MULTICHAIN_TOKEN_ADDRESSES:
            aux_symbol = data["symbol"]
            data["symbol"] = aux_symbol[:5] + "multi" + aux_symbol[5:]
        if data["token1_address"] in MULTICHAIN_TOKEN_ADDRESSES:
            aux_symbol = data["symbol"]
            slash_index = aux_symbol.find("/") + 1
            data["symbol"] = aux_symbol[:slash_index] + "multi" + aux_symbol[slash_index:]

    @classmethod
    def _cleanup_old_data(cls, address):
        cls.query_delete(cls.address == address.lower())
        

    @classmethod
    def _prepare_multicall(cls, address):
        """
        Prepares a Multicall object with multiple blockchain method calls.
        
        :param address: The address on the blockchain to call methods on.
        :type address: str
        :return: A Multicall object with prepared method calls.
        :rtype: Multicall
        """
        return Multicall(
            [
                Call(
                    address,
                    "getReserves()(uint256,uint256)",
                    [["reserve0", None], ["reserve1", None]],
                ),
                Call(address, "token0()(address)", [["token0_address", None]]),
                Call(address, "token1()(address)", [["token1_address", None]]),
                Call(address, "totalSupply()(uint256)", [["total_supply", None]]),
                Call(address, "symbol()(string)", [["symbol", None]]),
                Call(address, "decimals()(uint8)", [["decimals", None]]),
                Call(address, "stable()(bool)", [["stable", None]]),
                Call(
                    VOTER_ADDRESS,
                    ["gauges(address)(address)", address],
                    [["gauge_address", None]],
                ),
            ]
        )


    @classmethod
    def _tvl(cls, pool_data, token0, token1):
        """Returns the TVL of the pool."""
        tvl = 0

        if token0.price and token0.price != 0:
            # LOGGER.debug(
            #     "Pool %s:(%s) has a price of %s
            # for token0. And a reserve of %s.",
            #     cls.__name__,
            #     pool_data["symbol"],
            #     token0.price,
            #     pool_data["reserve0"],
            # )
            tvl += pool_data["reserve0"] * token0.price

        if token1.price and token1.price != 0:
            # LOGGER.debug(
            #     "Pool %s:(%s) has a price of %s
            # for token1. And a reserve of %s.",
            #     cls.__name__,
            #     pool_data["symbol"],
            #     token1.price,
            #     pool_data["reserve1"],
            # )
            tvl += pool_data["reserve1"] * token1.price

        if tvl != 0 and (token0.price == 0 or token1.price == 0):
            LOGGER.debug(
                "Pool %s:(%s) has a price of 0 for one of its tokens.",
                cls.__name__,
                pool_data["symbol"],
            )
            tvl = tvl * 2
        LOGGER.debug(
            "Pool %s:(%s) has a TVL of %s.",
            cls.__name__, pool_data["symbol"], tvl
        )
        return tvl
