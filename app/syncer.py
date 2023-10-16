# -*- coding: utf-8 -*-

import time
import concurrent.futures

from app.assets import Assets
from app.pairs import Pair, Pairs
from app.settings import CACHE, LOGGER, SYNC_WAIT_SECONDS, reset_multicall_pool_executor
from app.vara import VaraPrice
from app.circulating import CirculatingSupply
from app.configuration import Configuration


def is_cache_expired(key):
    ttl = CACHE.ttl(key)
    return ttl is None or ttl <= 0


def sync_with_cache(key, task_name, sync_function, *args):
    """Generalized function to check cache and run sync functions."""
    cached_data_str = CACHE.get(key)
    if cached_data_str and not is_cache_expired(key):
        LOGGER.debug(f"Using cached {task_name}.")
    else:
        LOGGER.debug(f"Updating {task_name} data...")
        sync_function(*args)


def sync_tokens():
    sync_with_cache("assets:json", "Token List", Assets.sync)

def sync_circulating():
    sync_with_cache("supply:string", "circulating supply", CirculatingSupply.recache)

def sync_configuration():
    sync_with_cache("volume:json", "configuration", Configuration.dexscreener_volume_data)

def sync_pairs():
    sync_with_cache("pairs:json", "Pairs", sync_pairs_data)

def sync_vara():
    sync_with_cache("vara:json", "VARA price", VaraPrice.recache)

def sync_supply():
    sync_with_cache("supply:json", "supply", CirculatingSupply.recache)

def sync_pairs_data():
    addresses = Pair.chain_addresses()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        LOGGER.debug(
            "Syncing %s pairs using %s threads...",
            len(addresses),
            executor._max_workers
        )
        executor.map(Pair.from_chain, addresses)
    Pairs.recache()

def sync():
    t0 = time.time()
    
    LOGGER.info("Syncing tokens ...")
    sync_tokens()
    
    # Concurrent execution
    with concurrent.futures.ThreadPoolExecutor() as executor:
        tasks = [
            executor.submit(task_func) for task_func in [
                sync_pairs, sync_vara, sync_supply, sync_circulating, sync_configuration
            ]
        ]
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

