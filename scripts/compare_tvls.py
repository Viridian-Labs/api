import pandas as pd
import requests


def transform_data(data):
    """Transform data into a dictionary with address as key."""
    return {pair["address"]: pair for pair in data}


def are_tvls_close(tvl1, tvl2, percent_tolerance=0.1):
    """Check if tvls are close based on percentual difference."""
    if tvl1 == 0 or tvl2 == 0:
        return False  # Avoid division by zero
    percent_difference = abs(tvl1 - tvl2) / max(tvl1, tvl2)

    return percent_difference <= percent_tolerance


def dexscreener_request(address):
    json_url = f"https://api.dexscreener.com/latest/dex/pairs/core/{address}"
    pairs = requests.get(json_url).json()["pairs"]
    if pairs is None or not isinstance(pairs, list) or len(pairs) == 0:
        return 0
    # print(pairs[0])
    tvl = (
        pairs[0].get("liquidity").get("usd")
        if pairs[0].get("liquidity")
        else 0
    )
    return float(tvl)


# Pandas config
pd.set_option("display.max_rows", None)
pd.set_option("display.max_columns", None)
pd.set_option("display.width", None)

json1_url = "https://api.old.equilibrefinance.com/api/v1/pairs"
json1_data = requests.get(json1_url).json()["data"]

json2_url = "http://localhost:8000/api/v1/pairs"
json2_data = requests.get(json2_url).json()["data"]

pairs1 = transform_data(json1_data)
pairs2 = transform_data(json2_data)

diff_tvls = []
same_tvls = []
close_tvls = []

diff_tvls_dex = []
same_tvls_dex = []
close_tvls_dex = []

for address, pair1 in pairs1.items():
    pair2 = pairs2.get(address)
    if pair2:
        tvl1 = pair1.get("tvl", 0)
        tvl2 = pair2.get("tvl", 0)
        tvl_dex = dexscreener_request(address)
        symbol = pair1.get("symbol", "N/A")

        if tvl1 != tvl2:
            if are_tvls_close(tvl1, tvl2):
                close_tvls.append((address, symbol, tvl1, tvl2))
            else:
                diff_tvls.append((address, symbol, tvl1, tvl2))
        else:
            same_tvls.append((address, symbol, tvl1, tvl2))

        if tvl2 != tvl_dex:
            if are_tvls_close(tvl2, tvl_dex):
                close_tvls_dex.append((address, symbol, tvl2, tvl_dex))
            else:
                diff_tvls_dex.append((address, symbol, tvl2, tvl_dex))
        else:
            same_tvls_dex.append((address, symbol, tvl2, tvl_dex))

print("TVLs with different values:")
df = pd.DataFrame(
    diff_tvls, columns=["Address", "Symbol", "TVL OLD", "TVL NEW"]
)
df["Difference"] = df["TVL OLD"] - df["TVL NEW"]
df.sort_values(by=["Difference"], inplace=True, ascending=False)

print(df)
print("TVLs with same values:")
df2 = pd.DataFrame(
    same_tvls, columns=["Address", "Symbol", "TVL OLD", "TVL NEW"]
)
print(df2)
print("TVLs with close values:")
df3 = pd.DataFrame(
    close_tvls, columns=["Address", "Symbol", "TVL OLD", "TVL NEW"]
)
print(df3)

print("DEXSCREENER ANALYSIS")
print("TVLs with different values:")
df = pd.DataFrame(
    diff_tvls_dex, columns=["Address", "Symbol", "TVL NEW", "TVL DEX"]
)
df["Difference"] = df["TVL NEW"] - df["TVL DEX"]
df.sort_values(by=["Difference"], inplace=True, ascending=False)
print(df)
print("TVLs with same values:")
df2 = pd.DataFrame(
    same_tvls_dex, columns=["Address", "Symbol", "TVL NEW", "TVL DEX"]
)
print(df2)
print("TVLs with close values:")
df3 = pd.DataFrame(
    close_tvls_dex, columns=["Address", "Symbol", "TVL NEW", "TVL DEX"]
)
print(df3)
