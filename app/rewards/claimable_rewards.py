import json

from multicall import Call, Multicall
from app.settings import (CACHE, LOGGER)
from app.pairs.aprs import get_apr

def get_voter_claimable_rewards(token_id):
    pairs = get_apr()

    rewards = {}

    calls = []
    for pair in pairs.values():
        fee_distributor_address = pair['fee_distributor_address']

        rewards[fee_distributor_address] = {}

        for token in pair['tokens']:
            token_address = token['address']
            rewards[fee_distributor_address][token_address] = {
                'symbol': token['symbol'],
                'earned': 0,
                'price': token['price'],
                'totalUSD': 0
            }

            key = f'{fee_distributor_address}-{token_address}'
            calls.append(
                Call(
                    fee_distributor_address,
                    ["earned(address,uint256)(uint256)", token_address, token_id],
                    [[key, lambda v: v[0]]]
                )
            )

    for key, value in Multicall(calls)().items():
        fee_distributor_address, token_address = key.split('-')
        reward = rewards[fee_distributor_address][token_address]
        reward['earned'] = value
        reward['totalUSD'] = value * reward['price'] / 1e18

    return rewards


if __name__ == '__main__':
    rewards = get_voter_claimable_rewards(50)
    print(rewards)
