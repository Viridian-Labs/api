# -*- coding: utf-8 -*-

import json
from datetime import timedelta

import falcon
from multicall import Call, Multicall

from app.settings import (CACHE, DEFAULT_TOKEN_ADDRESS, LOGGER, SUPPLY_CACHE_EXPIRATION,
                          TREASURY_ADDRESS, VE_ADDRESS)


class Supply(object):
    """Handles supply info.

    The class manages the caching and retrieval of supply information. The data
    includes total supply, locked supply, and the circulating supply. This
    endpoint provides a quick way to fetch up-to-date supply metrics.
    """

    CACHE_KEY = "supply:json"
    CACHE_TIME = timedelta(minutes=5)

    @classmethod
    def recache(cls):
        """Re-fetches and caches the supply data.

        This method is used to get fresh data from the blockchain and cache it 
        for quick retrieval.
        """
        supply_multicall = Multicall(
            [
                Call(
                    DEFAULT_TOKEN_ADDRESS,
                    "decimals()(uint256)",
                    [["token_decimals", None]],
                ),
                Call(VE_ADDRESS, "decimals()(uint256)",
                     [["lock_decimals", None]]),
                Call(
                    DEFAULT_TOKEN_ADDRESS,
                    "totalSupply()(uint256)",
                    [["raw_total_supply", None]],
                ),
                Call(
                    DEFAULT_TOKEN_ADDRESS,
                    ["balanceOf(address)(uint256)", VE_ADDRESS],
                    [["raw_locked_supply", None]],
                ),
                Call(
                    DEFAULT_TOKEN_ADDRESS,
                    ["balanceOf(address)(uint256)", TREASURY_ADDRESS],
                    [["raw_treasury_supply", None]],
                ),
            ]
        )

        data = supply_multicall()

        data["total_supply"] = data["raw_total_supply"] / \
            10 ** data["token_decimals"]
        data["locked_supply"] = (
            data["raw_locked_supply"] / 10 ** data["lock_decimals"]
            + data["raw_treasury_supply"] / 10 ** data["token_decimals"]
        )
        data["circulating_supply"] = \
            data["total_supply"] - data["locked_supply"]

        data["percentage_locked"] = \
            data["locked_supply"] / data["total_supply"] * 100

        supply_data = json.dumps(dict(data=data))

        CACHE.set(cls.CACHE_KEY, supply_data)
        CACHE.expire(cls.CACHE_KEY, SUPPLY_CACHE_EXPIRATION)

        LOGGER.debug("Cache updated for %s.", cls.CACHE_KEY)

        return supply_data

    def on_get(self, req, resp):
        """Caches and returns our supply info.

        Fetches the supply data from the cache or calls recache() to get fresh
        data if cache is empty. Returns the data or HTTP 204 if no data is
        available.
        """
        supply_data = CACHE.get(self.CACHE_KEY) or self.recache()

        if supply_data:
            resp.text = supply_data
            resp.status = falcon.HTTP_200
        else:
            LOGGER.warning("Supply data not found in cache!")
            resp.status = falcon.HTTP_204
