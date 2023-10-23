# -*- coding: utf-8 -*-

import time
import concurrent.futures
import traceback

from retrying import retry
from app.assets import Assets
from app.pairs import Pairs
from app.settings import CACHE, LOGGER, SYNC_WAIT_SECONDS, reset_multicall_pool_executor
from app.vara import VaraPrice
from app.circulating import CirculatingSupply
from app.configuration import Configuration


class Syncer:

    def __init__(self):
        pass  

    @staticmethod
    def is_cache_expired(key):
        ttl = CACHE.ttl(key)
        return ttl is None or ttl <= 0


    @staticmethod
    def sync_with_cache(key, task_name, sync_function, *args):
        """Generalized function to check cache and run sync functions."""
        cached_data_str = CACHE.get(key)
        if cached_data_str and not Syncer.is_cache_expired(key):
            LOGGER.debug(f"Using cached {task_name}.")
        else:
            LOGGER.debug(f"Updating {task_name} data...")
            sync_function(*args)


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
    def sync_vara():
        Syncer.sync_with_cache("vara:json", "VARA price", VaraPrice.sync)

    @staticmethod
    def sync_supply():
        Syncer.sync_with_cache("supply:json", "supply", CirculatingSupply.sync)


    @retry(stop_max_attempt_number=3, wait_fixed=2000)  
    def sync(self):
        t0 = time.time()                
        
        try:
        
            with concurrent.futures.ThreadPoolExecutor() as executor:
                tasks = [
                    executor.submit(task_func) for task_func in [                        
                        self.sync_pairs,  
                        self.sync_circulating,
                        self.sync_configuration,                              
                        self.sync_vara,
                        self.sync_supply,
                        self.sync_tokens,
                    ]
                ]
                for task in concurrent.futures.as_completed(tasks):
                    task.result()
            
            LOGGER.info("Total Syncing done in %s seconds.", time.time() - t0)
            reset_multicall_pool_executor()

        except Exception as e:
            LOGGER.error(f"Sync failed: {e}")
            LOGGER.error(traceback.format_exc())
            raise 
        finally:
            LOGGER.info(f"Sync completed in {time.time() - t0} seconds.")

        
    @staticmethod
    def sync_forever():
        sync_instance = Syncer()

        LOGGER.info("Syncing every %s seconds ...", SYNC_WAIT_SECONDS)
        LOGGER.info("Performing initial sync...")

        sync_instance.sync_tokens()        

        LOGGER.info("Initial sync finished...")


        while True:
            try:
                sync_instance.sync()
            except KeyboardInterrupt:
                LOGGER.info("Syncing stopped!")
                break
            except Exception as error:
                LOGGER.error(error)

            time.sleep(SYNC_WAIT_SECONDS)
            

syncer = Syncer()