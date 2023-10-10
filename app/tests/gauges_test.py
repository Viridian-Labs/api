# -*- coding: utf-8 -*-

from multicall import Call, Multicall
from app.settings import (VOTER_ADDRESS, WRAPPED_BRIBE_FACTORY_ADDRESS, LOGGER, DEFAULT_DECIMAL)
from app.assets import Token
from web3 import Web3
import json

#address = "0x5a574F12299A5C1a70a0E1dD2fD2E0d2417211a6"
address = "0x78Ef6D3E3d0da9B2248C11BE11743B4C573ADd25"


class GaugesTestCase:    

      
    @staticmethod
    def test_fetch_external_rewards(pair_address):
        """Fetch external rewards for the gauge."""

        Token.from_tokenlists()

        w3 = Web3()
      
        try:
            pair = Multicall([
                Call(pair_address, ["name()(string)"], [["name", None]]),
                Call(pair_address, ["symbol()(string)"], [["symbol", None]]),
                Call(VOTER_ADDRESS, ["gauges(address)(address)", pair_address], [["gauge_address", None]])
            ])()
            print(f"Pair: {pair['name']} ({pair['symbol']}), Gauge Address: {pair['gauge_address']}")

        except Exception as e:
            LOGGER.error("Error fetching pair data from chain for address %s: %s", pair_address, e)
            return None

        try:
            gauges = Multicall([
                Call(VOTER_ADDRESS, ["internal_bribes(address)(address)", pair["gauge_address"]], [["fees_address", None]]),
                Call(VOTER_ADDRESS, ["external_bribes(address)(address)", pair["gauge_address"]], [["bribe_address", None]]),
                Call(VOTER_ADDRESS, ["isAlive(address)(bool)", pair["gauge_address"]], [["isAlive", None]])
            ])()
            print(f"Fees Address: {gauges['fees_address']}, Bribe Address: {gauges['bribe_address']}, Is Alive: {gauges['isAlive']}")

        except Exception as e:
            LOGGER.error("Error fetching gauge data from chain for address %s: %s", pair["gauge_address"], e)
            return None

        try:
            wrapped_bribe_address = Call(WRAPPED_BRIBE_FACTORY_ADDRESS, ["oldBribeToNew(address)(address)", gauges["bribe_address"]])()            
            wrapped_bribe_address = Web3.toChecksumAddress(wrapped_bribe_address)

            print(f"Wrapped Bribe Address: {wrapped_bribe_address}")

        except Exception as e:
            LOGGER.error("Error fetching bribes data from chain for address %s", e)
            return None

        try:
            tokens_len = Call(wrapped_bribe_address, "rewardsListLength()(uint256)")()
        except Exception as e:
            LOGGER.error("Error fetching bribes data from chain for address %s", e)
            return None


        reward_calls = []
        current_block = w3.eth.getBlock('latest')
        current_timestamp = current_block['timestamp']
        

        with open('app/abis/ExternalBribe.sol/abi.json', 'r') as file:
                CONTRACT_ABI_EXTERNAL_BRIBE = json.load(file)                
                contract = w3.eth.contract(address=wrapped_bribe_address, abi=CONTRACT_ABI_EXTERNAL_BRIBE)                   


        adjusted_timestamp = contract.functions.getEpochStart(current_timestamp).call()

        for idx in range(tokens_len):
            bribe_token_address = Call(wrapped_bribe_address, ["rewards(uint256)(address)", idx])()                               
            reward = contract.functions.tokenRewardsPerEpoch(Web3.toChecksumAddress(bribe_token_address), adjusted_timestamp).call()
            print('reward', reward)
            reward_calls.append(Call(wrapped_bribe_address, ["left(address)(uint256)", bribe_token_address], [[bribe_token_address, None]]))

        rewards_data = Multicall(reward_calls)()        


        print('Current timestamp: ', current_timestamp)
        print('Checking pair: ', pair["symbol"])
        print('Checking fees gauge: ', gauges["fees_address"])
        print('Checking bribes gauge: ', gauges["bribe_address"])
        print('Checking wrapped_bribe_address...', wrapped_bribe_address)

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
    tester = GaugesTestCase()
    tester.test_fetch_external_rewards(address)
