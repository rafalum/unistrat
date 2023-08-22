import math
import time
import threading
import numpy as np
import pandas as pd
from web3 import Web3

from provider import Provider
from protocol_state import ProtocolState
from position_manager import PositionManager

BLOCK_INDEX = 0
TICK_INDEX = 1
LIQUIDITY_INDEX = 2

NUM_BLOCKS = 5

class Strategy:

    def __init__(self, provider: Provider, state: ProtocolState, position_manager: PositionManager):

        self.provider = provider
        self.state = state
        self.position_manager = position_manager

        self.evaluate = True
        self.thread = threading.Thread(target=self._evaluate)
        

    def _evaluate(self):

        while self.evaluate:

            if not self.provider.backtest:
                time.sleep(60)

            past_data = np.stack(self.state.swap_data, axis=0)

            last_block = int(past_data[-1, BLOCK_INDEX])
            last_tick = int(past_data[-1, TICK_INDEX])

            # evaluate open positions
            for index in self.position_manager.open_positions_index:
                if self.position_manager.positions_meta_data[index]["block"] + 60 * 5 <= last_block:
                    self.position_manager.close_position(index)

            # evaluate new position
            data = pd.DataFrame(past_data)
            reduced_data = data.groupby(data.iloc[:,0] // 5).apply(lambda x: x.iloc[-1]).to_numpy()

            # not enough data to make informed decision
            if reduced_data.shape[0] < 120:
                #print("not engough data")
                continue

            past_ticks = reduced_data[-120:, TICK_INDEX]

            delta = np.diff(past_ticks)
            std = np.std(delta)

            if std > 10 or len(self.position_manager.open_positions_index) > 0:
                time.sleep(2)
                continue

            upper_tick = int((last_tick + std * math.sqrt(60)) // 10 * 10)
            lower_tick = int((last_tick - std * math.sqrt(60)) // 10 * 10)
            
            self.position_manager.open_position(lower_tick, upper_tick)

    def start(self):
        self.evaluate = True
        self.thread.start()
    
    def stop(self):
        self.evaluate = False
        self.thread.join()
