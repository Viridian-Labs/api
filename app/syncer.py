# -*- coding: utf-8 -*-

import time
import requests
from multicall import Call, Multicall

from app.assets import Assets, Token
from app.pairs import Pairs, Pair
from app.settings import CACHE, LOGGER, SYNC_WAIT_SECONDS, ROUTER_ADDRESS, reset_multicall_pool_executor
from app.vara import VaraPrice
from app.circulating import CirculatingSupply
from app.configuration import Configuration


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
    def sync_special():
        token_addresses = {
            'GMD': '0xeffae8eb4ca7db99e954adc060b736db78928467',
            'spVARA': '0x489e54eec6c228a1457975eb150a7efb8350b5be',
            'acsVARA': '0x53a5dd07127739e5038ce81eff24ec503a6cc479',
            'CHAM': '0x0fb3e4e84fb78c93e466a2117be7bc8bc063e430',
            'xSHRAP': '0xe1e9db9b4d51a8878f030094f7965edc5eec7802',
            'SHRP': '0x308f66ebee21861d304c8013eb3a9a5fc78a8a6c',
        }

        pairs_data = requests.get('https://api.equilibrefinance.com/api/v1/pairs').json()['data']
        relevant_pairs = [pair for pair in pairs_data if pair['token0']['address'] in token_addresses.values() or pair['token1']['address'] in token_addresses.values()]

        for pair in relevant_pairs:
            token0 = pair['token0']
            token1 = pair['token1']

            if token0['symbol'] in token_addresses:
                our_token = token0
                other_token = token1
            elif token1['symbol'] in token_addresses:
                our_token = token1
                other_token = token0
            else:
                continue

            LOGGER.info(f"Checking price for {our_token['symbol']}: {other_token['symbol']} via  {pair['symbol']}:{pair['address']}")

            token = Token.find(our_token['address'])

            price = token._get_direct_price(Token.find(other_token['address']))

            token.price = float(price)

            token.save()

            LOGGER.info(f"Price for {token.symbol}: {token.price} - updated using other token {other_token['symbol']}")

        Assets.force_recache()
        LOGGER.info("Assets cache updated")
        
                    
                                     

    @staticmethod
    def sync():
        t0 = time.time()
        LOGGER.info("Syncing data...")

        Syncer.sync_tokens()
        t1 = time.time()

        Syncer.sync_pairs()
        t2 = time.time()

        Syncer.sync_special()
        t3 = time.time()

        Syncer.sync_circulating()
        t4 = time.time()

        Syncer.sync_configuration()
        t5 = time.time()

        Syncer.sync_supply()
        t6 = time.time()

        Syncer.sync_vara()
        t7 = time.time()

        LOGGER.info("Syncing tokens data done in %s seconds.", t1 - t0)
        LOGGER.info("Syncing pairs data done in %s seconds.", t2 - t1)
        LOGGER.info("Syncing special data done in %s seconds.", t3 - t2)
        LOGGER.info("Syncing circulating data done in %s seconds.", t4 - t3)
        LOGGER.info("Syncing configuration data done in %s seconds.", t5 - t4)
        LOGGER.info("Syncing supply data done in %s seconds.", t6 - t5)
        LOGGER.info("Syncing vara data done in %s seconds.", t7 - t6)
        LOGGER.info("Total syncing time: %s seconds.", t7 - t0)

        reset_multicall_pool_executor()

        

    @staticmethod
    def sync_forever():
        LOGGER.info(f"Syncing every {SYNC_WAIT_SECONDS} seconds ...")

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
