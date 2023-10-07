# -*- coding: utf-8 -*-

from datetime import timedelta

import falcon

from app.settings import (
    CACHE,
    DEFAULT_TOKEN_ADDRESS,
    LOGGER,
    VARA_CACHE_EXPIRATION
)

from app.assets import Token


class VaraPrice(object):
    """Handles supply info"""

    CACHE_KEY = "vara:json"
    CACHE_TIME = timedelta(minutes=5)

    @classmethod
    def recache(cls):
        """Updates the cache for Vara price."""
        token = Token.find(DEFAULT_TOKEN_ADDRESS)
        LOGGER.debug("Token: %s", token.symbol)
        LOGGER.debug("VARA price: %s", token.price)

        # Cache the token price as a string
        CACHE.set(cls.CACHE_KEY, str(token.price))
        CACHE.expire(cls.CACHE_KEY, VARA_CACHE_EXPIRATION)

        LOGGER.debug("Cache updated for %s.", cls.CACHE_KEY)

        return token.price

    def on_get(self, req, resp):
        """Caches and returns our supply info."""
        vara_price = CACHE.get(self.CACHE_KEY) or VaraPrice.recache()

        resp.text = vara_price
        resp.status = falcon.HTTP_200
