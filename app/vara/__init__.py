# -*- coding: utf-8 -*-

from datetime import timedelta

import falcon

from app.settings import (
    CACHE,
    DEFAULT_TOKEN_ADDRESS,
    LOGGER,
)

from app.assets import Token


class VaraPrice(object):
    """Handles supply info"""

    CACHE_KEY = "vara-price:string"
    CACHE_TIME = timedelta(minutes=5)

    @classmethod
    def recache(cls):

        token = Token.find(DEFAULT_TOKEN_ADDRESS)
        LOGGER.debug("Token: %s", token.symbol)
        LOGGER.debug("VARA price: %s", token.price)
        CACHE.setex(cls.CACHE_KEY, cls.CACHE_TIME, token.price)
        LOGGER.debug("Cache updated for %s.", cls.CACHE_KEY)

        return token

    def on_get(self, req, resp):
        """Caches and returns our supply info"""
        vara_price = CACHE.get(self.CACHE_KEY) or VaraPrice.recache()

        resp.text = vara_price
        resp.status = falcon.HTTP_200
