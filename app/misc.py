# -*- coding: utf-8 -*-

import datetime
import decimal
import json
import uuid

class ModelUteis:
    """
    A utility class providing static methods related to tokens and gauges.
    """

    # Class level sets to store addresses of zero-price tokens and not-alive gauges.
    zero_price_token_addresses = set()
    not_alive_gauge_addresses = set()

    # Class level lists to store actual token and gauge objects.
    zero_price_tokens = []
    not_alive_gauges = []

    @staticmethod
    def ensure_token_validity(token):
        """
        Ensure the validity of a token by setting default values for missing attributes.

        :param token: Token object to validate.
        """
        if token.name is None:
            token.name = 'UNKNOWN'
        if token.symbol is None:
            token.symbol = 'UNKNOWN'
        if token.decimals is None:
            token.decimals = 18

        token.save()    
   

    @staticmethod
    def validate_token(decimals):
        """
        Validate token based on its decimals.

        :param decimals: Number of decimals the token has.
        :return: Boolean indicating the validity of the token.
        """
        return decimals is not None and isinstance(decimals, int)


class JSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder that handles special data types like decimals, datetimes, and UUIDs.
    """

    def default(self, obj):
        """
        Override the default method to provide custom serialization for special types.

        :param obj: Object to be serialized.
        :return: Serialized form of the object.
        """
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        elif isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        elif isinstance(obj, uuid.UUID):
            return obj.hex
       
        return super(JSONEncoder, self).default(obj)


