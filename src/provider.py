import numpy as np
from typing import Tuple, List, Union

from .utils import get_contract, get_provider

from .position import Position

BLOCK_INDEX = 0


class Provider:
    def __init__(self, backtest=False, swap_data=None, mint_data=None, burn_data=None):

        if backtest and not swap_data:
            raise ValueError("Backtest set to true -> please specify data file")

        self.provider = get_provider()
        self.pool_contract = get_contract("USDC_ETH_POOL_ADDRESS")
        self.nft_contract = get_contract("NFT_POSITION_MANAGER")

        self.backtest = backtest

        if backtest:
            self.swap_data = np.loadtxt(swap_data, delimiter=",", dtype=float)
            self.mint_data = np.loadtxt(mint_data, delimiter=",", dtype=float)
            self.burn_data = np.loadtxt(burn_data, delimiter=",", dtype=float)

            self.block_number = self.swap_data[0, 0]
            self.last_block = self.swap_data[-1, 0]
  
    
    def get_tick_state(self, tick, block_number) -> List[Union[int, bool]]:

        tick_state = self.pool_contract.functions.ticks(int(tick)).call(block_identifier=int(block_number))

        if tick_state[-1]:
            return tick_state
        else:
            return None
        
    def get_current_block(self) -> int:

        if self.backtest:
            current_block = self.block_number
            self.block_number += 1

            if current_block > self.last_block:
                return -1
            
            return current_block
        else:
            return self.provider.eth.block_number
        
    def get_events(self, block_number, type):

        if self.backtest:
            if type == "Swap":
                swap_events = self.swap_data[self.swap_data[:, BLOCK_INDEX] == block_number]
                event_data = swap_events.tolist()
            elif type == "Mint":
                mint_events = self.mint_data[self.mint_data[:, BLOCK_INDEX] == block_number]
                event_data = mint_events.tolist()
            elif type == "Burn":
                burn_events = self.burn_data[self.burn_data[:, BLOCK_INDEX] == block_number]
                event_data = burn_events.tolist()

        else:
            event_filter = self.pool_contract.events[type].create_filter(fromBlock=block_number, toBlock=block_number+1)
            events = event_filter.get_all_entries()
            
            event_data = []
            for event in events:
                if type == "Swap":
                    event_data.append([event.blockNumber, event.args['tick'], event.args['liquidity'], event.args['sqrtPriceX96'], event.args['amount0'], event.args['amount1']])
                elif type == "Mint":
                    event_data.append([event.blockNumber, event.args['tickLower'], event.args['tickUpper'], event.args['amount0'], event.args['amount1']])
                elif type == "Burn":
                    event_data.append([event.blockNumber, event.args['tickLower'], event.args['tickUpper'], event.args['amount0'], event.args['amount1']])

        return event_data
    
    def get_growth_global(self, block_number) -> Tuple:

        fee_growth_global_0 = self.pool_contract.functions.feeGrowthGlobal0X128().call(block_identifier=int(block_number)) / (1 << 128)
        fee_growth_global_1 = self.pool_contract.functions.feeGrowthGlobal1X128().call(block_identifier=int(block_number)) / (1 << 128)

        return fee_growth_global_0, fee_growth_global_1
    
    def get_liquidity(self, block_number) -> int:

        liquidity = self.pool_contract.functions.liquidity().call(block_identifier=int(block_number))

        return liquidity
