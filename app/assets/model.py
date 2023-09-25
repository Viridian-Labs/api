# -*- coding: utf-8 -*-

import requests
import requests.exceptions
from multicall import Call, Multicall
from walrus import BooleanField, FloatField, IntegerField, Model, TextField
from web3.auto import w3
from web3.exceptions import ContractLogicError
import time
import json
import concurrent.futures

from app.settings import (
    AXELAR_BLUECHIPS_ADDRESSES,
    BLUECHIP_TOKEN_ADDRESSES,
    CACHE,
    HALT_API_PRICE_FEEDS,
    IGNORED_TOKEN_ADDRESSES,
    SPECIAL_SYMBOLS,
    LOGGER,
    NATIVE_TOKEN_ADDRESS,
    ROUTE_TOKEN_ADDRESSES,
    ROUTER_ADDRESS,
    STABLE_TOKEN_ADDRESS,    
    TOKENLISTS,
    PRICE_FEED_ORDER,
    AGGREGATED_PRICE_ORDER,
)


class Token(Model):
    """ERC20 token model."""

    __database__ = CACHE

    address = TextField(primary_key=True)
    name = TextField()
    symbol = TextField()
    decimals = IntegerField()
    logoURI = TextField()
    price = FloatField(default=0)
    stable = BooleanField(default=0)    
    liquid_staked_address = TextField()    
    created_at = FloatField(default=w3.eth.get_block("latest").timestamp)
    
    DEXSCREENER_ENDPOINT = "https://api.dexscreener.com/latest/dex/tokens/" # See: https://docs.dexscreener.com/#tokens
    DEFILLAMA_ENDPOINT = "https://coins.llama.fi/prices/current/" # See: https://defillama.com/docs/api#operations-tag-coins
    DEXGURU_ENDPOINT = 'https://api.dev.dex.guru/v1/chain/10/tokens/%/market' # See: https://api.dev.dex.guru/docs#tag/Token-Finance

    def debank_price_in_stables(self):
        """Returns the price quoted from DeBank"""
        # Peg it forever.
        if self.address == STABLE_TOKEN_ADDRESS:
            return 1.0

        req = self.DEBANK_ENDPOINT + 'token_id=' + self.address.lower()

        res = requests.get(req).json()
        token_data = res.get('data') or {}

        return token_data.get('price') or 0

    def dexguru_price_in_stables(self):
        """Returns the price quoted from DexGuru"""
        # Peg it forever.
        if self.address == STABLE_TOKEN_ADDRESS:
            return 1.0

        res = requests.get(self.DEXGURU_ENDPOINT % self.address.lower()).json()

        return res.get('price_usd', 0)


    def defillama_price_in_stables(self) -> float:
        """Returns the price quoted from our llama defis."""
        
        # Peg it forever.
        if self.address == STABLE_TOKEN_ADDRESS:
            return 1.0
        
        chain_token = "kava:" + self.address.lower()
        session = requests.Session()
        
        try:
            res = session.get(self.DEFILLAMA_ENDPOINT + chain_token)
            res.raise_for_status()  
            data = res.json()
        except (requests.RequestException, ValueError) as e:
            LOGGER.error("Error fetching price from DefiLlama: %s", e)
            return 0
        
        coins = data.get("coins", {})
        for _, coin in coins.items():
            price = coin.get("price", 0)
            if price:
                return price
        
        LOGGER.error("No price found for token: %s", self.address)
        return 0
    

    def dexscreener_price_in_stables(self):
        """Returns the price quoted from an aggregator in stables/USDC."""
        if self.address == STABLE_TOKEN_ADDRESS:
            return 1.0
        
        session = requests.Session()  
        try:
            res = session.get(self.DEXSCREENER_ENDPOINT + self.address)
            res.raise_for_status() 
            data = res.json()
        except (requests.RequestException, ValueError) as e:
            LOGGER.error("Error fetching price from Dexscreener: %s", e)
            return 0
        
        pairs = data.get("pairs", [])
        if not pairs:
            return 0
        
        CHAIN_ID = "kava"
        DEX_ID = "equilibre"
        pairs_in_kava = [
            pair for pair in pairs
            if pair.get("chainId") == CHAIN_ID
            and pair.get("dexId") == DEX_ID
            and pair.get("quoteToken", {}).get("address", "").lower() != self.address.lower()
        ]
        
        price_str = str((pairs_in_kava[0] if pairs_in_kava else pairs[0]).get("priceUsd", 0)).replace(",", "")
        try:
            return float(price_str)
        except ValueError:
            LOGGER.error("Invalid price received: %s", price_str)
            return 0
        
    def aggregated_price_in_stables(self):
        price_getters_mapping = {
            "_get_price_from_dexscreener": self._get_price_from_dexscreener,
            "chain_price_in_stables": self.chain_price_in_stables,
            "debank_price_in_stables": self.debank_price_in_stables,
            "_get_price_from_defillama": self._get_price_from_defillama,
            "dexguru_price_in_stables": self.dexguru_price_in_stables
        }

        # Get the environment variable as a string and split it into a list
        aggregated_price_order = AGGREGATED_PRICE_ORDER

        for func_name in aggregated_price_order:
            if func_name in price_getters_mapping:
                func = price_getters_mapping[func_name]  # Corrected line
                price = func()
                if price > 0:
                    self.price = price
                    return price

        return 0 
   
    def _get_price_from_dexscreener(self):
        price = self.dexscreener_price_in_stables()
        if price > 0 and self.address not in BLUECHIP_TOKEN_ADDRESSES:
            LOGGER.debug("Dexscreener price for %s: %s", self.symbol, price)
        return price


    def _get_price_from_defillama(self):
        try:
            price = self.defillama_price_in_stables()
            LOGGER.debug("Defillama price for %s: %s", self.symbol, price)
            return price
        except requests.exceptions.RequestException as e:
            LOGGER.error("Error fetching price from Defillama for %s: %s", self.symbol, str(e))
            return 0
        

    def chain_price_in_stables(self):
        """Returns the price quoted from our router in stables/USDC."""
        # Peg it forever.
        if self.address == STABLE_TOKEN_ADDRESS:
            return 1.0                  
        
        LOGGER.debug("Chain price for %s", self.symbol)
        stablecoin = Token.find(STABLE_TOKEN_ADDRESS)
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
            LOGGER.debug("Chain price for %s: %s", self.symbol, amount)
        except ContractLogicError:
            LOGGER.debug("Found error getting chain price for %s", self.symbol)
            return 0

        return amount / 10 ** stablecoin.decimals

    
    def chain_price_in_stables_and_default_token(self):
        """Returns the price quoted from our router in stables/USDC
        passing through default token route or some special cases"""

        if self.address == STABLE_TOKEN_ADDRESS:
            return 1.0
        
        LOGGER.debug("Chain price NEW for %s", self.symbol)

        stablecoin = Token.find(STABLE_TOKEN_ADDRESS)
        nativecoin = Token.find(NATIVE_TOKEN_ADDRESS)

        calls = []
        for token_address in ROUTE_TOKEN_ADDRESSES:
            token = Token.find(token_address)
            LOGGER.debug("CALC THROUGH for %s", token.symbol)
            calls.append(
                Call(
                    ROUTER_ADDRESS,
                    [
                        "getAmountOut(uint256,address,address)(uint256,bool)",
                        1 * 10 ** self.decimals,
                        self.address,
                        token_address,
                    ],
                )
            )

        results = Multicall(calls)()

        for i, token_address in enumerate(ROUTE_TOKEN_ADDRESSES):
            try:
                amountA, is_stable = results[i]
                token = Token.find(token_address)
                if token_address in BLUECHIP_TOKEN_ADDRESSES:
                    amountB, is_stable = Call(
                        ROUTER_ADDRESS,
                        [
                            "getAmountOut(uint256,address,address)(uint256,bool)",
                            amountA,
                            token_address,
                            nativecoin.address,
                        ],
                    )()
                    amountC, is_stable = Call(
                        ROUTER_ADDRESS,
                        [
                            "getAmountOut(uint256,address,address)(uint256,bool)",
                            amountB,
                            nativecoin.address,
                            stablecoin.address,
                        ],
                    )()
                    if amountC > 0:
                        return amountC / 10 ** stablecoin.decimals

                if self.symbol in ["DEXI"] and token.symbol == "multiUSDC":
                    LOGGER.debug("DEXI especial case through LION")
                    lion = Token.find("0x990e157fC8a492c28F5B50022F000183131b9026")
                    amountA, is_stable = Call(
                        ROUTER_ADDRESS,
                        [
                            "getAmountOut(uint256,address,address)(uint256,bool)",
                            1 * 10 ** self.decimals,
                            self.address,
                            lion.address,
                        ],
                    )()
                    amountB, is_stable = Call(
                        ROUTER_ADDRESS,
                        [
                            "getAmountOut(uint256,address,address)(uint256,bool)",
                            amountA,
                            lion.address,
                            token.address,
                        ],
                    )()
                    amountC, is_stable = Call(
                        ROUTER_ADDRESS,
                        [
                            "getAmountOut(uint256,address,address)(uint256,bool)",
                            amountB,
                            token.address,
                            stablecoin.address,
                        ],
                    )()
                    if amountC > 0:
                        return amountC / 10 ** stablecoin.decimals

                amountB, is_stable = Call(
                    ROUTER_ADDRESS,
                    [
                        "getAmountOut(uint256,address,address)(uint256,bool)",
                        amountA,
                        token_address,
                        stablecoin.address,
                    ],
                )()
                if amountB > 0:
                    return amountB / 10 ** stablecoin.decimals
            except ContractLogicError:
                continue

        return 0


    def chain_price_in_bluechips(self):
        """Returns the price quoted from our router in stables/USDC
        passing through a bluechip route"""
        # Peg it forever.
        if self.address == STABLE_TOKEN_ADDRESS:
            return 1.0
        
        LOGGER.debug("Chain price Bluechips for %s", self.symbol)
        stablecoin = Token.find(STABLE_TOKEN_ADDRESS)
        
        calls = []
        for b in BLUECHIP_TOKEN_ADDRESSES:
            bluechip = Token.find(b)
            calls.append(
                Call(
                    ROUTER_ADDRESS,
                    [
                        "getAmountOut(uint256,address,address)(uint256,bool)",
                        1 * 10 ** self.decimals,
                        self.address,
                        bluechip.address,
                    ],
                )
            )
        
        try:
            results = Multicall(calls)()
        except ContractLogicError:
            return 0
        
        for i, (amountA, is_stable) in enumerate(results):
            bluechip = Token.find(BLUECHIP_TOKEN_ADDRESSES[i])
            try:
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
                continue
        
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

    @classmethod
    def find(cls, address):
        """Loads a token from the database, of from chain if not found."""
        if address is None:
            return None

        try:

            return cls.load(address.lower())
        except KeyError:
            LOGGER.error("ERROR Fetching %s:%s...", cls.__name__, address)
            return cls.from_chain(address.lower())
        

    def _update_price(self):
        start_time = time.time()
        
        if self.symbol in IGNORED_TOKEN_ADDRESSES:
            return self._finalize_update(0, start_time)

        if not HALT_API_PRICE_FEEDS or self.symbol in SPECIAL_SYMBOLS:
            price = self.aggregated_price_in_stables()
            if price > 0:
                return self._finalize_update(price, start_time)        
            
        if not self.decimals:
            LOGGER.debug("Token doesn't have any decimals %s", self.symbol)
            return 0
        
        if not isinstance(self.decimals, int):
            LOGGER.error("Invalid value for decimals for token: %s", self.address)
            return 0

        price_functions = {
            "chain_price_in_stables": self.chain_price_in_stables,
            "chain_price_in_bluechips": self.chain_price_in_bluechips,
            "chain_price_in_stables_and_default_token": self.chain_price_in_stables_and_default_token,
            "chain_price_in_liquid_staked": self.chain_price_in_liquid_staked,
        }

        for func_name in PRICE_FEED_ORDER:
            if func_name in price_functions:
                func = price_functions[func_name]
                price = func()

                if price > 0:
                    return self._finalize_update(price, start_time)

        if self.address in AXELAR_BLUECHIPS_ADDRESSES:
            price = self.temporary_price_in_bluechips()
            if price > 0:
                return self._finalize_update(price, start_time)

        return self._finalize_update(0, start_time)


    def _get_chain_price(self, log_message, price_function):
        LOGGER.debug(log_message)
        return price_function()

    def _finalize_update(self, price, start_time):
        self.price = price
        self.save()
        elapsed_time = time.time() - start_time
        LOGGER.debug("Updated price of %s - %s - Time taken: %s seconds", self.symbol, self.price, elapsed_time)
        return self.price
    

    @classmethod
    def from_chain(cls, address, logoURI=None):
        address = address.lower()
        LOGGER.debug("Fetching from chain %s:%s...", cls.__name__, address)
        """Fetches and returns a token from chain."""
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

    @classmethod
    def from_tokenlists(cls):
        """Fetches and merges all the tokens from available tokenlists."""
        our_chain_id = w3.eth.chain_id

        def fetch_tokenlist(tlist):
            tokens = []
            with requests.Session() as session:  
                try:
                    res = session.get(tlist).json()
                except (requests.RequestException, json.JSONDecodeError) as error:
                    LOGGER.error("Error fetching token list %s: %s", tlist, error)
                    return tokens   

                for token_data in res.get("tokens", []):
                    try:
                        if token_data.get("chainId") != our_chain_id:
                            LOGGER.debug("Token not in chain: %s", token_data.get("symbol"))
                            continue

                        address = token_data.get("address", "").lower()

                        if address in IGNORED_TOKEN_ADDRESSES or not address:
                            LOGGER.debug("Address ignored: %s", address)
                            continue

                        liquid_staked_address = token_data.get("liquid_staked_address", "").lower()
                        symbol = token_data.get("symbol", "")
                        tags = token_data.get("tags", [""])

                        token = cls.create(address=address, liquid_staked_address=liquid_staked_address, symbol=symbol)
                        token.stable = 1 if "stablecoin" in tags[0] else 0
                        token._update_price()

                        tokens.append(token)
                    except Exception as error:
                        LOGGER.error("Error loading token %s: %s", token_data.get("symbol"), error)
            return tokens

        all_tokens = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(fetch_tokenlist, tlist) for tlist in TOKENLISTS]
            for future in concurrent.futures.as_completed(futures):
                try:
                    all_tokens.extend(future.result())
                except Exception as exc:
                    LOGGER.error('The function generated an exception: %s' % exc)

        return all_tokens  
