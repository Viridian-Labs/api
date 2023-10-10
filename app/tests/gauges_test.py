# -*- coding: utf-8 -*-

from multicall import Call, Multicall

from app.assets import Token

address = "0x5a574F12299A5C1a70a0E1dD2fD2E0d2417211a6"

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
        except Exception as e:
            LOGGER.error(
                "Error fetching pair data from chain for address %s: %s",
                pair_address,
                e,
            )
            return None
        
        print(pair)

        try:
            gauges = Multicall([
                Call(VOTER_ADDRESS, ["internal_bribes(address)(address)", pair["gauge_address"]], [["fees_address", None]]),
                Call(VOTER_ADDRESS, ["external_bribes(address)(address)", pair["gauge_address"]], [["bribe_address", None]]),
                Call(VOTER_ADDRESS, ["isAlive(address)(bool)", pair["gauge_address"]], [["isAlive", None]])
            ])()
        except Exception as e:
            LOGGER.error(
                "Error fetching gauge data from chain for address %s: %s",
                pair["gauge_address"],
                e,
            )
            return None
        
        print(gauges)

        bribe_address = gauges["bribe_address"]

        try:
            wrapped_bribe_address = Call(WRAPPED_BRIBE_FACTORY_ADDRESS, ["oldBribeToNew(address)(address)", bribe_address])()
        except Exception as e:
            LOGGER.error(
                "Error fetching bribes data from chain for address %s", e
            )
            return None
        
        print('wrapped_bribe_address', wrapped_bribe_address)

        try:
            tokens_len = Call(
                wrapped_bribe_address, "rewardsListLength()(uint256)"
            )()
        except Exception as e:
            LOGGER.error(
                "Error fetching bribes data from chain for address %s", e
            )
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
            token = Token.find(bribe_token_address)    

            if token: 

            decimals = token.decimals
            rewards = amount / 10 ** decimals

            if token.price:
                tbv = amount / 10 ** token.decimals * token.price                

                balance = Call(bribe_token_address, ["balanceOf(address)(uint256)", gauges["fees_address"]], [["balanceOf", None]])()
                
                amount = balance["balanceOf"] / 10 ** decimals

                print('Address: $', token.address, ' - Balance: ', amount, token.symbol)
            

if __name__ == "__main__":
    tester = GaugesTestCase()
    tester.test_fetch_external_rewards(address)
