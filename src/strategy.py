import math
import time
import threading
import numpy as np
import pandas as pd

from .uniwap_math import round_tick

from .provider import Provider
from .protocol_state import ProtocolState
from .position_manager import PositionManager


class Strategy:

    def __init__(self, provider: Provider, state: ProtocolState, position_manager: PositionManager):

        self.provider = provider
        self.state = state
        self.position_manager = position_manager

        self.evaluate = False
        self.thread = threading.Thread(target=self._evaluate)

    def _evaluate(self):

        # wait for first tick
        while self.state.current_tick is None:
            time.sleep(10)

        while self.evaluate:

            if not self.provider.backtest:
                time.sleep(60)

            past_swap_data = np.stack(self.state.swap_data, axis=0) if self.state.swap_data else np.array([])
            past_mint_data = np.stack(self.state.mint_data, axis=0) if self.state.mint_data else np.array([])
            past_burn_data = np.stack(self.state.burn_data, axis=0) if self.state.burn_data else np.array([])

            current_block = self.state.current_block
            current_tick = self.state.current_tick

            self._strategy(past_swap_data, past_mint_data, past_burn_data, current_block, current_tick)

    def _strategy(self, past_swap_data: np.ndarray, past_mint_data: np.ndarray, past_burn_data: np.ndarray, current_block: int, current_tick: int) -> None:

        """
        Implement your strategy here (closing and opening of positions)

        :param past_swap_data: contains the last swap data
        :param past_mint_data: contains the last mint data
        :param past_burn_data: contains the last burn data
        :param current_block: : contains the current block number
        :param current_tick: contains the current tick
        :return: None
        """

        # Simple example strategy: 
        #  - close all positions after 5 * 60 blocks (~ 1 hour assuming a block time of 12 seconds)
        #  - open a new position if no position is open AND the past 120 ticks are within 1 standard deviation of the current tick
        #  - tick range of new position is the standard deviation of the past 2 hours

        # evaluate open positions
        for index in self.position_manager.open_positions_index:
            if self.position_manager.positions_meta_data[index]["block"] + 60 * 5 <= current_block:
                self.position_manager.close_position(index)

        # consider every 5th block in order to get minute-by-minute data
        data = pd.DataFrame(past_swap_data)
        reduced_data = data.groupby(data.iloc[:,0] // 5).apply(lambda x: x.iloc[-1]).to_numpy()

        # not enough data to make informed decision
        if reduced_data.shape[0] < 120:
            return

        # consider the last 2 hours
        last_2_hours = reduced_data[-120:, self.state.TICK_INDEX]

        # calculate the standard deviation of the minute-by-minute tick change
        delta = np.diff(last_2_hours)
        std = np.std(delta)

        # too much volatility or already open position
        if std > 10 or len(self.position_manager.open_positions_index) > 0:
            time.sleep(2)
            return

        # open a new position -> extrapolate the minute-by-minute std to 1 hour
        upper_tick = round_tick((current_tick + std * math.sqrt(60)))
        lower_tick = round_tick((current_tick - std * math.sqrt(60)))
        
        self.position_manager.open_position(lower_tick, upper_tick, y_real=10**18)

    def start(self):
        self.evaluate = True
        self.thread.start()
    
    def stop(self):
        self.evaluate = False
        self.thread.join()
