import concurrent.futures
import json
import time
from typing import Dict, Union

import requests
from multicall import Call, Multicall
from walrus import BooleanField, FloatField, IntegerField, Model, TextField
from web3.auto import w3
from web3.exceptions import ContractLogicError

from app.misc import ModelUteis
from app.settings import (
    AXELAR_BLUECHIPS_ADDRESSES,
    BLUECHIP_TOKEN_ADDRESSES,
    CACHE,
    EXTERNAL_PRICE_ORDER,
    GET_PRICE_INTERNAL_FIRST,
    IGNORED_TOKEN_ADDRESSES,
    INTERNAL_PRICE_ORDER,
    LOGGER,
    NATIVE_TOKEN_ADDRESS,
    RETRY_DELAY,
    ROUTE_TOKEN_ADDRESSES,
    ROUTER_ADDRESS,
    STABLE_TOKEN_ADDRESS,
    TOKENLISTS,
    DEFAULT_TOKEN_ADDRESS
)

DEXSCREENER_ENDPOINT = "https://api.dexscreener.com/latest/dex/tokens/"
DEFILLAMA_ENDPOINT = "https://coins.llama.fi/prices/current/"
DEXGURU_ENDPOINT = "https://api.dev.dex.guru/v1/chain/10/tokens/%/market"
DEBANK_ENDPOINT = "https://api.debank.com/history/token_price?chain=op&"

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
    created_at = FloatField(default=w3.eth.get_block("latest").timestamp)
    taxed = BooleanField(default=False)
    tax = FloatField(default=0)
    price_control = TextField()
    

    DEXSCREENER_ENDPOINT = DEXSCREENER_ENDPOINT
    DEFILLAMA_ENDPOINT = DEFILLAMA_ENDPOINT
    DEXGURU_ENDPOINT = DEXGURU_ENDPOINT
    DEBANK_ENDPOINT = DEBANK_ENDPOINT

    ROUTE_CONFIGURATIONS = [
        {
            "route_type": "direct", 
            "method": "_get_direct_price"
        },
        {
            "route_type": "axelar_bluechips",
            "method": "_get_price_through_tokens",
            "token_addresses": AXELAR_BLUECHIPS_ADDRESSES,
        },
        {
            "route_type": "axelar_bluechips",
            "method": "_get_price_through_tokens",
            "token_addresses": AXELAR_BLUECHIPS_ADDRESSES,
        },
        {
            "route_type": "bluechip_tokens",
            "method": "_get_price_through_tokens",
            "token_addresses": BLUECHIP_TOKEN_ADDRESSES,
        },
        {
            "route_type": "native_token",
            "method": "_get_price_through_tokens",
            "token_addresses": [NATIVE_TOKEN_ADDRESS],
        },
        {
            "route_type": "stable_token",
            "method": "_get_price_through_tokens",
            "token_addresses": [STABLE_TOKEN_ADDRESS],
        },
        {
            "route_type": "route_token",
            "method": "_get_price_through_tokens",
            "token_addresses": ROUTE_TOKEN_ADDRESSES,
        },
        {
            "route_type": "chain_price_in_pairs",
            "method": "chain_price_in_pairs"
        },
        {
            "route_type": "chain_price_in_liquid_staked",
            "method": "chain_price_in_liquid_staked"
        },
        {
            "route_type": "chain_price_in_stables_and_default_token",
            "method": "chain_price_in_stables_and_default_token"
        },
        {
            "route_type": "_get_price_from_defillama",
            "method": "_get_price_from_defillama"
        },
        {
            "route_type": "_get_price_from_dexscreener",
            "method": "_get_price_from_dexscreener"
        },
    ]            

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
            "_get_price_from_debank": self._get_price_from_debank,
            "_get_price_from_defillama": self._get_price_from_defillama,
            "_get_price_from_dexguru": self._get_price_from_dexguru,
        }

        for func_name in EXTERNAL_PRICE_ORDER:
            if func_name in price_getters_mapping:
                func = price_getters_mapping[func_name]
                try:
                    price = func()
                    if price > 0:
                        self.price = price
                        LOGGER.debug(f'Price for {self.symbol} fetched using {func_name}. Price {price}')
                        return price
                except Exception as e:
                    LOGGER.error(
                        f"Error fetching price using {func_name}: {e}"
                    )

        return 0

    def get_price_internal_source(self):
        """
        Fetches the price of the token from internal sources defined in
        INTERNAL_PRICE_ORDER.

        It iterates over the internal price getters and returns the price
        from the first successful fetch.

        Returns:
            float: The fetched price of the token from an internal source,
            0 if all fetches fail.

        Raises:
            Exception: Any exception raised by the internal price
            getter methods.
        """

        stablecoin = Token.find(STABLE_TOKEN_ADDRESS)

        if not stablecoin:
            LOGGER.error("No stable coin found")
            return 0

        for route_config in self.ROUTE_CONFIGURATIONS:
            route_type = route_config["route_type"]
            if route_type in INTERNAL_PRICE_ORDER:
                method_name = route_config["method"]
                method = getattr(self, method_name)
                try:                    
                    if "token_addresses" in route_config:
                        price = method(route_config["token_addresses"], stablecoin)
                    elif method_name == "_get_direct_price":
                        price = method(stablecoin)
                    else:
                        price = method()

                    if price > 0:
                        self.price = price
                        return price

                    time.sleep(RETRY_DELAY)
                except Exception as e:
                    LOGGER.error(f"Error fetching price using {route_type}: {e}")

            else:
                LOGGER.error(f"Invalid route_type {route_type}")
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
            amount, is_stable = Call(
                ROUTER_ADDRESS,
                [
                    "getAmountOut(uint256,address,address)(uint256,bool)",
                    1 * 10 ** self.decimals,
                    self.address,
                    stablecoin.address,
                ],
            )()
            return amount / 10 ** stablecoin.decimals
        except ContractLogicError:
            LOGGER.debug("Found error getting chain price for %s", self.symbol)
            return 0

    def _get_price_through_tokens(self, token_addresses, stablecoin):
        token_addresses = [address for address in token_addresses if address]

        if not isinstance(token_addresses, list):
            LOGGER.error("Invalid token_addresses type. Expected list.")
            return 0

        total_price = 0

        for token_address in token_addresses:
            if (
                not token_address
                or not token_address.startswith("0x")
                or len(token_address) != 42
            ):
                LOGGER.error(f"Invalid Ethereum address: {token_address}")
                continue

            try:
                amountB = self._retry_get_amount_out(
                    token_address, stablecoin.address, stablecoin.decimals
                )

                if isinstance(amountB, int) and amountB > 0:
                    total_price += amountB / 10 ** stablecoin.decimals

            except ContractLogicError as e:
                LOGGER.error(
                    f"Price not found for token address: {token_address}: {e}"
                )
            except Exception as e:
                LOGGER.error(
                    f"Error getting amount out for {token_address}: {e}"
                )

        return total_price

    def _retry_get_amount_out(
        self, token_address, target_address, target_decimals
    ):
        for i in range(MAX_RETRIES):
            try:
                result = Call(
                    ROUTER_ADDRESS,
                    [
                        "getAmountOut(uint256,address,address)(uint256,bool)",
                        1 * 10 ** self.decimals,
                        self.address,
                        token_address,
                    ],
                )()

                if not isinstance(result, tuple):
                    LOGGER.error(
                        f"Unexpected result type for {token_address}    "
                    )
                    continue

                amount, _ = result

                result = Call(
                    ROUTER_ADDRESS,
                    [
                        "getAmountOut(uint256,address,address)(uint256,bool)",
                        amount,
                        token_address,
                        target_address,
                    ],
                )()

                if not isinstance(result, tuple):
                    LOGGER.error(f"Unexpected result type for {token_address}")
                    continue

                amount, _ = result

                return amount

            except ContractLogicError:
                LOGGER.error(
                    f"Price not found for token address: {token_address}"
                )
            except Exception as e:
                LOGGER.error(
                    f"Error getting amount out for {token_address}: {e}"
                )

            if i < MAX_RETRIES - 1:
                LOGGER.warning(
                    f"Retrying request after error for {token_address}"
                )
                time.sleep(RETRY_DELAY)
            else:
                LOGGER.error(f"Unable to fetch data for {token_address}")
                return 0
    
    def chain_price_in_bluechips(self):
        """Returns the price quoted from our router in stables/USDC
        passing through a bluechip route"""
        # Peg it forever.
        if self.address == STABLE_TOKEN_ADDRESS:
            return 1.0
        # LOGGER.debug("Chain price Bluechips for %s", self.symbol)
        stablecoin = Token.find(STABLE_TOKEN_ADDRESS)
        for b in BLUECHIP_TOKEN_ADDRESSES:
            try:
                bluechip = Token.find(b)
                amountA, is_stable = Call(
                    ROUTER_ADDRESS,
                    [
                        "getAmountOut(uint256,address,address)(uint256,bool)",
                        1 * 10 ** self.decimals,
                        self.address,
                        bluechip.address,
                    ],
                )()
                amountB, is_stable = Call(
                    ROUTER_ADDRESS,
                    [
                        "getAmountOut(uint256,address,address)(uint256,bool)",
                        amountA,
                        bluechip.address,
                        stablecoin.address,
                    ],
                )()
                if amountB > 0:
                    return amountB / 10 ** stablecoin.decimals
            except ContractLogicError:
                return 0

        return 0

    def chain_price_in_liquid_staked(self):
        """Returns the price quoted from our router in stables/USDC
        passing through a liquid staked route"""
        # Peg it forever.
        if self.address == STABLE_TOKEN_ADDRESS:
            return 1.0

        LOGGER.debug("Chain price Liquid Staked for %s", self.symbol)
        stablecoin = Token.find(STABLE_TOKEN_ADDRESS)

        try:
            liquid = Token.find(self.liquid_staked_address)

            if not liquid:
                return 0
            amountA, is_stable = Call(
                ROUTER_ADDRESS,
                [
                    "getAmountOut(uint256,address,address)(uint256,bool)",
                    1 * 10 ** self.decimals,
                    self.address,
                    liquid.address,
                ],
            )()
            amountB, is_stable = Call(
                ROUTER_ADDRESS,
                [
                    "getAmountOut(uint256,address,address)(uint256,bool)",
                    amountA,
                    liquid.address,
                    stablecoin.address,
                ],
            )()
        except ContractLogicError:
            return 0

        return amountB / 10 ** stablecoin.decimals

    def temporary_price_in_bluechips(self):
        mToken = Token.find(self.liquid_staked_address)
        if not mToken:
            return 0
        return mToken.price

    def chain_price_in_pairs(self):
        try:
            pairs_data = requests.get(
                "https://api.equilibrefinance.com/api/v1/pairs"
            ).json()["data"]
        except Exception as e:
            LOGGER.error(f"Failed to fetch pair data: {e}")
            return None
        
        relevant_pairs = [
                p for p in pairs_data
                if self.address in [p["token0"]["address"], p["token1"]["address"]]
            ]
            
        price = self._calculate_price_from_pairs(relevant_pairs)
            

        LOGGER.info(f"Saving price for token {self.symbol}: {price}")
        return price

    def _calculate_price_from_pairs(self, pairs):
        for pair in pairs:
            token0 = pair["token0"]
            token1 = pair["token1"]

            if token0["address"] == self.address:
                other_token = token1
            elif token1["address"] == self.address:
                other_token = token0
            else:
                continue

            price = self._get_direct_price(Token.find(other_token["address"]))
            if price > 0:
                return price
        return 0

    def _calculate_price_from_pairs(self, pairs):
        for pair in pairs:
            token0 = pair["token0"]
            token1 = pair["token1"]

            if token0["address"] == self.address:
                other_token = token1
            elif token1["address"] == self.address:
                other_token = token0
            else:
                continue

            price = self._get_direct_price(Token.find(other_token["address"]))
            if price > 0:
                return price
        return 0

    def chain_price_in_stables_and_default_token(self):        
        """Returns the price quoted from our router in stables/USDC
        passing through default token route or some special cases"""
        
        LOGGER.debug("chain_price_in_stables_and_default_token price for %s", self.symbol)


        # Peg it forever.
        if self.address == STABLE_TOKEN_ADDRESS:
            return 1.0
        
        LOGGER.debug("Chain price NEW for %s", self.symbol)
        stablecoin = Token.find(STABLE_TOKEN_ADDRESS)
        
      
        nativecoin = Token.find(NATIVE_TOKEN_ADDRESS)
        default_token = Token.find(DEFAULT_TOKEN_ADDRESS)
        
        for token_address in ROUTE_TOKEN_ADDRESSES:
            token = Token.find(token_address)
            
            if (
                self.symbol in ["CHAM", "GMD", "multiETH", "multiWBTC", "TV", "BIFI"]            
            ):
                stablecoin = Token.find("0xc86c7c0efbd6a49b35e8714c5f59d99de09a225b") # wKAVA
           
            if (
                self.symbol in ["multiUSDT"]            
            ):
                stablecoin = Token.find("0xe1da44c0da55b075ae8e2e4b6986adc76ac77d73") # VARA 
                
                         
            LOGGER.debug("%s CALC THROUGH for %s", self.symbol, stablecoin.symbol)
            try:
                amountA, is_stable = Call(
                    ROUTER_ADDRESS,
                    [
                        "getAmountOut(uint256,address,address)(uint256,bool)",
                        1 * 10**self.decimals,
                        self.address,
                        token_address,
                    ],
                )()
                LOGGER.debug("AmountA for %s: %s", token.symbol, amountA)

                amountB, _ = Call(
                    ROUTER_ADDRESS,
                    [
                        "getAmountOut(uint256,address,address)(uint256,bool)",
                        amountA,
                        token_address,
                        stablecoin.address,
                    ],
                )()
                LOGGER.debug("AmountB for %s: %s", token.symbol, amountB)            
                
                if (
                    self.symbol in ["CHAM", "GMD", "multiETH", "multiWBTC", "TV", "BIFI", "multiUSDT"]                    
                ):                    
                                        
                    if amountB is not None and amountB > 0:
                        return amountB / 10**stablecoin.decimals
                                                                                        
                    
                if token_address in [
                    "0xE3F5a90F9cb311505cd691a46596599aA1A0AD7D".lower(),
                    "0x818ec0A7Fe18Ff94269904fCED6AE3DaE6d6dC0b".lower(),
                ]:                    
                    amountB, _ = Call(
                        ROUTER_ADDRESS,
                        [
                            "getAmountOut(uint256,address,address)"
                            + "(uint256,bool)",
                            amountA,
                            token_address,
                            nativecoin.address,
                        ],
                    )()
                    amountC, _ = Call(
                        ROUTER_ADDRESS,
                        [
                            "getAmountOut(uint256,address,address)"
                            + "(uint256,bool)",
                            amountB,
                            nativecoin.address,
                            stablecoin.address,
                        ],
                    )()

                    if amountC is not None and amountC > 0:
                        return amountC / 10**stablecoin.decimals
                                               
                                                
                if (
                    self.symbol in ["ACS", "BNB"]
                    and token_address == default_token.address
                ):
                    continue
                if self.symbol in ["DEXI"] and token.symbol == "multiUSDC":
                    LOGGER.debug("DEXI especial case through LION")
                    lion = Token.find(
                        "0x990e157fC8a492c28F5B50022F000183131b9026"
                    )
                    amountA, _ = Call(
                        ROUTER_ADDRESS,
                        [
                            "getAmountOut(uint256,address,address)"
                            + "(uint256,bool)",
                            1 * 10**self.decimals,
                            self.address,
                            lion.address,
                        ],
                    )()
                    amountB, _ = Call(
                        ROUTER_ADDRESS,
                        [
                            "getAmountOut(uint256,address,address)"
                            + "(uint256,bool)",
                            amountA,
                            lion.address,
                            token.address,
                        ],
                    )()
                    amountC, _ = Call(
                        ROUTER_ADDRESS,
                        [
                            "getAmountOut(uint256,address,address)"
                            + "(uint256,bool)",
                            amountB,
                            token.address,
                            stablecoin.address,
                        ],
                    )()

                    if amountC is not None and amountC > 0:
                        print("DEXI especial case through LION")
                        return amountC / 10**stablecoin.decimals
                if amountB is not None and amountB > 0:
                    return amountB / 10**stablecoin.decimals
                # Special case for TVestige and UMBRA (calc from wKAVA)
                if token_address == nativecoin.address and self.symbol in [
                    "TV",
                    "UMBRA",
                ]:
                    amountA = amountA / 10**nativecoin.decimals
                    return amountA * nativecoin.price
            except ContractLogicError:
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
            token._update_price()

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
            pairs_in_kava = [
                pair
                for pair in pairs
                if pair["chainId"] == "kava"
                and pair["dexId"] == "equilibre"
                and pair["quoteToken"]["address"].lower()
                != self.address.lower()
            ]
            #LOGGER.debug(f"Pairs in Kava: {pairs_in_kava}")
            
            
            if len(pairs_in_kava) == 0:
                price = str(pairs[0].get("priceUsd") or 0).replace(",", "")
            else:
                price = str(pairs_in_kava[0].get("priceUsd") or 0).replace(",", "")
            
            return float(price)
        except (requests.RequestException, ValueError, IndexError) as e:
            LOGGER.error("Error fetching price from Dexscreener: %s", e)
            return 0

    def _get_price_from_defillama(self) -> float:
        
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        
        url = self.DEFILLAMA_ENDPOINT + "kava:" + self.address.lower()
        print(url)
        
        try:
            res = requests.get(url)
            res.raise_for_status()
            data = res.json()

            if "coins" not in data or not isinstance(data["coins"], dict):
                LOGGER.error(
                    f"Unexpected structure in DefiLlama response for token \
                        {self.address}: 'coins' key missing or \
                            not a dictionary."
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
                f"Error fetching price from DefiLlama for token \
                    {self.address} using URL {url}: {e}"
            )
            return 0

    def _get_price_from_debank(self):
        try:
            res = requests.get(
                self.DEBANK_ENDPOINT + "token_id=" + self.address.lower()
            )

            res.raise_for_status()
            token_data = res.json().get("data") or {}

            return token_data.get("price") or 0
        except (requests.RequestException, ValueError) as e:
            LOGGER.error("Error fetching price from DeBank: %s", e)
            return 0

    def _get_price_from_dexguru(self):
        try:
            res = requests.get(self.DEXGURU_ENDPOINT % self.address.lower())
            res.raise_for_status()
            return res.json().get("price_usd", 0)
        except (requests.RequestException, ValueError) as e:
            LOGGER.error("Error fetching price from DexGuru: %s", e)
            return 0    

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
            headers = {'Cache-Control': 'no-cache'}
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
        token.price_control = token_data.get("price_control", "")
        token.decimals = token_data.get("decimals", 18)
        

        token._update_price()
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
        
    def _update_price(self):
        start_time = time.time()
        ModelUteis.ensure_token_validity(self)

        if self.address in IGNORED_TOKEN_ADDRESSES:
            LOGGER.error(
                "Token %s is in the ignored list. Skipping update.",
                self.symbol,
            )
            return self._finalize_update(0, start_time)        

        if self.price_control:
            LOGGER.info(
                "Token %s has price_control. Fetching price using %s",
                self.symbol,
                self.price_control,
            )
            
            print('1')
            
            stablecoin = Token.find(STABLE_TOKEN_ADDRESS)
            
            print('2')
            
            if not stablecoin:
                
                print('3')
                LOGGER.error("No stable coin found")
                return 0
            
            print('4')
            for route_config in self.ROUTE_CONFIGURATIONS:
                print('5')
                route_type = route_config["route_type"]
                print('6', route_type)
                            
                if self.price_control == route_type:
                    method_name = route_config["method"]
                    print('7', method_name)
                    method = getattr(self, method_name)

                    try:
                        if "token_addresses" in route_config:
                            print('8')  
                            price_control_price = method(route_config["token_addresses"], stablecoin)
                            print('9')
                        else:
                            print('10')
                            price_control_price = method()  
                            print('11')

                        if price_control_price > 0:
                            print('12')
                            return self._finalize_update(price_control_price, start_time)
                                                                
                    except Exception as e:
                        LOGGER.error(f"Error fetching price using {route_type}: {e}")
                                                                
            
        print('13')
        
        # Price from blue chip addresses
        if self.address in AXELAR_BLUECHIPS_ADDRESSES + BLUECHIP_TOKEN_ADDRESSES:
            external_price = self.get_price_external_source()
            return self._finalize_update(external_price, start_time)

        # Internal source price
        if GET_PRICE_INTERNAL_FIRST:
            LOGGER.debug("Getting price internal first for %s", self.symbol)
            internal_price = self.get_price_internal_source()
            return self._finalize_update(internal_price, start_time)
            
        external_price = self.get_price_external_source()        
        if external_price > 0:
            return self._finalize_update(external_price, start_time)
            
        return self._finalize_update(0, start_time)
        
    def _finalize_update(self, price, start_time):
        """Finalizes the update by setting the price and saving the token."""

        self.price = price
        self.save()
        elapsed_time = time.time() - start_time
        LOGGER.info(
            "Updated price of %s - %s - Time taken: %s seconds",
            self.symbol,
            self.price,
            elapsed_time,
        )
        return self.price
