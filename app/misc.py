# -*- coding: utf-8 -*-

import datetime
import decimal
import json
import uuid


class ModelUteis():
    # TODO: Treat the special tokens
    # TODO: Treat not alive gauges

    zero_price_tokens = []
    not_alive_gauges = []

    @staticmethod
    def ensure_token_validity(token):
        if token.name is None:
            token.name = 'UNKNOWN'
        if token.symbol is None:
            token.symbol = 'UNKNOWN'
        if token.decimals is None:
            token.decimals = 18
        
        token.save()

    @staticmethod
    def add_zero_price_token(token):
        if not any(existing_token.address == token.address for existing_token in ModelUteis.zero_price_tokens):
            ModelUteis.zero_price_tokens.append(token)

    @staticmethod
    def get_zero_price_tokens():
        return ModelUteis.zero_price_tokens    

    @staticmethod
    def add_not_alive_gauge(gauge):                
        
        if not any(existing_token == gauge.address for existing_token in ModelUteis.not_alive_gauges):
            ModelUteis.not_alive_gauges.append(gauge)

    @staticmethod
    def get_not_alive_gauge():
        return ModelUteis.not_alive_gauges

    @staticmethod
    def validate_token(decimals):
        return decimals is not None and isinstance(decimals, int)


class JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for decimals."""

    
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        elif isinstance(obj, datetime.datetime):
            return obj.isoformat()
        elif isinstance(obj, datetime.date):
            return obj.isoformat()
        elif isinstance(obj, uuid.UUID):
            return obj.hex
       
        return json.JSONEncoder.default(self, obj)