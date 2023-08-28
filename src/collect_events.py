import os
import json
import math
import time
from web3 import Web3

from src.utils import get_contract

def collect_events(contract, from_block, to_block, events=["Swap", "Mint", "Burn"]):

    increment = min(2000, to_block - from_block)
    for i in range(from_block, to_block, increment):

        print(f"{i}/{to_block}")

        for event_name in events:

            event_filter = contract.events[event_name].create_filter(fromBlock=i, toBlock=i+increment)

            # get all events that match the filter
            event_data = event_filter.get_all_entries()

            for event in event_data:
                with open(f"data/{event_name}.csv", "a") as f:
                    if event_name == "Swap":
                        f.writelines(f"{event.blockNumber}, {event.args['tick']}, {event.args['liquidity']}, {event.args['sqrtPriceX96']}, {event.args['amount0']}, {event.args['amount1']}\n")
                    else:
                        f.writelines(f"{event.blockNumber}, {event.args['tickLower']}, {event.args['tickUpper']}, {event.args['amount0']}, {event.args['amount1']}\n")


if __name__ == "__main__":
    contract = get_contract()
    collect_events(contract, 17000001, 17500001)
