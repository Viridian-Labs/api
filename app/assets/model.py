import concurrent.futures
import json
import time
from statistics import mean, stdev
from typing import Dict, Union

import requests
from multicall import Call, Multicall
from walrus import BooleanField, FloatField, IntegerField, Model, TextField
from web3 import Web3, HTTPProvider
from web3.middleware import geth_poa_middleware
# from web3.auto import w3
from web3.exceptions import ContractLogicError

from app.misc import ModelUteis
from app.settings import (
    CACHE,
    DEFAULT_TOKEN_ADDRESS,
    EXTERNAL_PRICE_ORDER,
    FACTORY_ADDRESS,
    IGNORED_TOKEN_ADDRESSES,
    LOGGER,
    ROUTE_TOKEN_ADDRESSES,
    ROUTER_ADDRESS,
    STABLE_TOKEN_ADDRESS,
    TOKENLISTS,
)

DEXSCREENER_ENDPOINT = "https://api.dexscreener.com/latest/dex/tokens/"
DEFILLAMA_ENDPOINT = "https://coins.llama.fi/prices/current/"
# DEXGURU_ENDPOINT = "https://api.dev.dex.guru/v1/chain/10/tokens/%/market"
# DEBANK_ENDPOINT = "https://api.debank.com/history/token_price?chain=core&"

MAX_RETRIES = 0


