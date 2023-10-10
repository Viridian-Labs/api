# -*- coding: utf-8 -*-

import json
from web3 import Web3
from multicall import Call, Multicall
from app.settings import (
    VOTER_ADDRESS,
    WRAPPED_BRIBE_FACTORY_ADDRESS,
    LOGGER,
    DEFAULT_DECIMAL,
)
from app.assets import Token

class GaugesTestCase:
    def __init__(self):
        Token.from_tokenlists()
        self.web3 = Web3()

    def _fetch_pair_data(self, pair_address):
        try:
            pair = Multicall([
                Call(pair_address, ["name()(string)"], [["name", None]]),
                Call(pair_address, ["symbol()(string)"], [["symbol", None]]),
                Call(VOTER_ADDRESS, ["gauges(address)(address)", pair_address], [["gauge_address", None]])
            ])()
            return pair
        except Exception as e:
            LOGGER.error("Error fetching pair data from chain for address %s: %s", pair_address, e)
            return None

    def _fetch_gauge_data(self, gauge_address):
        try:
            gauges = Multicall([
                Call(VOTER_ADDRESS, ["internal_bribes(address)(address)", gauge_address], [["fees_address", None]]),
                Call(VOTER_ADDRESS, ["external_bribes(address)(address)", gauge_address], [["bribe_address", None]]),
                Call(VOTER_ADDRESS, ["isAlive(address)(bool)", gauge_address], [["isAlive", None]])
            ])()
            return gauges
        except Exception as e:
            LOGGER.error("Error fetching gauge data from chain for address %s: %s", gauge_address, e)
            return None

    def _fetch_wrapped_bribe_address(self, bribe_address):
        try:
            wrapped_bribe_address = Call(WRAPPED_BRIBE_FACTORY_ADDRESS, ["oldBribeToNew(address)(address)", bribe_address])()
            wrapped_bribe_address = Web3.toChecksumAddress(wrapped_bribe_address)
            return wrapped_bribe_address
        except Exception as e:
            LOGGER.error("Error fetching wrapped bribes data from chain for address %s", e)
            return None

    def test_fetch_external_rewards(self, pair_address):
        pair = self._fetch_pair_data(pair_address)
        if not pair:
            return

        gauges = self._fetch_gauge_data(pair["gauge_address"])
        if not gauges:
            return

        wrapped_bribe_address = self._fetch_wrapped_bribe_address(gauges["bribe_address"])
        if not wrapped_bribe_address:
            return

        current_block = self.web3.eth.getBlock('latest')
        current_timestamp = current_block['timestamp']

        LOGGER.info('Current timestamp %s: ', current_timestamp)

        with open('app/abis/ExternalBribe.sol/abi.json', 'r') as file:
            CONTRACT_ABI_EXTERNAL_BRIBE = json.load(file)
            contract = self.web3.eth.contract(address=wrapped_bribe_address, abi=CONTRACT_ABI_EXTERNAL_BRIBE)

        adjusted_timestamp = contract.functions.getEpochStart(current_timestamp).call()

        reward_calls = []
        tokens_len = contract.functions.rewardsListLength().call()

        for idx in range(tokens_len):
            bribe_token_address = Call(wrapped_bribe_address, ["rewards(uint256)(address)", idx])()
            reward = contract.functions.tokenRewardsPerEpoch(Web3.toChecksumAddress(bribe_token_address), adjusted_timestamp).call()    
            LOGGER.info('reward for  %s %s: ', bribe_token_address, reward)        
            reward_calls.append(Call(wrapped_bribe_address, ["left(address)(uint256)", bribe_token_address], [[bribe_token_address, None]]))

        rewards_data = Multicall(reward_calls)()

        
        LOGGER.info('Checking pair: %s', pair["symbol"])
        LOGGER.info('Checking fees gauge: %s', gauges["fees_address"])
        LOGGER.info('Checking bribes gauge: %s', gauges["bribe_address"])
        LOGGER.info('Checking wrapped_bribe_address: %s', wrapped_bribe_address)

        for (bribe_token_address, amount) in rewards_data.items():
            token = Token.find(bribe_token_address)

            if not token:
                continue

            if not token.decimals:
                token.decimals = DEFAULT_DECIMAL

            decimals = token.decimals
            rewards = amount / 10 ** decimals

            if token.price:
                tbv = amount / 10 ** token.decimals * token.price

                balance = Call(bribe_token_address, ["balanceOf(address)(uint256)", gauges["fees_address"]], [["balanceOf", None]])()
                amount = balance["balanceOf"] / 10 ** decimals

                print(f"Token: {token.symbol} (Address: {token.address}), Balance: {amount}, Rewards: {rewards}, Tvb: {tbv}")

if __name__ == "__main__":
    #address = "0x5a574F12299A5C1a70a0E1dD2fD2E0d2417211a6"
    address = "0x78Ef6D3E3d0da9B2248C11BE11743B4C573ADd25"
    tester = GaugesTestCase()
    tester.test_fetch_external_rewards(address)
