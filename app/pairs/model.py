# -*- coding: utf-8 -*-

import time

from app.assets import Token
from app.gauges import Gauge
from app.settings import (CACHE, DEFAULT_TOKEN_ADDRESS, FACTORY_ADDRESS,
                          LOGGER, MULTICHAIN_TOKEN_ADDRESSES, RETRY_COUNT,
                          RETRY_DELAY, VOTER_ADDRESS)
from multicall import Call, Multicall
from walrus import BooleanField, FloatField, IntegerField, Model, TextField
from web3.constants import ADDRESS_ZERO


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

    def syncup_gauge(self, retry_count=RETRY_COUNT, retry_delay=RETRY_DELAY):
        """Fetches and updates the gauge data associated
        with this pair from the blockchain."""

        if self.gauge_address in (ADDRESS_ZERO, None):
            return

        gauge_address_str = (
            self.gauge_address.decode("utf-8")
            if isinstance(self.gauge_address, bytes)
            else self.gauge_address
        )

        for _ in range(retry_count):
            try:
                gauge = Gauge.from_chain(gauge_address_str)
                self._update_apr(gauge)
                return gauge
            except Exception as e:
                LOGGER.error(
                    f"Error fetching gauge for address {self.address}: {e}"
                )
                LOGGER.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)

        return None

    def _update_apr(self, gauge):

        if self.tvl == 0:
            return

        token = Token.find(DEFAULT_TOKEN_ADDRESS)

        if token is not None and gauge is not None:
            token_price = token.price
            daily_apr = (gauge.reward * token_price) / self.tvl * 100
            self.apr = daily_apr * 365

        self.save()

    @classmethod
    def find(cls, address):

        if address is None:
            return None

        try:
            return cls.load(address.lower())
        except KeyError:
            return cls.from_chain(address.lower())

    @classmethod
    def chain_addresses(cls):

        pairs_count = Call(FACTORY_ADDRESS, "allPairsLength()(uint256)")()

        pairs_multi = Multicall(
            [
                Call(
                    FACTORY_ADDRESS,
                    ["allPairs(uint256)(address)", idx],
                    [[idx, None]],
                )
                for idx in range(0, pairs_count)
            ]
        )

        return list(pairs_multi().values())

    @classmethod
    def from_chain(cls, address):

        try:
            address = address.lower()

            pair_multi = Multicall(
                [
                    Call(
                        address,
                        "getReserves()(uint256,uint256)",
                        [["reserve0", None], ["reserve1", None]],
                    ),
                    Call(
                        address,
                        "token0()(address)",
                        [["token0_address", None]],
                    ),
                    Call(
                        address,
                        "token1()(address)",
                        [["token1_address", None]],
                    ),
                    Call(
                        address,
                        "totalSupply()(uint256)",
                        [["total_supply", None]],
                    ),
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

            data = pair_multi()
            LOGGER.debug(
                "Loading %s:(%s) %s.", cls.__name__, data["symbol"], address
            )

            data["address"] = address

            data["total_supply"] = data["total_supply"] / (
                10 ** data["decimals"]
            )

            token0 = Token.find(data["token0_address"])
            token1 = Token.find(data["token1_address"])

            if token0 and token1:
                data["reserve0"] = data["reserve0"] / (10**token0.decimals)
                data["reserve1"] = data["reserve1"] / (10**token1.decimals)

            if data.get("gauge_address") in (ADDRESS_ZERO, None):
                data["gauge_address"] = None
            else:
                data["gauge_address"] = data["gauge_address"].lower()

            data["tvl"] = cls._tvl(data, token0, token1)

            data["isStable"] = data["stable"]
            data["totalSupply"] = data["total_supply"]

            symbol_patches = {
                "0x1e221ea8d1440c3549942821412c03f101f5e99a": "vAMM-TOREv1/WKAVA",
                "0xce3433baf2356e8404ca7dcc39eb61feda73e2c8": "vAMM-TOREv1/VARA",
                "0x1ae83a1b9ee963213d1e3ff337f92930582d304f": "vAMM-TOREv2/WKAVA",
                "0xa034bf4c9092be31285c4cd7c5247b90c9f4faaf": "vAMM-multiBNB/multiUSDC",
                "0x530b9201e1dbc11b596367428e5d344ebb636630": "vAMM-multiBNB/VARA",
            }

            for address, symbol in symbol_patches.items():
                if address in data["address"]:
                    data["symbol"] = symbol

            if data["token0_address"] in MULTICHAIN_TOKEN_ADDRESSES:
                data["symbol"] = data["symbol"].replace("/", "/multi")
            if data["token1_address"] in MULTICHAIN_TOKEN_ADDRESSES:
                slash_index = data["symbol"].find("/") + 1
                data["symbol"] = (
                    data["symbol"][:slash_index]
                    + "multi"
                    + data["symbol"][slash_index:]
                )

            cls.query_delete(cls.address == address.lower())

            pair = cls.create(**data)
            LOGGER.debug(
                "Fetched %s:(%s) %s.", cls.__name__, pair.symbol, pair.address
            )

            pair.syncup_gauge()

            return pair

        except Exception as e:
            LOGGER.error(f"Error fetching pair for address {address}: {e}")
            return None

    @classmethod
    def _tvl(cls, pool_data, token0, token1):
        excluded_pools_map = {
            "vAMM-TW1/TW2": "0xe6c4b59c291562fa7d9ff5b39c38e2a28294ec49",
        }

        try:
            if pool_data["symbol"] in excluded_pools_map:
                LOGGER.debug(f"Excluded pool {pool_data['symbol']}")
                return 0

            tvl = 0

            if token0 is not None and token0.price and token0.price != 0:
                tvl += pool_data["reserve0"] * token0.price

            if token1 is not None and token1.price and token1.price != 0:
                tvl += pool_data["reserve1"] * token1.price

            if (
                token0 is not None
                and token1 is not None
                and tvl != 0
                and (token0.price == 0 or token1.price == 0)
            ):
                LOGGER.debug(
                    "Pool %s:(%s) has a price of 0 for one of its tokens.",
                    cls.__name__,
                    pool_data["symbol"],
                )
                tvl = tvl * 2

            LOGGER.debug(
                "Pool %s:(%s) has a TVL of %s.",
                cls.__name__,
                pool_data["symbol"],
                tvl,
            )
            return tvl

        except Exception as e:
            LOGGER.error(f"Error TVL for pool {pool_data.get('symbol')}: {e}")
            return 0

    def balance_of(self, token_address):
        try:
            balance_call = Call(
                self.address, "balanceOf(address)(uint256)", [token_address]
            )
            multicall = Multicall([balance_call])
            result = multicall()
            balance = result.get(balance_call)
            return balance

        except Exception as e:
            LOGGER.error(
                f"Error fetching balance {token_address} {self.address}: {e}"
            )
            return 0

    def total_liquidity(self):
        try:
            liquidity_call = Call(self.address, "totalSupply()(uint256)")
            multicall = Multicall([liquidity_call])
            result = multicall()
            liquidity = result.get(liquidity_call)
            return liquidity

        except Exception as e:
            LOGGER.error(
                f"Error fetching total liquidity for pair {self.address}: {e}"
            )
            return 0
