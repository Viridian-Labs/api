# -*- coding: utf-8 -*-

from datetime import timedelta

import falcon

from app.assets import Token
from app.settings import (
    CACHE,
    DEFAULT_TOKEN_ADDRESS,
    LOGGER,
    VIRI_CACHE_EXPIRATION,
)


class ViriPrice(object):
    """
    Handles the retrieval and caching of the Viri price.

    The class manages the caching and retrieval of the Viri price information.
    This endpoint provides a quick way to fetch the up-to-date
    Viri token price.
    """

    CACHE_KEY = "viri:json"
    CACHE_TIME = timedelta(minutes=5)

    @classmethod
    def sync(cls):
        cls.recache()

    @classmethod
    def recache(cls):
        """
        Updates and returns the Viri token price.

        This method fetches the fresh price of the Viri token from the database
        and caches it for quick retrieval in subsequent requests.
        """

        try:
            token = Token.find(DEFAULT_TOKEN_ADDRESS)

            if token:

                LOGGER.debug("Token: %s", token)
                LOGGER.debug("VIRI price: %s", token.price)

                CACHE.set(cls.CACHE_KEY, str(token.price))
                CACHE.expire(cls.CACHE_KEY, VIRI_CACHE_EXPIRATION)

                LOGGER.debug("Cache updated for %s.", cls.CACHE_KEY)
                return str(token.price)

        except AttributeError as e:
            LOGGER.error(
                "Error accessing token attributes: %s", e, exc_info=True
            )
            return None

        return "0"

    def on_get(self, req, resp):
        """
        Retrieves and returns the Viri token price.

        This method gets the Viri price from the cache. If the price isn't in
        the cache, it calls the recache() method to get fresh data.
        """
        viri_price = CACHE.get(self.CACHE_KEY) or ViriPrice.recache()

        if viri_price:
            resp.text = viri_price
            resp.status = falcon.HTTP_200
        else:
            LOGGER.warning("Viri price not found in cache!")
            resp.status = falcon.HTTP_204
