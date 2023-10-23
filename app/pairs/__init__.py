# -*- coding: utf-8 -*-

import json

import falcon

import time
from multiprocessing import Process
from multiprocessing.pool import ThreadPool

from web3 import Web3
from app.assets import Token
from app.gauges import Gauge
from app.misc import JSONEncoder
from app.settings import CACHE, LOGGER, reset_multicall_pool_executor

from .model import Pair


class Pairs(object):
     
    """Handles liquidity pools/pairs and related operations."""

    CACHE_KEY = "pairs:json"


    @classmethod
    def sync(cls):
        
        """Syncs pair data from the blockchain and updates the cache."""

        LOGGER.info("Syncing pairs ...")
        t0 = time.time()

        Token.from_tokenlists()


        with ThreadPool(4) as pool:
            addresses = Pair.chain_addresses()

            LOGGER.debug(
                "Syncing %s pairs using %s threads...", len(
                    addresses), pool._processes
            )

            pool.map(Pair.from_chain, addresses)
            pool.close()
            pool.join()

        Pairs.recache() 

        LOGGER.info("Syncing pairs done in %s seconds.", time.time() - t0)

        reset_multicall_pool_executor()


    @classmethod
    def serialize(cls):

        """
        Serializes the list of Pair objects along with related Token and Gauge data
        into a list of dictionaries.
        """

        pairs = []

        for pair in Pair.all():
            data = pair._data            

            data["token0"] = Token.find(pair.token0_address.decode('utf-8')) if isinstance(pair.token0_address, bytes) else Token.find(pair.token0_address)
            data["token1"] = Token.find(pair.token1_address.decode('utf-8')) if isinstance(pair.token1_address, bytes) else Token.find(pair.token1_address)

            if pair.gauge_address:
                print('pair.gauge_address', pair.gauge_address)
                gauge = Gauge.find(pair.gauge_address.decode('utf-8')) if isinstance(pair.gauge_address, bytes) else Gauge.find(pair.gauge_address)

                if gauge is not None:
                    data["gauge"] = gauge._data
                    data["gauge"]["bribes"] = []

                    for (token_addr, reward_ammount) in gauge.rewards:

                        token_addr_str = token_addr.decode('utf-8') if isinstance(token_addr, bytes) else token_addr

                        data["gauge"]["bribes"].append(
                            dict(
                                token=Token.find(token_addr_str),
                                reward_ammount=float(reward_ammount),                                
                                rewardAmmount=float(reward_ammount),
                            )
                        )

            pairs.append(data)

        return pairs


    @classmethod
    def recache(cls):

        """
        Updates the cache with the serialized pairs data.
        """

        pairs = json.dumps(dict(data=cls.serialize()), cls=JSONEncoder)

        CACHE.set(cls.CACHE_KEY, pairs)
        LOGGER.debug("Cache updated for %s.", cls.CACHE_KEY)

        return pairs

    def resync(self, pair_address, gauge_address):
        
        """Resyncs a pair based on it's address or gauge address."""

        if Web3.isAddress(gauge_address):
            old_pair = Pair.get(Pair.gauge_address ==
                                str(gauge_address).lower())
            Pair.from_chain(old_pair.address)
        elif Web3.isAddress(pair_address):
            Pair.from_chain(pair_address)
        else:
            return

        reset_multicall_pool_executor()
        Pairs.recache()

    def on_get(self, req, resp):
        
        """
        Fetches gauge data from the blockchain given an address,
        and updates or creates the corresponding Gauge object in the database.
        """
        
        self.resync(req.get_param("pair_address"),
                    req.get_param("gauge_address"))

        pairs = CACHE.get(self.CACHE_KEY) or Pairs.recache()

        resp.status = falcon.HTTP_200
        resp.text = pairs
