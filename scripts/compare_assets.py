from statistics import mean, stdev

import numpy as np
import pandas as pd
import requests


def transform_data(data):
    """Transform data into a dictionary with address as key."""
    return {token["address"]: token for token in data}


def are_prices_close(price1, price2, percent_tolerance=0.1):
    """Check if prices are close based on percentual difference."""
    if price1 == 0 or price2 == 0:
        return False  # Avoid division by zero
    percent_difference = abs(price1 - price2) / max(price1, price2)

    return percent_difference <= percent_tolerance


def get_data_price_from_dexscreener(address):
    json3_url = "https://api.dexscreener.com/latest/dex/tokens/"
    pairs = requests.get(json3_url + address).json()["pairs"]
    if pairs is None or not isinstance(pairs, list) or len(pairs) == 0:
        return 0
    pairs_in_core = [
        pair
        for pair in pairs
        if pair["chainId"] == "core"
        and pair["dexId"] == "viridian"
        and pair["quoteToken"]["address"].lower() != address.lower()
    ]
    # LOGGER.debug(f"Pairs in Core: {pairs_in_core}")

    if len(pairs_in_core) == 0:
        # price = str(pairs[0].get("priceUsd") or 0).replace(",", "")
        prices = [float(x.get("priceUsd") or 0) for x in pairs]

    else:
        # prices = str(pairs_in_core[0].get("priceUsd") or 0).replace(
        #     ",", ""
        # )
        prices = [float(x.get("priceUsd") or 0) for x in pairs_in_core]
    print(f"TOKEN: {address}")
    print(f"Prices in Dexscreener: {prices}")
    prices_mean = mean([x for x in prices])
    if len(prices) > 2:
        prices_std = (
            stdev([x for x in prices])
            if len(prices) > 2
            else 0.8 * prices_mean
        )
        final_prices = [
            x for x in prices if abs(x - prices_mean) <= prices_std
        ]
        print(f"Final prices: {final_prices}")
        min_diff = min([abs(x - prices_mean) for x in final_prices])
        price = [x for x in prices if abs(x - prices_mean) == min_diff][0]
        print(f"Price: {price}")
        return float(price)
    if len(prices) >= 0:
        min_diff = min([abs(x - prices_mean) for x in prices])
        price = [x for x in prices if abs(x - prices_mean) == min_diff][0]
        return float(price)
    else:
        return 0


# Fetching data from the APIs
json1_url = "https://api.old.equilibrefinance.com/api/v1/assets"
json1_data = requests.get(json1_url).json()["data"]

json2_url = "http://localhost:8000/api/v1/assets"
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
        price3 = get_data_price_from_dexscreener(address)
        symbol = token1.get("symbol", "Unknown")
        if price1 != price2:
            if are_prices_close(price1, price2):
                close_prices.append((symbol, address, price1, price2, price3))
            # elif are_prices_close(price2, price3):
            #     close_prices.append((symbol, address,
            #       price1, price2, price3))
            else:
                different_prices.append(
                    (symbol, address, price1, price2, price3)
                )
        else:
            same_prices.append((symbol, address, price1, price2, price3))

# pd.options.display.float_format = '{:.6f}'.format
print("Tokens with different prices:")
df = pd.DataFrame(
    different_prices,
    columns=[
        "Symbol",
        "Address",
        "Price in Prod",
        "Price in Stag",
        "Price in Dexscreener",
    ],
)
df["Same as Dexscreener"] = np.where(
    df["Price in Stag"] == df["Price in Dexscreener"], True, False
)
# df.loc[df["Price in Prod"] == 0, "Price in Prod"] = "ZERO"
# df.loc[df["Price in Stag"] == 0, "Price in Stag"] = "ZERO"
# df.loc[df["Price in Dexscreener"] == 0, "Price in Dexscreener"] = "ZERO"
df.sort_values(by=["Symbol"], inplace=True, ascending=True)

print(df)
print(f"Count: {len(df)}")


print("\nTokens with close and acceptable prices:")
df2 = pd.DataFrame(
    close_prices,
    columns=[
        "Symbol",
        "Address",
        "Price in Prod",
        "Price in Stag",
        "Price in Dexscreener",
    ],
)
df2["Same as Dexscreener"] = np.where(
    df2["Price in Stag"] == df2["Price in Dexscreener"], True, False
)
# df2.loc[df2["Price in Prod"] == 0, "Price in Prod"] = "ZERO"
# df2.loc[df2["Price in Stag"] == 0, "Price in Stag"] = "ZERO"
# df2.loc[df2["Price in Dexscreener"] == 0, "Price in Dexscreener"] = "ZERO"
df2.sort_values(by=["Symbol"], inplace=True, ascending=True)
print(df2)
print(f"Count: {len(df2)}")


print("\nTokens with the same price:")
df3 = pd.DataFrame(
    same_prices,
    columns=[
        "Symbol",
        "Address",
        "Price in Prod",
        "Price in Stag",
        "Price in Dexscreener",
    ],
)
df3["Same as Dexscreener"] = np.where(
    df3["Price in Stag"] == df3["Price in Dexscreener"], True, False
)
df3.loc[df3["Price in Prod"] == 0, "Price in Prod"] = "ZERO"
df3.loc[df3["Price in Stag"] == 0, "Price in Stag"] = "ZERO"
df3.loc[df3["Price in Dexscreener"] == 0, "Price in Dexscreener"] = "ZERO"
df3.sort_values(by=["Symbol"], inplace=True, ascending=True)
print(df3)
