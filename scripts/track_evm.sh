#!/bin/bash

# Create logs directory if it doesn't exist
mkdir -p logs

# Debug log file
DEBUG_LOG="logs/debug_log.txt"

# Get the IPs associated with the domain
IPS=$(dig +short evm.kava.io)

echo "Script started at: $(date)" | tee -a $DEBUG_LOG

# Start tcpdump to monitor connections to the IPs
for IP in $IPS; do
    if [[ $IP =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "Monitoring connections to IP: $IP" | tee -a $DEBUG_LOG
        sudo tcpdump -i any port 8545 or port 8546 -w "logs/outputfile_${IP}_$(date +%Y%m%d).pcap" &
    else
        echo "Skipped non-IP string: $IP" | tee -a $DEBUG_LOG
    fi
done

# Wait until user stops the script
echo "Press Ctrl+C to stop monitoring..."
wait
