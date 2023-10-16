# -*- coding: utf-8 -*-

import time
import concurrent.futures

from app.assets import Assets, Token
from app.pairs import Pair, Pairs
from app.settings import (CACHE, LOGGER, SYNC_WAIT_SECONDS, TOKEN_CACHE_EXPIRATION,
                          reset_multicall_pool_executor)
from app.vara import VaraPrice
from app.circulating import CirculatingSupply


def is_cache_expired(key):
    ttl = CACHE.ttl(key)
    return ttl is None or ttl <= 0


def sync_tokens():
    cached_tokens_str = CACHE.get("assets:json")
    if cached_tokens_str and not is_cache_expired("assets:json"):
        LOGGER.debug("Using cached Token List.")
    else:
        LOGGER.debug("Updating Token List data...")
        Assets.sync()


def sync_pairs():
    cached_pairs_str = CACHE.get("pairs:json")
    if cached_pairs_str and not is_cache_expired("pairs:json"):
        LOGGER.debug("Using cached Pairs.")
    else:
        LOGGER.debug("Updating Pairs data...")
        addresses = Pair.chain_addresses()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            LOGGER.debug(
                "Syncing %s pairs using %s threads...",
                len(addresses),
                executor._max_workers
            )
            executor.map(Pair.from_chain, addresses)
        Pairs.recache()


def sync_vara():
    cached_vara_str = CACHE.get("vara:json")
    if cached_vara_str and not is_cache_expired("vara:json"):
        LOGGER.debug("Using cached VARA price")
    else:
        LOGGER.debug("Updating VARA price...")
        VaraPrice.recache()


def sync_supply():
    cached_tokens_str = CACHE.get("supply:string")
    if cached_tokens_str and not is_cache_expired("supply:string"):
        LOGGER.debug("Using cached supply.")
    else:
        LOGGER.debug("Updating supply data...")
        CirculatingSupply.recache()


def sync():
    t0 = time.time()
    
    # Sync tokens first
    LOGGER.info("Syncing tokens ...")
    sync_tokens()
    
    # Then run other tasks concurrently
    with concurrent.futures.ThreadPoolExecutor() as executor:
        tasks = [executor.submit(task_func) for task_func in [sync_pairs, sync_vara, sync_supply]]
        for task in concurrent.futures.as_completed(tasks):
            task.result()
    
    LOGGER.info("Total Syncing done in %s seconds.", time.time() - t0)
    reset_multicall_pool_executor()


def sync_forever():
    LOGGER.info("Syncing every %s seconds ...", SYNC_WAIT_SECONDS)

    while True:
        try:
            sync()
        except KeyboardInterrupt:
            LOGGER.info("Syncing stopped!")
            break
        except Exception as error:
            LOGGER.error(error)

        time.sleep(SYNC_WAIT_SECONDS)


