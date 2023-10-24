# -*- coding: utf-8 -*-

from multicall import Call, Multicall
from walrus import FloatField, HashField, IntegerField, Model, TextField, BooleanField
from web3.constants import ADDRESS_ZERO

from app.misc import ModelUteis

from app.assets import Token
from app.settings import (
    CACHE,
    DEFAULT_TOKEN_ADDRESS,
    LOGGER,
    VOTER_ADDRESS,
    WRAPPED_BRIBE_FACTORY_ADDRESS,
)


class Gauge(Model):
    """Model representing a Gauge with functionalities to fetch and update data from the blockchain.

    The model provides methods to:
    - Fetch and validate token decimals.
    - Retrieve a gauge instance from cache or chain.
    - Fetch gauge data from the blockchain.
    - Update and rebase the APR for the gauge.
    - Fetch both internal and external rewards associated with the gauge.
    """

    __database__ = CACHE

    DEFAULT_DECIMALS = 18
    DAY_IN_SECONDS = 24 * 60 * 60
    CACHER = CACHE.cache()

    address = TextField(primary_key=True)
    decimals = IntegerField(default=DEFAULT_DECIMALS)
    total_supply = FloatField()
    bribe_address = TextField(index=True)
    fees_address = TextField(index=True)
    wrapped_bribe_address = TextField(index=True)
    reward = FloatField()
    rewards = HashField()
    tbv = FloatField(default=0.0)
    votes = FloatField(default=0.0)
    apr = FloatField(default=0.0)
    isAlive = BooleanField(default=False)
    

    # Backwards compatibility fields
    bribeAddress = TextField()
    feesAddress = TextField()
    totalSupply = FloatField()  

    @classmethod
    def find(cls, address):
        """Retrieve a gauge from cache or from the chain."""
        if not address:
            return None

        try:
            return cls.load(address.lower())
        except KeyError:
            return cls.from_chain(address.lower())

    @classmethod
    def from_chain(cls, address):
        """Fetch gauge data from the chain."""
        address = address.lower()

        try:
            data = Multicall(
                [
                    Call(
                        address,
                        "totalSupply()(uint256)",
                        [["total_supply", None]],
                    ),
                    Call(
                        address,
                        [
                            "rewardRate(address)(uint256)",
                            DEFAULT_TOKEN_ADDRESS,
                        ],
                        [["reward_rate", None]],
                    ),
                    Call(
                        VOTER_ADDRESS,
                        ["external_bribes(address)(address)", address],
                        [["bribe_address", None]],
                    ),
                    Call(
                        VOTER_ADDRESS,
                        ["internal_bribes(address)(address)", address],
                        [["fees_address", None]],
                    ),
                    Call(
                        VOTER_ADDRESS,
                        ["isAlive(address)(bool)", address],
                        [["isAlive", None]],
                    ),
                ]
            )()

            if not data.get("isAlive"):
                LOGGER.warning(
                    f"Gauge {address} is not Alive."
                )     
            
                        
            data["total_supply"] = data["total_supply"] / cls.DEFAULT_DECIMALS

            
            token = Token.find(DEFAULT_TOKEN_ADDRESS)

            if token is not None:



                if data.get("reward_rate") is not None:
                    data["reward"] = (
                        data["reward_rate"] / 10**token.decimals * cls.DAY_IN_SECONDS
                    )
                    data["reward"] = (
                        data["reward_rate"] / 10**token.decimals * cls.DAY_IN_SECONDS
                    )
                else:
                    LOGGER.warning(f"No reward rate data for address {address}")                
                    data["reward"] = 0                

                if data.get("bribe_address") in (ADDRESS_ZERO, None):
                    LOGGER.warning(f"No bribe address data for address {address}")
                    data["bribeAddress"] = ADDRESS_ZERO
                    data["feesAddress"] = 0
                    data["totalSupply"] = 0
                else:

                    data["bribeAddress"] = data["bribe_address"]
                    data["feesAddress"] = data["fees_address"]
                    data["totalSupply"] = data["total_supply"]

                    if data.get("bribe_address") not in (ADDRESS_ZERO, None):
                        data["wrapped_bribe_address"] = Call(
                            WRAPPED_BRIBE_FACTORY_ADDRESS,
                            ["oldBribeToNew(address)(address)", data["bribe_address"]],
                        )()
                    else:
                        data["wrapped_bribe_address"] = ADDRESS_ZERO

                    if data.get("wrapped_bribe_address") in (ADDRESS_ZERO, ""):
                        del data["wrapped_bribe_address"]
                    

                    cls.query_delete(cls.address == address.lower())

                    data["isAlive"] = data.get("isAlive")

                    gauge = cls.create(address=address, **data)

                    LOGGER.debug("Fetched %s:%s.", cls.__name__, address)

                    if data.get("wrapped_bribe_address") not in (ADDRESS_ZERO, None):
                        cls._fetch_external_rewards(gauge)


                    cls._fetch_internal_rewards(gauge)
                    cls._update_apr(gauge)

                    return gauge
            
            return None

        except Exception as e:
            LOGGER.error(
                "Error fetching gauge data from chain for address %s: %s",
                address,
                e,
            )
            return None

    @classmethod    
    def rebase_apr(cls):
        """Rebase the APR."""
        minter_address = Call(VOTER_ADDRESS, "minter()(address)")()
        weekly = Call(minter_address, "weekly_emission()(uint256)")()
        supply = Call(minter_address, "circulating_supply()(uint256)")()
        growth = Call(
            minter_address, ["calculate_growth(uint256)(uint256)", weekly]
        )()

        return ((growth * 52) / supply) * 100

    @classmethod
    def _update_apr(cls, gauge):
        """Update the APR for the gauge."""
        from app.pairs.model import Pair

        pair = Pair.get(Pair.gauge_address == gauge.address)
        votes = Call(
            VOTER_ADDRESS, ["weights(address)(uint256)", pair.address]
        )()

        token = Token.find(DEFAULT_TOKEN_ADDRESS)
        votes = votes / 10**token.decimals

        gauge.apr = cls.rebase_apr()
        if token.price and votes * token.price > 0:
            gauge.votes = votes
            gauge.apr += ((gauge.tbv * 52) / (votes * token.price)) * 100
            gauge.save()

    @classmethod
    def _fetch_external_rewards(cls, gauge):
        """Fetch external rewards for the gauge."""
        
        LOGGER.debug("Fetched %s:%s.", cls.__name__, gauge)

        tokens_len = Call(
            gauge.wrapped_bribe_address, "rewardsListLength()(uint256)"
        )()
        reward_calls = []

        for idx in range(tokens_len):
            bribe_token_address = Call(
                gauge.wrapped_bribe_address, ["rewards(uint256)(address)", idx]
            )()
            reward_calls.append(
                Call(   
                    gauge.wrapped_bribe_address,
                    ["left(address)(uint256)", bribe_token_address],
                    [[bribe_token_address, None]],
                )
            )

        rewards_data = Multicall(reward_calls)()

        for bribe_token_address, amount in rewards_data.items():

            bribe_token_address_str = bribe_token_address.decode('utf-8') if isinstance(bribe_token_address, bytes) else bribe_token_address            

            LOGGER.debug("Checking bribe token %s:%s.", cls.__name__, bribe_token_address_str)

            token = Token.find(bribe_token_address_str)

            if token is not None:
                
                LOGGER.debug("Bribe token found %s:%s.", cls.__name__, token.symbol)
            
                gauge.rewards[token.address] = amount / 10**token.decimals

                if token.price:
                    gauge.tbv += amount / 10**token.decimals * token.price         

        gauge.save()

    @classmethod
    def _fetch_internal_rewards(cls, gauge):
        """Fetch internal rewards for the gauge."""
        from app.pairs.model import Pair

        pair = Pair.get(Pair.gauge_address == gauge.address)
        fees_data = Multicall(
            [
                Call(
                    gauge.fees_address,
                    ["left(address)(uint256)", pair.token0_address],
                    [["fees0", None]],
                ),
                Call(
                    gauge.fees_address,
                    ["left(address)(uint256)", pair.token1_address],
                    [["fees1", None]],
                ),
            ]
        )()

        fees = [
            [pair.token0_address, fees_data["fees0"]],
            [pair.token1_address, fees_data["fees1"]],
        ]

        for token_address, fee in fees:

            token_address_str = token_address.decode('utf-8') if isinstance(token_address, bytes) else token_address            

            token = Token.find(token_address_str)

            if gauge.rewards.get(token_address):
                gauge.rewards[token_address] = float(
                    gauge.rewards[token_address]
                ) + (fee / 10**token.decimals)
            elif fee > 0:
                gauge.rewards[token_address] = fee / 10**token.decimals

            if token.price:
                gauge.tbv += fee / 10**token.decimals * token.price

        gauge.save()
