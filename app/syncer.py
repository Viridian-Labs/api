# -*- coding: utf-8 -*-

import time
import json

from app.assets import Assets, Token
from app.pairs import Pairs, Pair
from app.settings import CACHE, LOGGER, SYNC_WAIT_SECONDS, TOKEN_CACHE_EXPIRATION, reset_multicall_pool_executor
from app.vara import VaraPrice
from app.circulating import CirculatingSupply
from app.configuration import Configuration
from app.misc import ModelUteis, JSONEncoder



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
        # Sync basic data
        LOGGER.info("Syncing pairs ...")
        t0 = time.time()

        Syncer.sync_tokens()
        Syncer.sync_pairs()
        #Syncer.sync_circulating()
        #Syncer.sync_configuration()
        #Syncer.sync_supply()
        #Syncer.sync_vara()

        LOGGER.info("Syncing data done in %s seconds.",  time.time() - t0)
        
        try:
            LOGGER.debug("Syncing zero-price tokens")            
            zero_price_tokens = ModelUteis.get_zero_price_tokens()
            pairs_data = json.loads(CACHE.get("pairs:json").decode('utf-8')).get('data', [])
            
            for token in zero_price_tokens:
                LOGGER.debug(f"Updating price for {token.symbol} through pairs")           
                
                best_price = float('inf')
                for pair_data in pairs_data:
                    pair = Pair.find(pair_data['address'])
                    
                    if token.address not in [pair.token0_address, pair.token1_address]:
                        continue

                    opposing_token_address = pair.token1_address if token.address == pair.token0_address else pair.token0_address
                    opposing_token = Token.find(opposing_token_address)
                    
                    price_through_tokens = token._get_price_through_tokens([token.address], opposing_token)
                    direct_price = token._get_direct_price(opposing_token)

                    valid_prices = [price for price in [price_through_tokens, direct_price] if price > 0]
                    
                    if valid_prices:
                        current_best = min(valid_prices)
                        best_price = min(best_price, current_best)
                        
                        LOGGER.debug(f"Price for {token.symbol} is {current_best} through pair {pair.symbol} for token {opposing_token.symbol}")

                if best_price != float('inf'):
                    token.price = best_price

        except Exception as e:
            LOGGER.error(f"Error during syncing zero-price tokens: {e}")
        
        LOGGER.debug("Updating cache for assets:json")

        serializable_tokens = [tok._data for tok in Token.all()]

        print('serializable_tokens', serializable_tokens)

        CACHE.set("assets:json", json.dumps(dict(data=serializable_tokens), cls=JSONEncoder))
        CACHE.expire("assets:json", TOKEN_CACHE_EXPIRATION)

        quit(0)

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
