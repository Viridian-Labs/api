import requests

# Fetching data from the APIs
json1_data = requests.get(
    "https://api.equilibrefinance.com/api/v1/assets"
).json()["data"]
json2_data = requests.get("http://localhost:8000/api/v1/assets").json()["data"]

# Function to transform data into a dictionary with address as key
def transform_data(data):
    return {token["address"]: token for token in data}

# Transforming the data sets
tokens1 = transform_data(json1_data)
tokens2 = transform_data(json2_data)

# Comparing the prices
different_prices = []
same_prices = []

for address, token1 in tokens1.items():
    token2 = tokens2.get(address)
    if token2:
        price1 = token1.get("price", 0)
        price2 = token2.get("price", 0)
        symbol = token1.get("symbol", "Unknown")
        if price1 != price2:
            different_prices.append((symbol, address, price1, price2))
        else:
            same_prices.append((symbol, address, price1))

# Displaying the results
print("Tokens with different prices:")
for symbol, address, price1, price2 in different_prices:
    print(
        f"Symbol: {symbol}, Address: {address}, Price in Prod: {price1}, Price in Stag: {price2}"
    )

print("\nTokens with the same price:")
for symbol, address, price in same_prices:
    print(f"Symbol: {symbol}, Address: {address}, Price: {price}")
