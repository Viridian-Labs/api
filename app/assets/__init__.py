# -*- coding: utf-8 -*-

import json

import falcon

from app.settings import CACHE, LOGGER, TOKEN_CACHE_EXPIRATION

from .model import Token


class Assets(object):
    """Handles our base/chain assets as a tokenlist"""

    CACHE_KEY = "assets:json"

    @classmethod
    def sync(cls):       
        Tokens = Token.from_tokenlists()

        serializable_tokens = [tok._data for tok in Tokens]

        CACHE.set("assets:json", json.dumps(dict(data=serializable_tokens)))
        CACHE.expire("assets:json", TOKEN_CACHE_EXPIRATION)


    def on_get(self, req, resp):
        """Caches and returns our assets"""
        assets = CACHE.get(self.CACHE_KEY) 
        if assets:
            resp.status = falcon.HTTP_200
            resp.media = json.loads(assets)
        else:
            LOGGER.warning("Assets not found in cache!")
            resp.status = falcon.HTTP_204