class Token(Model):

    """
    The Token class represents a blockchain token and provides methods to fetch
    and update its price from various sources, both internal and external.
    It also provides class methods to fetch token data
    from the chain and from token lists.

    Attributes:
        address (TextField): The blockchain address of the token, primary key.
        name (TextField): The name of the token.
        symbol (TextField): The symbol representing the token.
        decimals (IntegerField): The number of decimal places the token uses.
        logoURI (TextField): The URI where the token's logo can be found.
        price (FloatField): The current price of the token.
        stable (BooleanField): Whether the token is stable.
        liquid_staked_address (TextField): Address of the original token.
        created_at (FloatField): The timestamp when the token was created.
        taxes (FloatField): The taxes associated with the token.
    """

    __database__ = CACHE
    address = TextField(primary_key=True)
    name = TextField()
    symbol = TextField()
    decimals = IntegerField()
    logoURI = TextField()
    price = FloatField(default=0)
    stable = BooleanField(default=False)
    liquid_staked_address = TextField()
    w3 = Web3(HTTPProvider('https://rpc.ankr.com/core'))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    created_at = FloatField(default=w3.eth.get_block("latest").timestamp)
    taxed = BooleanField(default=False)
    tax = FloatField(default=0)
    stable_route = BooleanField(default=False)
    price_control = TextField()

    DEXSCREENER_ENDPOINT = DEXSCREENER_ENDPOINT
    DEFILLAMA_ENDPOINT = DEFILLAMA_ENDPOINT
    # DEXGURU_ENDPOINT = DEXGURU_ENDPOINT
    # DEBANK_ENDPOINT = DEBANK_ENDPOINT

    def get_price_external_source(self):
        """
        Fetches the price of the token from external sources defined in
        EXTERNAL_PRICE_ORDER.

        It iterates over the external price getters and returns the price
        from the first successful fetch.

        Returns:
            float: The fetched price of the token from an external source,
            0 if all fetches fail.

        Raises:
            Exception: Any exception raised by the external price
            getter methods.
        """

        ModelUteis.ensure_token_validity(self)

        price_getters_mapping = {
            "_get_price_from_dexscreener": self._get_price_from_dexscreener,
            # "_get_price_from_debank": self._get_price_from_debank,
            "_get_price_from_defillama": self._get_price_from_defillama,
            # "_get_price_from_dexguru": self._get_price_from_dexguru,
        }

        for func_name in EXTERNAL_PRICE_ORDER:
            if func_name in price_getters_mapping:
                func = price_getters_mapping[func_name]
                try:
                    price = func()
                    if price > 0:
                        self.price = price
                        LOGGER.debug(
                            f"Price for {self.symbol} using {func_name}. "
                            f"Price {price}"
                        )
                        return price
                except Exception as e:
                    LOGGER.error(f"Error fetching price {func_name}: {e}")

        return 0

    def _get_direct_price(self, stablecoin):
        """
        Fetches the direct price of the token in terms of the provided
        stablecoin.

        Parameters:
            stablecoin (Token): The stablecoin against which the price of
            the token is to be fetched.

        Returns:
            float: The fetched price of the token, 0 if fetching fails.

        Raises:
            ContractLogicError: If there is an error in getting the chain
            price for the token.
        """

        try:
            LOGGER.debug("Token: %s", self.symbol)
            LOGGER.debug("Decimales: %s", self.decimals)
            LOGGER.debug("Address: %s", self.address)
            LOGGER.debug("Stablecoin Address: %s", self.address)

            amount, is_stable = Call(
                ROUTER_ADDRESS,
                [
                    "getAmountOut(uint256,address,address)(uint256,bool)",
                    1 * 10**self.decimals,
                    self.address,
                    stablecoin.address,
                ],
            )()

            LOGGER.debug("Amount result: %s", amount)

            return amount / 10**stablecoin.decimals * stablecoin.price
        except ContractLogicError:
            LOGGER.debug("Found error getting chain price for %s", self.symbol)
            return 0

    def get_pair(self, address):
        try:
            pair = Call(
                FACTORY_ADDRESS,
                [
                    "getPair(address,address,bool)(address)",
                    self.address,
                    address,
                    True,
                ],
                [],
            )()
            if pair == "0x0000000000000000000000000000000000000000":
                raise ContractLogicError
        except ContractLogicError:
            try:
                pair = Call(
                    FACTORY_ADDRESS,
                    [
                        "getPair(address,address,bool)(address)",
                        self.address,
                        address,
                        False,
                    ],
                    [],
                )()
                if pair == "0x0000000000000000000000000000000000000000":
                    raise ContractLogicError
            except ContractLogicError:
                return None
        return pair

    def chain_price_in_route_tokens_reserves(self):
        """Returns the price quoted from our router in stables/USDC."""
        # Peg it forever.
        if self.address == STABLE_TOKEN_ADDRESS:
            return 1.0

        # We search for all the pairs that have the token
        # as one of the pair tokens
        max_reserve_of_token = max_reserve_of_other_token = 0
        route_token_selected = "0x0000000"
        prices = []
        for token_address in ROUTE_TOKEN_ADDRESSES:
            pair = self.get_pair(token_address)

            if pair is None:
                continue

            token0 = Call(pair, "token0()(address)", [])()
            token1 = Call(pair, "token1()(address)", [])()
            reserve0, reserve1 = Call(
                pair, ["getReserves()(uint256,uint256)"], []
            )()
            LOGGER.debug(f"Reserves for pair {pair}: {reserve0}, {reserve1}")

            if token0 == self.address:
                # and reserve0 > max_reserve_of_token:
                max_reserve_of_token = reserve0 / 10**self.decimals
                other_token = Token.find(token1)
                if not other_token:
                    continue
                max_reserve_of_other_token = (
                    reserve1 / 10**other_token.decimals
                )
                route_token_selected = token1
            if token1 == self.address:
                # and reserve1 > max_reserve_of_token:
                max_reserve_of_token = reserve1 / 10**self.decimals
                other_token = Token.find(token0)
                if not other_token:
                    continue
                max_reserve_of_other_token = (
                    reserve0 / 10**other_token.decimals
                )
                route_token_selected = token0

            temp_price = (
                max_reserve_of_other_token
                / max_reserve_of_token
                * other_token.price
            )
            LOGGER.debug(
                f"Price for {self.symbol} and route token {other_token.symbol}"
                f":{temp_price}"
            )
            if temp_price > 0:
                prices.append(
                    {
                        "price": float(temp_price),
                        "reserve": max_reserve_of_token,
                    }
                )

        if route_token_selected == "0x0000000":
            return 0
        route_token = Token.find(route_token_selected)
        try:
            # * We filter the prices that are too far from the
            # * mean in terms of reserves
            # ! SPOILER: we don't do this anymore
            reserves_mean = mean([x["reserve"] for x in prices])

            # reserves_std = (
            #     stdev([x["reserve"] for x in prices])
            #     if len(prices) > 2
            #     else 0.9 * reserves_mean
            # )

            prices = [x for x in prices if x["reserve"] >= reserves_mean]
            prices_mean = mean([x["price"] for x in prices])
            LOGGER.debug(
                f"Prices for {self.symbol}: {[x['price'] for x in prices]}"
            )
            if len(prices) > 2:
                LOGGER.debug("Prices after filtering: %s", prices)
                # * We filter the prices that are too far
                # * from the mean in terms of prices
                prices_std = (
                    stdev([x["price"] for x in prices])
                    if len(prices) > 2
                    else 0.9 * prices_mean
                )
                final_prices = [
                    x["price"]
                    for x in prices
                    if abs(x["price"] - prices_mean) <= prices_std
                ]
                # * Getting the closest price to the mean
                min_diff = min([abs(x - prices_mean) for x in final_prices])
                final_price = [
                    x["price"]
                    for x in prices
                    if abs(x["price"] - prices_mean) == min_diff
                ][0]
            else:
                # min_diff = min([
                #   abs(x["price"] - prices_mean) for x in prices])
                # * Getting the greater price
                final_price = prices[1 if len(prices) > 1 else 0]["price"]
            LOGGER.debug(f"PRICE for {self.symbol}: {final_price}")
            return final_price

        except ContractLogicError:
            LOGGER.debug(
                f"Error getting amount out for {self.symbol}"
                f"and route token {route_token.symbol}"
            )
            return 0

    # ! Legacy function. We don't use this anymore,
    # ! here for reference
    def chain_price_in_route_tokens_router(self):
        # Peg it forever.
        if self.address == STABLE_TOKEN_ADDRESS:
            return 1.0
        for route_token in ROUTE_TOKEN_ADDRESSES:
            route_token = Token.find(route_token)
            if not route_token:
                continue
            if route_token.address == STABLE_TOKEN_ADDRESS:
                route_token.price = 1.0
            try:
                amount, is_stable = Call(
                    ROUTER_ADDRESS,
                    [
                        "getAmountOut(uint256,address,address)(uint256,bool)",
                        1 * 10 ** (self.decimals - 4),
                        self.address,
                        route_token.address,
                    ],
                )()
                # amount = Call(
                #     pair_selected,
                #     [
                #         'current(address,uint256)(uint256)',
                #         self.address,
                #         1 * 10**self.decimals
                #     ]
                # )()

                LOGGER.debug(
                    f"Amount out: {amount},"
                    f"route token decimals: {route_token.decimals},"
                    f"route token price: {route_token.price}"
                )
                if route_token.price > 0 and amount > 0:
                    return (
                        amount
                        * 10**4
                        / 10**route_token.decimals
                        * route_token.price
                    )
            except ContractLogicError:
                LOGGER.debug(
                    f"Error getting amount out for {self.symbol}"
                    f"and route token {route_token.symbol}"
                )
                return 0

    @classmethod
    def from_chain(cls, address, logoURI=None):
        """Fetches and returns a token from chain."""

        try:
            address = address.lower()
            LOGGER.debug("Fetching from chain %s:%s...", cls.__name__, address)

            token_multi = Multicall(
                [
                    Call(address, ["name()(string)"], [["name", None]]),
                    Call(address, ["symbol()(string)"], [["symbol", None]]),
                    Call(address, ["decimals()(uint8)"], [["decimals", None]]),
                ]
            )

            data = token_multi()

            # TODO: Add a dummy logo...
            token = cls.create(address=address, **data)
            # token._update_price()
            token._price_feed()

            LOGGER.debug("Fetched %s:%s.", cls.__name__, address)

            return token
        except Exception as e:
            LOGGER.error(f"Failed to fetch data for address {address}: {e}")
            return None

    def _get_price_from_dexscreener(self):
        try:
            res = requests.get(self.DEXSCREENER_ENDPOINT + self.address)

            res.raise_for_status()
            data = res.json()

            pairs = data.get("pairs")

            if pairs is None or not isinstance(pairs, list) or len(pairs) == 0:
                # LOGGER.warning("Unexpected struct in Dexscreener response:\
                # 'pairs' key missing, None, or not a non-empty list.")
                # LOGGER.debug(f"Dexscreener API Response: {data}")
                return 0
            pairs_in_core = [
                pair
                for pair in pairs
                if pair["chainId"] == "core"
                and pair["dexId"] == "viridian"
                and pair["quoteToken"]["address"].lower()
                != self.address.lower()
            ]

            if len(pairs_in_core) == 0:
                price = str(pairs[0].get("priceUsd") or 0).replace(",", "")
            else:
                price = str(pairs_in_core[0].get("priceUsd") or 0).replace(
                    ",", ""
                )

            return float(price)
        except (requests.RequestException, ValueError, IndexError) as e:
            LOGGER.error("Error fetching price from Dexscreener: %s", e)
            return 0

    def _get_price_from_defillama(self) -> float:
        url = self.DEFILLAMA_ENDPOINT + "core:" + self.address.lower()

        try:
            res = requests.get(url)
            res.raise_for_status()
            data = res.json()

            if "coins" not in data or not isinstance(data["coins"], dict):
                LOGGER.error(
                    f"Unexpected structure in DefiLlama response for token"
                    f"{self.address}: 'coins' key missing or"
                    f"not a dictionary."
                )
                return 0

            coins = data["coins"]
            for _, coin in coins.items():
                price = coin.get("price", 0)
                if price:
                    return price

            LOGGER.warning(
                f"No price found in DefiLlama for token: {self.symbol}"
            )
            return 0

        except (requests.RequestException, ValueError) as e:
            LOGGER.error(
                f"Error fetching price from DefiLlama for token"
                f"{self.address} using URL {url}: {e}"
            )
            return 0

    # def _get_price_from_debank(self):
    #     try:
    #         res = requests.get(
    #             self.DEBANK_ENDPOINT + "token_id=" + self.address.lower()
    #         )

    #         res.raise_for_status()
    #         token_data = res.json().get("data") or {}

    #         return token_data.get("price") or 0
    #     except (requests.RequestException, ValueError) as e:
    #         LOGGER.error("Error fetching price from DeBank: %s", e)
    #         return 0

    # def _get_price_from_dexguru(self):
    #     try:
    #         res = requests.get(self.DEXGURU_ENDPOINT % self.address.lower())
    #         res.raise_for_status()
    #         return res.json().get("price_usd", 0)
    #     except (requests.RequestException, ValueError) as e:
    #         LOGGER.error("Error fetching price from DexGuru: %s", e)
    #         return 0

    @classmethod
    def find(cls, address):
        if not address:
            LOGGER.error("Address is None. Unable to fetch %s.", cls.__name__)
            return None

        try:
            address_str = (
                address.decode("utf-8")
                if isinstance(address, bytes)
                else address
            )
            return (
                cls.load(address_str.address.lower())
                if hasattr(address_str, "address")
                else cls.load(address_str.lower())
            )
        except KeyError:
            LOGGER.info(
                f"Key {address_str} not found in cache. Fetching from chain..."
            )
            return (
                cls.from_chain(address_str.address.lower())
                if hasattr(address_str, "address")
                else cls.from_chain(address_str.lower())
            )

    @classmethod
    def from_tokenlists(cls):
        w3 = Web3(HTTPProvider('https://rpc.ankr.com/core'))
        w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        our_chain_id = w3.eth.chain_id
        all_tokens = cls._fetch_all_tokens(our_chain_id)

        return all_tokens

    @classmethod
    def _fetch_all_tokens(cls, our_chain_id):
        """Fetches all tokens from the token lists."""

        all_tokens = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(cls._fetch_tokenlist, tlist, our_chain_id)
                for tlist in TOKENLISTS
            ]
            for future in concurrent.futures.as_completed(futures):
                try:
                    all_tokens.extend(future.result())
                except Exception as exc:
                    LOGGER.error("Generated an exception: %s", exc)

        return all_tokens

    @classmethod
    def _fetch_tokenlist(cls, tlist, our_chain_id):
        """Fetches tokens from a specific token list."""

        tokens = []

        try:
            headers = {"Cache-Control": "no-cache"}
            res = requests.get(tlist, headers=headers).json()

            for token_data in res.get("tokens", []):
                if cls._is_valid_token(token_data, our_chain_id):
                    token = cls._create_and_update_token(token_data)
                    tokens.append(token)
                else:
                    LOGGER.debug(
                        "Ignoring token %s from tokenlist %s",
                        token_data.get("address"),
                        tlist,
                    )
        except (requests.RequestException, json.JSONDecodeError) as error:
            LOGGER.error("Error loading token list %s: %s", tlist, error)
        return tokens

    @staticmethod
    def _is_valid_token(
        token_data: Dict[str, Union[str, int]], our_chain_id: int
    ) -> bool:
        address = token_data.get("address", "").lower()

        return (
            token_data.get("chainId") == our_chain_id
            and address not in IGNORED_TOKEN_ADDRESSES
            and address
        )

    @classmethod
    def _create_and_update_token(
        cls, token_data: Dict[str, Union[str, int]]
    ) -> "Token":
        """Creates and updates the token."""

        address = token_data.get("address", "").lower()
        liquid_staked_address = token_data.get(
            "liquid_staked_address", ""
        ).lower()
        symbol = token_data.get("symbol", "")
        tags = token_data.get("tags", [""])
        token = cls.create(
            address=address,
            liquid_staked_address=liquid_staked_address,
            symbol=symbol,
        )

        token.name = token_data.get("name", "")
        token.logoURI = token_data.get("logoURI", "")
        token.stable = True if "stablecoin" in tags[0] else False
        token.taxed = (
            True
            if len(tags) > 1
            and isinstance(tags[1], str)
            and "taxed" in tags[1]
            else False
        )
        token.tax = token_data.get("tax", False)
        token.price_control = token_data.get("price_control", "").lower()
        token.stable_route = token_data.get("stable_route", False)
        token.decimals = token_data.get("decimals", 18)

        # token._update_price()
        token._price_feed()

        return token

    def to_dict(self):
        return {
            "address": self.address,
            "name": self.name,
            "symbol": self.symbol,
            "decimals": self.decimals,
            "logoURI": self.logoURI,
            "price": self.price,
            "stable": self.stable,
            "liquid_staked_address": self.liquid_staked_address,
            "created_at": self.created_at,
            "taxed": self.taxed,
            "tax": self.tax,
        }

    def _price_feed(self):
        """
        Returns the price feed of the token.
        Based on different sources as:
            - Direct routing to some token
            - Direct routing to stablecoin
            - Algo based on the reserves of the token
                in the liquidity pools
            - External sources
        """
        start_time = time.time()
        ModelUteis.ensure_token_validity(self)
        price = 0
        try:
            # ! EXCEPTIONS - These are configured manually from the
            # ! tokenlist file IGNORED TOKENS, OPTION TOKEN...
            if self.address in IGNORED_TOKEN_ADDRESSES:
                LOGGER.error(
                    "Token %s is in the ignored list. Skipping update.",
                    self.symbol,
                )
                return self._finalize_update(0, start_time)

            if self.price_control != "":
                price = self._get_direct_price(Token.find(self.price_control))

            if self.stable_route:
                price = self._get_direct_price(
                    Token.find(STABLE_TOKEN_ADDRESS)
                )

            # * GENERAL CASE - Automatically calculated from the route
            # * tokens/reserves of liquidity pools
            if price <= 0:
                price = self.chain_price_in_route_tokens_reserves()
            if price <= 0:
                price = self.get_price_external_source()
            if price > 0:
                return self._finalize_update(price, start_time)
            return self._finalize_update(0, start_time)
        except Exception as e:
            LOGGER.error(f"Error fetching price: {e}")
            return self._finalize_update(0, start_time)

    def _finalize_update(self, price, start_time):
        """Finalizes the update by setting the price and saving the token."""

        self.price = price
        LOGGER.debug(
            f"Token {self.symbol}:"
            f"{self.price_control},"
            f"{self.stable_route},"
            f"{self.liquid_staked_address}"
        )
        self.save()
        elapsed_time = time.time() - start_time
        LOGGER.info(
            "Updated price of %s - %s - Time taken: %s seconds",
            self.symbol,
            self.price,
            elapsed_time,
        )
        return self.price
