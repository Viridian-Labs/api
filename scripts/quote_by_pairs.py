import requests
from multicall import Call, Multicall
from web3 import Web3

ROUTER_ADDRESS = "0xA7544C409d772944017BB95B99484B6E0d7B6388"  # Placeholder: replace with your router address

# Fetch the assets data
assets_data = requests.get('https://api.equilibrefinance.com/api/v1/assets').json()['data']

# Get the addresses of the tokens
token_addresses = {
    'GMD': '',
    'spVARA': '',
    'acsVARA': '',
    'CHAM': '',
    'xSHRAP': '',
    'SHRP': '',
}

# Populate the token_addresses dictionary with actual addresses
for asset in assets_data:
    if asset['symbol'] in token_addresses:
        token_addresses[asset['symbol']] = asset['address']

# Fetch the pairs data
pairs_data = requests.get('https://api.equilibrefinance.com/api/v1/pairs').json()['data']

# Loop through the pairs_data and find the pairs with the tokens
relevant_pairs = [pair for pair in pairs_data if pair['token0']['address'] in token_addresses.values() or pair['token1']['address'] in token_addresses.values()]

calls = []

for pair in relevant_pairs:
    token0 = pair['token0']
    token1 = pair['token1']

    # Determine if token0 or token1 is our target token
    if token0['symbol'] in token_addresses:
        our_token = token0
        other_token = token1
    elif token1['symbol'] in token_addresses:
        our_token = token1
        other_token = token0
    else:
        continue  # Neither tokens in our list, skip this pair

    print(f"Pair for {our_token['symbol']}: {other_token['symbol']} - {other_token['address']}")
    
    # Define the call for the contract function
    call = Call(
        ROUTER_ADDRESS,
        [
            "getAmountOut(uint256,address,address)(uint256,bool)",
            1 * 10**token0['decimals'],
            other_token['address'],  # Passing the token address instead of the symbol
            our_token['address']     # Passing our token's address as the last parameter
        ],
    )
    calls.append(call)

# Now, execute the calls using Multicall
try:
    w3 = Web3(Web3.HTTPProvider('https://evm.kava.io'))

    # Check Web3 connection
    if not w3.isConnected():
        raise Exception("Web3 is not connected to any provider.")

    results = Multicall(calls)

    # Iterate over results and print them
    for result in results:
        print('result', result)
except Exception as e:
    print(e)
