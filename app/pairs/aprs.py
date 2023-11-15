from app.settings import CACHE

def get_apr():
    aprs = CACHE.get("aprs:json")
    return aprs
