# -*- coding: utf-8 -*-

import json
import falcon
from app.settings import CACHE, LOGGER, TOKEN_CACHE_EXPIRATION
from .model import Token
from app.misc import JSONEncoder


class Assets(object):
    """Handles our base/chain assets as a tokenlist"""

    CACHE_KEY = "assets:json"

    @classmethod
    def sync(cls):       
        Tokens = Token.from_tokenlists()

        serializable_tokens = [tok._data for tok in Tokens]

        CACHE.set("assets:json", json.dumps(dict(data=serializable_tokens)))
        CACHE.expire("assets:json", TOKEN_CACHE_EXPIRATION)
        

    @staticmethod
    def serialize():

        """
        Serializes the list of Assets objects 
        into a list of dictionaries.
        """

        pairs = []

        for pair in Token.all():
            data = pair._data                        
            pairs.append(data)

        return pairs       


    @classmethod
    def recache(cls):

        """
        Updates the cache with the serialized pairs data.
        """

        tokens = json.dumps(dict(data=cls.serialize()), cls=JSONEncoder)

        CACHE.set(cls.CACHE_KEY, tokens)
        LOGGER.debug("Cache updated for %s.", cls.CACHE_KEY)

        return tokens


    def on_get(self, req, resp):
        """Caches and returns our assets"""
        assets = CACHE.get(self.CACHE_KEY) 
        if assets:
            resp.status = falcon.HTTP_200
            resp.media = json.loads(assets)
        else:
            LOGGER.warning("Assets not found in cache!")
            resp.status = falcon.HTTP_204
