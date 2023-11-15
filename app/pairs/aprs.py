from app.settings import CACHE, LOGGER, NATIVE_TOKEN_ADDRESS


def get_apr():
    aprs = CACHE.get("aprs:json")
    return aprs
