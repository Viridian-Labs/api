import json

import requests

json1_data = requests.get(
    "https://api.equilibrefinance.com/api/v1/assets"
).json()["data"]
json2_data = requests.get("http://localhost:8000/api/v1/assets").json()["data"]

with open("json1.txt", "w", encoding="utf-8") as f:
    json.dump({"data": json1_data}, f)

with open("json2.txt", "w", encoding="utf-8") as f:
    json.dump({"data": json2_data}, f)

with open("json1.txt", "r", encoding="utf-8") as f:
    json1_data = json.load(f)["data"]

with open("json2.txt", "r", encoding="utf-8") as f:
    json2_data = json.load(f)["data"]

tokens1 = {token["address"] for token in json1_data}
tokens2 = {token["address"] for token in json2_data}

tokens_only_in_json1 = tokens1 - tokens2
print("Tokens only in json1:", tokens_only_in_json1)

for token in json1_data:
    if token["address"] in tokens2:
        token2 = next(
            t for t in json2_data if t["address"] == token["address"]
        )

        if token["price"] != token2["price"]:
            print(
                f"Token {token['symbol']} has different prices: "
                f"{token['price']} (in json1) vs"
                f" {token2['price']} (in json2)"
            )
    else:
        print(f"Token {token['symbol']} is present in json1 but not in json2")

tokens_only_in_json2 = tokens2 - tokens1
print("Tokens only in json2:", tokens_only_in_json2)
