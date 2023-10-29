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
    def add_zero_price_token(token):
        """
        Add a token to the zero_price_tokens list if it's not already present.

        :param token: Token object with zero price.
        """
        if token.address not in ModelUteis.zero_price_token_addresses:
            ModelUteis.zero_price_token_addresses.add(token.address)
            ModelUteis.zero_price_tokens.append(token)

    @staticmethod
    def get_zero_price_tokens():
        """
        Return the list of zero price tokens.

        :return: List of zero price tokens.
        """
        return ModelUteis.zero_price_tokens

    @staticmethod
    def add_not_alive_gauge(gauge):
        """
        Add a gauge to the not_alive_gauges list if it's not already present.

        :param gauge: Gauge object which is not alive.
        """
        if gauge.address not in ModelUteis.not_alive_gauge_addresses:
            ModelUteis.not_alive_gauge_addresses.add(gauge.address)
            ModelUteis.not_alive_gauges.append(gauge)

    @staticmethod
    def get_not_alive_gauge():
        """
        Return the list of gauges which are not alive.

        :return: List of not-alive gauges.
        """
        return ModelUteis.not_alive_gauges

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


