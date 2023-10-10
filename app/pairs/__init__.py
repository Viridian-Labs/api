# -*- coding: utf-8 -*-

import json

import falcon
from web3 import Web3

from app.assets import Token
from app.gauges import Gauge
from app.misc import JSONEncoder
from app.settings import (
    CACHE,
    LOGGER,
    PAIR_CACHE_EXPIRATION,
    reset_multicall_pool_executor,
)

from .model import Pair


class Pairs(object):
    """Handles our liquidity pools/pairs"""

    # Seconds to expire the cache, a bit longer than the syncer schedule...

    CACHE_KEY = "pairs:json"

    @classmethod
    def serialize(cls):
        serialized_pairs = []

        for pair in Pair.all():
            data = pair._data

            token0 = Token.find(pair.token0_address)
            if token0:
                data["token0"] = token0._data
            else:
                LOGGER.warning(
                    "Token not found for address: %s", pair.token0_address
                )
                data["token0"] = None

            token1 = Token.find(pair.token1_address)
            if token1:
                data["token1"] = token1._data
            else:
                LOGGER.warning(
                    "Token not found for address: %s", pair.token1_address
                )
                data["token1"] = None

            if pair.gauge_address:
                gauge = Gauge.find(pair.gauge_address)
                if gauge:
                    data["gauge"] = gauge._data
                    data["gauge"]["bribes"] = []

                    for token_addr, reward_ammount in gauge.rewards:
                        token_data = Token.find(token_addr)
                        if token_data:
                            data["gauge"]["bribes"].append(
                                dict(
                                    token=token_data._data,
                                    reward_ammount=float(reward_ammount),
                                    # TODO: Backwards compat...
                                    rewardAmmount=float(reward_ammount),
                                )
                            )
                        else:
                            LOGGER.warning(
                                "Token not found for address in gauge \
                                    rewards: %s",
                                token_addr,
                            )

                else:
                    LOGGER.warning(
                        "Gauge not found for address: %s", pair.gauge_address
                    )

            serialized_pairs.append(data)

        return serialized_pairs

    @classmethod
    def recache(cls):
        pairs = json.dumps(dict(data=cls.serialize()), cls=JSONEncoder)

        CACHE.set(cls.CACHE_KEY, pairs)
        CACHE.expire(cls.CACHE_KEY, PAIR_CACHE_EXPIRATION)

        LOGGER.debug("Cache updated for %s.", cls.CACHE_KEY)

        return pairs

    def resync(self, pair_address, gauge_address):
        """Resyncs a pair based on it's address or gauge address."""
        if Web3.isAddress(gauge_address):
            old_pair = Pair.get(
                Pair.gauge_address == str(gauge_address).lower()
            )
            Pair.from_chain(old_pair.address)
        elif Web3.isAddress(pair_address):
            Pair.from_chain(pair_address)
        else:
            return

        reset_multicall_pool_executor()
        Pairs.recache()

    def on_get(self, req, resp):
        """Returns cached liquidity pools/pairs"""
        self.resync(
            req.get_param("pair_address"), req.get_param("gauge_address")
        )

        pairs = CACHE.get(self.CACHE_KEY) or Pairs.recache()

        resp.status = falcon.HTTP_200
        resp.text = pairs
