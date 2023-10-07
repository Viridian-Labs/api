# -*- coding: utf-8 -*-

import json

import falcon

from app.settings import CACHE, LOGGER, TOKEN_CACHE_EXPIRATION

from .model import Token


class Assets(object):
    """Handles our base/chain assets as a tokenlist"""

    CACHE_KEY = "assets:json"

    @classmethod
    def recache(cls):
        tokens = [tok._data for tok in Token.all() if tok.logoURI is not None]
        assets = json.dumps(dict(data=tokens))

        CACHE.set(cls.CACHE_KEY, assets)
        CACHE.expire(cls.CACHE_KEY, TOKEN_CACHE_EXPIRATION)

        LOGGER.debug("Cache updated for %s.", cls.CACHE_KEY)
        return assets


    def on_get(self, req, resp):
        """Caches and returns our assets"""
        assets = CACHE.get(self.CACHE_KEY) or Assets.recache()

        resp.status = falcon.HTTP_200
        resp.text = assets
