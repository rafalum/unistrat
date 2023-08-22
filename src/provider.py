import numpy as np
from typing import Tuple, List, Union

BLOCK_INDEX = 0


class Provider:
    def __init__(self, provider, contract, backtest=False, data=None):

        if backtest and not data:
            raise ValueError("Backtest set to true -> please specify data file")

        self.provider = provider
        self.contract = contract

        self.backtest = backtest

        if backtest:
            self.data = np.loadtxt(data, delimiter=",", dtype=float)
            self.block_number = self.data[0, 0]
  

    def get_tick_state(self, tick, block_number) -> List[Union[int, bool]]:

        tick_state = self.contract.functions.ticks(tick).call(block_identifier=int(block_number))

        if tick_state[-1]:
            return tick_state
        else:
            return None
        
    def get_current_block(self) -> int:

        if self.backtest:
            current_block = self.block_number
            self.block_number += 1
            return current_block
        else:
            return self.provider.eth.block_number
        
    def get_events(self, block_number, type):

        if self.backtest:
            events = self.data[self.data[:, BLOCK_INDEX] == block_number]
            event_data = events.tolist()
        else:
            event_filter = self.contract.events[type].create_filter(fromBlock=block_number, toBlock=block_number+1)
            events = event_filter.get_all_entries()
            
            event_data = []
            for event in events:
                event_data.append([event.blockNumber, event.args['tick'], event.args['liquidity'], event.args['sqrtPriceX96'], event.args['amount0'], event.args['amount1']])

        return event_data
    
    def get_growth_global(self, block_number) -> Tuple:

        fee_growth_global_0 = self.contract.functions.feeGrowthGlobal0X128().call(block_identifier=int(block_number)) / (1 << 128)
        fee_growth_global_1 = self.contract.functions.feeGrowthGlobal1X128().call(block_identifier=int(block_number)) / (1 << 128)

        return fee_growth_global_0, fee_growth_global_1
