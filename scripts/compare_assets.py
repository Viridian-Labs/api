import requests


def transform_data(data):
    """Transform data into a dictionary with address as key."""
    return {token["address"]: token for token in data}


def are_prices_close(price1, price2, percent_tolerance=0.05):
    """Check if prices are close based on percentual difference."""
    if price1 == 0 or price2 == 0:
        return False  # Avoid division by zero
    percent_difference = abs(price1 - price2) / max(price1, price2)
    return percent_difference <= percent_tolerance


# Fetching data from the APIs
json1_url = "https://api.equilibrefinance.com/api/v1/assets"
json1_data = requests.get(json1_url).json()["data"]

json2_url = "https://apitest.equilibrefinance.com/api/v1/assets"
json2_data = requests.get(json2_url).json()["data"]

tokens1 = transform_data(json1_data)
tokens2 = transform_data(json2_data)

different_prices = []
same_prices = []
close_prices = []

for address, token1 in tokens1.items():
    token2 = tokens2.get(address)
    if token2:
        price1 = token1.get("price", 0)
        price2 = token2.get("price", 0)
        symbol = token1.get("symbol", "Unknown")
        if price1 != price2:
            if are_prices_close(price1, price2):
                close_prices.append((symbol, address, price1, price2))
            else:
                different_prices.append((symbol, address, price1, price2))
        else:
            same_prices.append((symbol, address, price1))

print("Tokens with different prices:")
for symbol, address, price1, price2 in different_prices:
    print(
        f"Symbol: {symbol}, Address: {address}, "
        f"Price in Prod: {price1}, Price in Stag: {price2}"
    )

print("\nTokens with close and acceptable prices:")
for symbol, address, price1, price2 in close_prices:
    print(
        f"Symbol: {symbol}, Address: {address}, "
        f"Price in Prod: {price1}, Price in Stag: {price2}"
    )

print("\nTokens with the same price:")
for symbol, address, price in same_prices:
    print(f"Symbol: {symbol}, Address: {address}, Price: {price}")
