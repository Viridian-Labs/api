# -*- coding: utf-8 -*-

import json
import math
from datetime import timedelta

import falcon
import requests
from versiontools import Version

from app import __version__
from app.pairs import Pair, Token
from app.settings import (
    CACHE,
    DEFAULT_TOKEN_ADDRESS,
    LOGGER,
    ROUTE_TOKEN_ADDRESSES,
    STABLE_TOKEN_ADDRESS,
)


class Configuration(object):
    """Returns an app configuration object."""
   
    DEXSCREENER_ENDPOINT = "https://api.dexscreener.com/latest/dex/pairs/kava/"
    CACHE_KEY = "volume:json"
    CACHE_TIME = timedelta(minutes=5)


    def dexscreener_volume_data():

        pairs_addresses = [p.address for p in Pair.all() if p]  # Handle case where p might be None
        if not pairs_addresses:
            LOGGER.warning("No pair addresses found.")
            return {
                "volume_m5": None,
                "volume_h1": None,
                "volume_h6": None,
                "volume_h24": None
            }

        subgroup_size = max(1, math.ceil(len(pairs_addresses) / 30))
        LOGGER.debug(f"Subgroup size: {subgroup_size}")

        pairs_addresses_subgroups = [
            pairs_addresses[i:i + subgroup_size] for i in range(0, len(pairs_addresses), subgroup_size)
        ]

        volume_m5, volume_h1, volume_h6, volume_h24 = 0, 0, 0, 0
        for sub_pair_group in pairs_addresses_subgroups:
            try:
                response = requests.get(f"{Configuration.DEXSCREENER_ENDPOINT},{','.join(sub_pair_group)}")
                response.raise_for_status()

                res_json = response.json()
                if "pairs" not in res_json or res_json["pairs"] is None:
                    LOGGER.warning("The 'pairs' key is missing or None in the API response.")
                    continue

                pairs_data = res_json["pairs"]
                volume_m5 += sum(p["volume"].get("m5", 0) for p in pairs_data)
                volume_h1 += sum(p["volume"].get("h1", 0) for p in pairs_data)
                volume_h6 += sum(p["volume"].get("h6", 0) for p in pairs_data)
                volume_h24 += sum(p["volume"].get("h24", 0) for p in pairs_data)
            except requests.RequestException as e:
                LOGGER.error(f"API request failed: {e}")

        volume_data = {
            "volume_m5": volume_m5,
            "volume_h1": volume_h1,
            "volume_h6": volume_h6,
            "volume_h24": volume_h24,
        }
        CACHE.set(Configuration.CACHE_KEY, json.dumps(volume_data), Configuration.CACHE_TIME)

        return volume_data

    
    def on_get(self, req, resp):
        default_token = Token.find(DEFAULT_TOKEN_ADDRESS)
        stable_token = Token.find(STABLE_TOKEN_ADDRESS)

        if not default_token or not stable_token:
            LOGGER.warning("Essential tokens not found!")
            resp.status = falcon.HTTP_204
            return

        route_token_addresses = set(ROUTE_TOKEN_ADDRESSES) - {DEFAULT_TOKEN_ADDRESS, STABLE_TOKEN_ADDRESS}
        route_tokens = [default_token, stable_token] + [Token.find(address) for address in route_token_addresses]

        if len(route_tokens) != len(ROUTE_TOKEN_ADDRESSES):
            LOGGER.warning("Some route tokens are missing!")
            resp.status = falcon.HTTP_204
            return

        all_pairs = [pair for pair in Pair.all()]
        tvl = sum(pair.tvl for pair in all_pairs if pair.tvl) if all_pairs else None
        max_apr = max(pair.apr for pair in all_pairs if pair.apr) if all_pairs else None

        cached_volume = CACHE.get(Configuration.CACHE_KEY)
        volume_data = json.loads(cached_volume.decode("utf-8")) if cached_volume else self.dexscreener_volume_data()

        if not route_tokens or not all_pairs or not tvl or not max_apr or not volume_data:
            LOGGER.warning("Required data is missing!")
            resp.status = falcon.HTTP_204
            return

        resp.status = falcon.HTTP_200
        resp.media = {
            "data": [token._data for token in route_tokens],
            "meta": {
                "tvl": tvl,
                "max_apr": max_apr,
                "volume": volume_data,
                "default_token": default_token._data,
                "stable_token": stable_token._data,
                "cache": (CACHE.connection is not None),
                "version": str(Version(*__version__)),
            }
        }
