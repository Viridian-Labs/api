# -*- coding: utf-8 -*-

import time
import json
from multiprocessing import Process
from multiprocessing.pool import ThreadPool

from app.assets import Assets, Token
from app.pairs import Pair, Pairs
from app.settings import (CACHE, LOGGER, SYNC_WAIT_SECONDS,
                          reset_multicall_pool_executor)
from app.vara import VaraPrice


def is_cache_expired(key):
    # Assuming CACHE.ttl returns the time-to-live of a cache key in seconds
    # or None if the key doesn't exist or doesn't have an expiration.
    ttl = CACHE.ttl(key)
    return ttl is None or ttl <= 0


def sync_tokens():
    """Syncs tokens and updates cache if needed."""
    cached_tokens_str = CACHE.get('assets:json')
    if cached_tokens_str and not is_cache_expired('assets:json'):
        LOGGER.debug("Using cached Token List.")
    else:
        LOGGER.debug("Updating Token List data...")
        Token.from_tokenlists()
        Assets.recache()


def sync_pairs():
    """Syncs pairs and updates cache if needed."""
    cached_pairs_str = CACHE.get('pairs:json')
    if cached_pairs_str and not is_cache_expired('pairs:json'):
        LOGGER.debug("Using cached Pairs.")
    else:
        LOGGER.debug("Updating Pairs data...")
        addresses = Pair.chain_addresses()
        with ThreadPool(4) as pool:
            LOGGER.debug("Syncing %s pairs using %s threads...", len(addresses), pool._processes)
            pool.map(Pair.from_chain, addresses)
        Pairs.recache()


def sync_vara():
    """Syncs tokens and updates cache if needed."""
    cached_vara_str = CACHE.get('vara:json')
    if cached_vara_str and not is_cache_expired('vara:json'):
        LOGGER.debug("Using cached VARA price")
    else:
        LOGGER.debug("Updating VARA price...")        
        VaraPrice.recache()



def sync():
    """Main syncing function."""
    t0 = time.time()

    LOGGER.info("Syncing tokens ...")
    sync_tokens()
    t_tokens = time.time() - t0

    LOGGER.info("Syncing pairs ...")
    t1 = time.time()
    sync_pairs()
    t_pairs = time.time() - t1

    LOGGER.info("Syncing vara ...")
    t2 = time.time()
    sync_vara()
    t_vara = time.time() - t2


    LOGGER.info("Syncing tokens done in %s seconds.", t_tokens)
    LOGGER.info("Syncing pairs done in %s seconds.", t_pairs)
    LOGGER.info("Syncing vara done in %s seconds.", t_vara)
    LOGGER.info("Total Syncing done in %s seconds.", time.time() - t0)

    reset_multicall_pool_executor()


def sync_forever():
    """Continuously syncs at defined intervals."""
    LOGGER.info("Syncing every %s seconds ...", SYNC_WAIT_SECONDS)

    while True:
        sync_proc = Process(target=sync)
        try:
            sync_proc.start()
            sync_proc.join()
        except KeyboardInterrupt:
            LOGGER.info("Syncing stopped!")
            break
        except Exception as error:
            LOGGER.error(error)
        finally:
            sync_proc.terminate()
            sync_proc.join()
            del sync_proc

        time.sleep(SYNC_WAIT_SECONDS)


if __name__ == "__main__":
    if SYNC_WAIT_SECONDS < 1:
        sync()
    else:
        sync_forever()
