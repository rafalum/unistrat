import os
import json
import math
import time
from web3 import Web3
from utils import get_contract

USDC_ETH_POOL_ADDRESS = "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"

contract = get_contract()

event_names = ["Swap", "Mint", "Burn"]

from_block = 17000001
to_block = 17020000
increment = 2000

for i in range(from_block, to_block, increment):

    print(f"{i}/{to_block}")

    for event_name in event_names:

        event_filter = contract.events[event_name].create_filter(fromBlock=i, toBlock=i+increment)

        # get all events that match the filter
        events = event_filter.get_all_entries()

        for event in events:
            with open(f"data/{event_name}.csv", "a") as f:
                if event_name == "Swap":
                    f.writelines(f"{event.blockNumber}, {event.args['tick']}, {event.args['liquidity']}, {event.args['sqrtPriceX96']}, {event.args['amount0']}, {event.args['amount1']}\n")
                else:
                    f.writelines(f"{event.blockNumber}, {event.args['tickLower']}, {event.args['tickUpper']}, {event.args['amount0']}, {event.args['amount1']}\n")
            
