#!/bin/bash

# Get the IPs associated with the domain
IPS=$(dig +short evm.kava.io)

for IP in $IPS; do
    if [[ $IP =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "Sending test request to IP: $IP"
        curl -s --max-time 5 -X POST --data '{"jsonrpc":"2.0","method":"web3_clientVersion","params":[],"id":1}' http://$IP:8545 > /dev/null
        if [ $? -eq 0 ]; then
            echo "Request to $IP succeeded."
        else
            echo "Request to $IP failed."
        fi
    else
        echo "Skipped non-IP string: $IP"
    fi
done
