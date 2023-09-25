# -*- coding: utf-8 -*-

import time
from multiprocessing import Process
from multiprocessing.pool import ThreadPool

from app.assets import Assets, Token
from app.pairs import Pair, Pairs
from app.settings import (LOGGER, SYNC_WAIT_SECONDS,
                          reset_multicall_pool_executor)
from app.vara import VaraPrice


def sync():
    """Syncs """
    t0 = time.time()
    LOGGER.info("Syncing tokens ...")
    
    Token.from_tokenlists()

    t00 = time.time() - t0    

    t1 = time.time()
    LOGGER.info("Syncing pairs ...")

    with ThreadPool(4) as pool:
        addresses = Pair.chain_addresses()

        LOGGER.debug(
            "Syncing %s pairs using %s threads...", len(
                addresses), pool._processes
        )

        pool.map(Pair.from_chain, addresses)
        pool.close()
        pool.join()

    # Reset any cache...
    Pairs.recache()
    Assets.recache()
    VaraPrice.recache()

    LOGGER.info("Syncing tokens done in %s seconds.", t00)
    LOGGER.info("Syncing pairs done in %s seconds.", time.time() - t1)    
    LOGGER.info("Total Syncing done in %s seconds.", time.time() - t0)

    reset_multicall_pool_executor()


def sync_forever():
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
            sync_proc.close()
            del sync_proc

        time.sleep(SYNC_WAIT_SECONDS)


if __name__ == "__main__":
    if SYNC_WAIT_SECONDS < 1:
        sync()
    else:
        sync_forever()
