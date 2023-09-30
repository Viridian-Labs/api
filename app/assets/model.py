import requests
import time
import json
import concurrent.futures
from multicall import Call, Multicall
from walrus import Model, TextField, IntegerField, FloatField, BooleanField
from web3.auto import w3
from web3.exceptions import ContractLogicError

from app.settings import (
    STABLE_TOKEN_ADDRESS,
    ROUTER_ADDRESS,
    EXTERNAL_PRICE_ORDER,
    INTERNAL_PRICE_ORDER,
    LOGGER,
    CACHE,    
    GET_PRICE_INTERNAL_FIRST,
    IGNORED_TOKEN_ADDRESSES,
    AXELAR_BLUECHIPS_ADDRESSES,
    BLUECHIP_TOKEN_ADDRESSES,
    NATIVE_TOKEN_ADDRESS,
    TOKENLISTS
)

DEXSCREENER_ENDPOINT = "https://api.dexscreener.com/latest/dex/tokens/"
DEFILLAMA_ENDPOINT = "https://coins.llama.fi/prices/current/"
DEXGURU_ENDPOINT = 'https://api.dev.dex.guru/v1/chain/10/tokens/%/market'
DEBANK_ENDPOINT = 'https://api.debank.com/history/token_price?chain=op&'

class Token(Model):

    """
    The Token class represents a blockchain token and provides methods to fetch and update its price
    from various sources, both internal and external. It also provides class methods to fetch token data
    from the chain and from token lists.
    
    Attributes:
        address (TextField): The blockchain address of the token, serves as the primary key.
        name (TextField): The name of the token.
        symbol (TextField): The symbol representing the token.
        decimals (IntegerField): The number of decimal places the token uses.
        logoURI (TextField): The URI where the token's logo can be found.
        price (FloatField): The current price of the token.
        stable (BooleanField): A boolean indicating whether the token is stable.
        liquid_staked_address (TextField): The address where the token is liquid staked.
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
    stable = BooleanField(default=0)
    liquid_staked_address = TextField()
    created_at = FloatField(default=w3.eth.get_block("latest").timestamp)
    taxes = FloatField(default=0)   

    DEXSCREENER_ENDPOINT = DEXSCREENER_ENDPOINT
    DEFILLAMA_ENDPOINT = DEFILLAMA_ENDPOINT
    DEXGURU_ENDPOINT = DEXGURU_ENDPOINT
    DEBANK_ENDPOINT = DEBANK_ENDPOINT 


    def get_price_external_source(self):

        """
        Fetches the price of the token from external sources defined in EXTERNAL_PRICE_ORDER.
        It iterates over the external price getters and returns the price from the first successful fetch.
        
        Returns:
            float: The fetched price of the token from an external source, 0 if all fetches fail.
            
        Raises:
            Exception: Any exception raised by the external price getter methods.
        """

        price_getters_mapping = {
            "_get_price_from_dexscreener": self._get_price_from_dexscreener,
            "_get_price_from_debank": self._get_price_from_debank,
            "_get_price_from_defillama": self._get_price_from_defillama,
            "_get_price_from_dexguru": self._get_price_from_dexguru
        }

        for func_name in EXTERNAL_PRICE_ORDER:
            if func_name in price_getters_mapping:
                func = price_getters_mapping[func_name]
                try:
                    price = func()
                    if price > 0:
                        self.price = price
                        return price
                except Exception as e:
                    LOGGER.error(f"Error fetching price using {func_name}: {e}")

        return 0


    def get_price_internal_source(self):

        """
        Fetches the price of the token from internal sources defined in INTERNAL_PRICE_ORDER.
        It iterates over the internal price getters and returns the price from the first successful fetch.
        
        Returns:
            float: The fetched price of the token from an internal source, 0 if all fetches fail.
            
        Raises:
            Exception: Any exception raised by the internal price getter methods.
        """

        stablecoin = Token.find(STABLE_TOKEN_ADDRESS)
        
        price_getters_mapping = {
            "direct": lambda: self._get_direct_price(stablecoin),
            "axelar_bluechips": lambda: self._get_price_through_tokens(AXELAR_BLUECHIPS_ADDRESSES, stablecoin),
            "bluechip_tokens": lambda: self._get_price_through_tokens(BLUECHIP_TOKEN_ADDRESSES, stablecoin),
            "native_token": lambda: self._get_price_through_tokens([NATIVE_TOKEN_ADDRESS], stablecoin),
        }
        
        for route_type in INTERNAL_PRICE_ORDER:
            if route_type in price_getters_mapping:
                try:
                    price = price_getters_mapping[route_type]()
                    if price > 0:
                        self.price = price
                        return price
                except Exception as e:
                    LOGGER.error(f"Error fetching price using {route_type}: {e}")
            else:
                LOGGER.error(f"Invalid route_type {route_type}")
        
        return 0


    def _get_direct_price(self, stablecoin):

        """
        Fetches the direct price of the token in terms of the provided stablecoin.
        
        Parameters:
            stablecoin (Token): The stablecoin against which the price of the token is to be fetched.
            
        Returns:
            float: The fetched price of the token, 0 if fetching fails.
            
        Raises:
            ContractLogicError: If there is an error in getting the chain price for the token.
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

        """
        Fetches the price of the token through a list of intermediary tokens in terms of the provided stablecoin.
        
        Parameters:
            token_addresses (List[str]): A list of addresses of the intermediary tokens.
            stablecoin (Token): The stablecoin against which the price of the token is to be fetched.
            
        Returns:
            float: The fetched price of the token, 0 if fetching fails or no valid calls.
            
        Raises:
            Exception: Any exception raised during the execution of multicall or getting amount out.
        """
        
        if not token_addresses or not isinstance(token_addresses, list):
            LOGGER.error("Invalid token_addresses")
            return 0
        
        calls = []
        for token_address in token_addresses:
            token = Token.find(token_address)
            if not token:
                LOGGER.error(f"Token not found for address: {token_address}")
                continue
            
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
        
        if not calls:
            LOGGER.error("No valid calls")
            return 0
        
        try:
            results = Multicall(calls)()
        except Exception as e:
            LOGGER.error(f"Error executing multicall: {e}")
            return 0
        
        for i, token_address in enumerate(token_addresses):
            try:
                amountA, is_stable = results[i]
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
                LOGGER.error(f"Contract logic error for token address: {token_address}")
                continue
            except Exception as e:
                LOGGER.error(f"Error getting amount out: {e}")
                continue
        
        return 0


    def _update_price(self):
            
        """
        Updates the price of the token by fetching it from the defined internal and external sources.
        The order of fetching and the sources are defined in GET_PRICE_INTERNAL_FIRST, 
        INTERNAL_PRICE_ORDER, and EXTERNAL_PRICE_ORDER.
        
        Returns:
            float: The updated price of the token, 0 if updating fails.
            
        Raises:
            Exception: Any exception raised by the price fetching methods.
        """
        
        start_time = time.time()

        if self.symbol in IGNORED_TOKEN_ADDRESSES or not isinstance(self.decimals, int):
            LOGGER.error("Invalid token or decimals for token: %s", self.address)
            return self._finalize_update(0, start_time)

        price_fetching_functions = [
            self.get_price_internal_source,
            self.get_price_external_source
        ] if GET_PRICE_INTERNAL_FIRST else [
            self.get_price_external_source,
            self.get_price_internal_source
        ]

        for get_price in price_fetching_functions:
            price = get_price()
            if price > 0:
                return self._finalize_update(price, start_time)

        return self._finalize_update(0, start_time)
    

    def _get_price_from_dexscreener(self):
        try:
            res = requests.get(self.DEXSCREENER_ENDPOINT + self.address)
            res.raise_for_status()
            data = res.json()
            price_str = str(data.get("pairs", [{}])[0].get("priceUsd", 0)).replace(",", "")
            return float(price_str)
        except (requests.RequestException, ValueError) as e:
            LOGGER.error("Error fetching price from Dexscreener: %s", e)
            return 0


    def _get_price_from_defillama(self):
        try:
            res = requests.get(self.DEFILLAMA_ENDPOINT + "kava:" + self.address.lower())
            res.raise_for_status()
            data = res.json()
            coins = data.get("coins", {})
            for _, coin in coins.items():
                price = coin.get("price", 0)
                if price:
                    return price
        except (requests.RequestException, ValueError) as e:
            LOGGER.error("Error fetching price from DefiLlama: %s", e)
            return 0
        LOGGER.error("No price found for token: %s", self.address)
        return 0


    def _get_price_from_debank(self):
        try:
            res = requests.get(self.DEBANK_ENDPOINT + 'token_id=' + self.address.lower())
            res.raise_for_status()
            token_data = res.json().get('data') or {}
            return token_data.get('price') or 0
        except (requests.RequestException, ValueError) as e:
            LOGGER.error("Error fetching price from DeBank: %s", e)
            return 0


    def _get_price_from_dexguru(self):
        try:
            res = requests.get(self.DEXGURU_ENDPOINT % self.address.lower())
            res.raise_for_status()
            return res.json().get('price_usd', 0)
        except (requests.RequestException, ValueError) as e:
            LOGGER.error("Error fetching price from DexGuru: %s", e)
            return 0
        
        
    def _finalize_update(self, price, start_time):
        """Finalizes the update by setting the price and saving the token."""
        self.price = price
        self.save()
        elapsed_time = time.time() - start_time
        LOGGER.debug("Updated price of %s - %s - Time taken: %s seconds", self.symbol, self.price, elapsed_time)
        return self.price


    @classmethod
    def find(cls, address):
        """Loads a token from the database, or from chain if not found."""
        if not address:
            LOGGER.error("Address is None. Unable to fetch %s.", cls.__name__)
            return None

        try:
            return cls.load(address.lower())
        except KeyError:
            LOGGER.error("Error fetching %s:%s from database. Fetching from chain...", cls.__name__, address)
            return cls.from_chain(address.lower())    


    @classmethod
    def from_chain(cls, address, logoURI=None):
        """Fetches and returns a token from chain."""
        address = address.lower()
        data = cls._fetch_data_from_chain(address)
        token = cls.create(address=address, **data)
        token._update_price()
        return token


    @staticmethod
    def _fetch_data_from_chain(address):
        """Fetches token data from the chain."""
        token_multi = Multicall(
            [
                Call(address, ["name()(string)"], [["name", None]]),
                Call(address, ["symbol()(string)"], [["symbol", None]]),
                Call(address, ["decimals()(uint8)"], [["decimals", None]]),
            ]
        )
        return token_multi()


    @classmethod
    def from_tokenlists(cls):
        """Fetches and merges all the tokens from available tokenlists."""
        our_chain_id = w3.eth.chain_id
        all_tokens = cls._fetch_all_tokens(our_chain_id)
        return all_tokens
    

    @classmethod
    def _fetch_all_tokens(cls, our_chain_id):
        """Fetches all tokens from the token lists."""
        all_tokens = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(cls._fetch_tokenlist, tlist, our_chain_id) for tlist in TOKENLISTS]
            for future in concurrent.futures.as_completed(futures):
                try:
                    all_tokens.extend(future.result())
                except Exception as exc:
                    LOGGER.error('Generated an exception: %s', exc)
        return all_tokens


    @classmethod
    def _fetch_tokenlist(cls, tlist, our_chain_id):
        """Fetches tokens from a specific token list."""
        tokens = []
        try:
            res = requests.get(tlist).json()
            for token_data in res.get("tokens", []):
                if cls._is_valid_token(token_data, our_chain_id):
                    token = cls._create_and_update_token(token_data)
                    tokens.append(token)
        except (requests.RequestException, json.JSONDecodeError) as error:
            LOGGER.error("Error loading token list %s: %s", tlist, error)
        return tokens


    @staticmethod
    def _is_valid_token(token_data, our_chain_id):
        """Validates if the token is from the correct chain and not in the ignored list."""
        address = token_data.get("address", "").lower()
        return token_data.get("chainId") == our_chain_id and address not in IGNORED_TOKEN_ADDRESSES and address


    @classmethod
    def _create_and_update_token(cls, token_data):
        """Creates and updates the token."""
        address = token_data.get("address", "").lower()
        liquid_staked_address = token_data.get("liquid_staked_address", "").lower()
        symbol = token_data.get("symbol", "")
        tags = token_data.get("tags", [""])
        token = cls.create(address=address, liquid_staked_address=liquid_staked_address, symbol=symbol)
        token.stable = 1 if "stablecoin" in tags[0] else 0
        token._update_price()
        return token


