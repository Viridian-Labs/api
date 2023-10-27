# -*- coding: utf-8 -*-

import time
import json

from app.assets import Assets, Token
from app.pairs import Pairs, Pair
from app.settings import CACHE, LOGGER, SYNC_WAIT_SECONDS, TOKEN_CACHE_EXPIRATION, reset_multicall_pool_executor
from app.vara import VaraPrice
from app.circulating import CirculatingSupply
from app.configuration import Configuration
from app.misc import ModelUteis


class Syncer:

    @staticmethod
    def is_cache_expired(key):
        ttl = CACHE.ttl(key)
        return ttl is None or ttl <= 0

    @staticmethod
    def sync_with_cache(key, task_name, sync_function, *args):
        """Generalized function to check cache and run sync functions."""
        if not CACHE.get(key) or Syncer.is_cache_expired(key):
            LOGGER.debug(f"Updating {task_name} data...")
            sync_function(*args)
        else:
            LOGGER.debug(f"Using cached {task_name}.")

    @staticmethod
    def sync_tokens():
        Syncer.sync_with_cache("assets:json", "Token List", Assets.sync)

    @staticmethod
    def sync_circulating():
        Syncer.sync_with_cache("supply:string", "circulating supply", CirculatingSupply.sync)

    @staticmethod
    def sync_configuration():
        Syncer.sync_with_cache("volume:json", "configuration", Configuration.sync)

    @staticmethod
    def sync_pairs():
        Syncer.sync_with_cache("pairs:json", "Pairs", Pairs.sync)
    
    @staticmethod
    def sync_supply():
        Syncer.sync_with_cache("supply:json", "supply", CirculatingSupply.sync)

    @staticmethod
    def sync_vara():
        Syncer.sync_with_cache("vara:json", "VARA price", VaraPrice.sync)

    @staticmethod
    def sync():
        LOGGER.info("Syncing pairs ...")
        t0 = time.time()

        Syncer.sync_tokens()
        Syncer.sync_pairs()
        Syncer.sync_circulating()
        Syncer.sync_configuration()
        Syncer.sync_supply()
        Syncer.sync_vara()

        LOGGER.info("Syncing data done in %s seconds.",  time.time() - t0)
        
        t1 = time.time()        

        try:
            LOGGER.debug("Syncing zero-price tokens")            
            zero_price_tokens = ModelUteis.get_zero_price_tokens()
            
            pairs_data = json.loads(CACHE.get("pairs:json").decode('utf-8')).get('data', [])
                       
            for token in zero_price_tokens:     

                LOGGER.debug(f"Updating price for {token.symbol} through pairs")           

                for pair_data in pairs_data:

                    pair = Pair.find(pair_data['address'])
                    tokenn = Token.find(token.address)    
                    price = 0
                    
                    if token.address == pair.token0_address:                        
                        price = tokenn._get_direct_price(Token.find(pair.token1_address))
                        LOGGER.debug(f"Price for {token.symbol} is {price} through pair {pair.symbol} using token {pair.token1_address}")
                    elif token.address == Pair(pair.token1_address):
                        price = tokenn._get_direct_price(Token.find(pair.token0_address))
                        LOGGER.debug(f"Price for {token.symbol} is {price} through pair {pair.symbol} using token {pair.token0_address}")
                    if price > 0:
                        LOGGER.debug(f"Updating price for {token.symbol} to {price} though pair {pair.symbol}")
                        token.price = price
                        token.save()
                        break

            tokens = Token.all()
            serializable_tokens = [tok._data for tok in tokens]
            CACHE.set("assets:json", json.dumps(dict(data=serializable_tokens)))
            CACHE.expire("assets:json", TOKEN_CACHE_EXPIRATION)
            LOGGER.debug("Cache updated for assets:json.")
                    
                                                                                                                                   
        except TypeError as e:
            LOGGER.error(f"Failed to deserialize pairs: {e}")
        
        reset_multicall_pool_executor()

    @staticmethod
    def sync_forever():
        LOGGER.info(f"Syncing every {SYNC_WAIT_SECONDS} seconds ...")
        LOGGER.info("Performing initial sync...")
        LOGGER.info("Initial sync finished...")

        while True:
            try:
                Syncer.sync()
            except KeyboardInterrupt:
                LOGGER.info("Syncing stopped!")
                break
            except Exception as error:
                LOGGER.error(error)

            time.sleep(SYNC_WAIT_SECONDS)


syncer = Syncer()
