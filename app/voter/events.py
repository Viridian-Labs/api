import time
import json
from blinker import signal
from web3 import Web3, exceptions
from app.settings import (
    VOTER_ADDRESS,    
    LOGGER,
    WEB3_PROVIDER_URI
)

eventGaugeCreated = signal('GaugeCreated')
eventGaugeKilled = signal('GaugeKilled')


class EventListener:

    def __init__(self):
        # Connect the 'on_event_received' method to the 'event_received' signal
        eventGaugeCreated.connect(self.on_event_received)
        eventGaugeKilled.connect(self.on_event_received)

    def on_event_received(self, sender, event):
        print(f"Received event in EventListener: {event}")
        

class VoterContractMonitor:

    def __init__(self, contract_address, node_endpoint):
        """
        Initializes the VoterContractMonitor with the provided contract address and node endpoint.
        It sets up the web3 instance, retrieves the current block, and initializes the contract instance.
        """
        self.w3 = Web3(Web3.HTTPProvider(node_endpoint))
        self.contract_address = contract_address
        self.last_processed_block = self.get_current_block()

        LOGGER.info(
            "Starting VoterContractMonitor. Last Block: %s",
            self.last_processed_block)

        with open('app/abis/Voter.sol/abi.json', 'r') as file:
            self.CONTRACT_ABI = json.load(file)
            self.contract = self.w3.eth.contract(address=self.contract_address, abi=self.CONTRACT_ABI)

    def get_current_block(self):
        """
        Retrieves the current block number from the Ethereum node.
        Returns None if there's a connection error.
        """
        try:
            return self.w3.eth.blockNumber
        except exceptions.ConnectionError:
            LOGGER.error(
                "Error: Unable to connect to Ethereum node %s",
                self.w3.eth.blockNumber)
            return None

    def process_events(self):
        """
        Processes the events from the contract starting from the last processed block until the current block.
        Updates the last processed block after processing.
        """
        current_block = self.get_current_block()
        if not current_block:
            return

        event_names = [event['name'] for event in self.CONTRACT_ABI if event['type'] == 'event']

        for event_name in event_names:
            try:
                event = getattr(self.contract.events, event_name)
                for log in event.getPastEvents(fromBlock=self.last_processed_block, toBlock=current_block):
                    self.handle_event(log)
            except exceptions.ContractLogicError as e:                
                LOGGER.error(
                    "Error processing %s %s",
                     event_name, e)

        self.last_processed_block = current_block


    def handle_event(self, event):
        """
        Handles a single event log.
        Currently, it just prints the event. This can be extended to include custom processing.
        """
        print(event)  
        


    def monitor(self):
        """
        Monitors the events continuously.
        It waits for 30 seconds between each check and processes any new events.
        """
        while True:
            try:
                time.sleep(30)  
                self.process_events()
            except Exception as e:
                LOGGER.error("Error processing %s", e)

if __name__ == "__main__":
    """
    Main execution point. Initializes the VoterContractMonitor and starts monitoring.
    """
    listener = EventListener()
    voter_monitor = VoterContractMonitor(contract_address=VOTER_ADDRESS, node_endpoint=WEB3_PROVIDER_URI)
    voter_monitor.monitor()
