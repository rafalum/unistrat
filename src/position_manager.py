import math
import logging

from .position import Position
from .provider import Provider
from .protocol_state import ProtocolState

from .utils import get_fee_growth_inside_last, real_reservers_to_virtal_reserves


class PositionManager:
    def __init__(self, provider: Provider, state: ProtocolState):

        self.provider = provider
        self.state = state
        
        self.positions = []
        self.positions_meta_data = []

        self.open_positions_index = []
        self.closed_positions_index = []

        self.performance = []

        self.logger = logging.getLogger('logger1')
        self.logger.setLevel(logging.INFO)
        handler = logging.FileHandler('src/logs/position.log')
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def open_position(self, lower_tick, upper_tick) -> None:

        current_block = self.state.current_block
        current_tick = self.provider.get_current_tick(current_block)

        upper_tick_state = self.provider.get_tick_state(upper_tick, current_block)
        lower_tick_state = self.provider.get_tick_state(lower_tick, current_block)

        if not upper_tick_state or not lower_tick_state:
            # tick not initialized -> discard position if simulation
            if self.provider.backtest:
                return
        
        fee_growth_global_0, fee_growth_global_1 = self.provider.get_growth_global(current_block)

        fee_growth_inside_0_last, fee_growth_inside_1_last = get_fee_growth_inside_last(lower_tick_state, upper_tick_state, lower_tick, upper_tick, current_tick, fee_growth_global_0, fee_growth_global_1)

        x_virt, y_virt, x_real = real_reservers_to_virtal_reserves(lower_tick, upper_tick, current_tick, y_real=10**18)
        liquidity = math.sqrt(x_virt * y_virt)

        position = Position(current_tick, lower_tick, upper_tick, liquidity, fee_growth_inside_0_last, fee_growth_inside_1_last)

        self.logger.info(f"Opened position: {lower_tick} - {upper_tick}")
        
        self.positions.append(position)
        self.open_positions_index.append(len(self.positions) - 1)
        self.positions_meta_data.append({"block": current_block, "tick": current_tick})

        return

    def close_position(self, index) -> None:

        position = self.positions[index]

        upper_tick = position.upper_tick
        lower_tick = position.lower_tick

        current_block = self.state.current_block
        current_tick = self.provider.get_current_tick(current_block)

        upper_tick_state = self.provider.get_tick_state(upper_tick, current_block)
        lower_tick_state = self.provider.get_tick_state(lower_tick, current_block)

        if not upper_tick_state or not lower_tick_state:
            # tick not initialized -> discard position if simulation
            if self.provider.backtest:
                self.open_positions_index.remove(index)
                self.logger.info(f"Discarded position: {position.lower_tick} - {position.upper_tick}")
                return
            
        fee_growth_global_0, fee_growth_global_1 = self.provider.get_growth_global(current_block)

        fee_growth_inside_0_last, fee_growth_inside_1_last = get_fee_growth_inside_last(lower_tick_state, upper_tick_state, lower_tick, upper_tick, current_tick, fee_growth_global_0, fee_growth_global_1)

        accumulated_fees = position.accumulated_fees(current_tick, fee_growth_inside_0_last, fee_growth_inside_1_last)
        value_hold = position.value_hold(current_tick)
        value_position = position.value_position(current_tick)

        self.performance.append({"accumulated_fees": accumulated_fees, "value_hold": value_hold, "value_position": value_position})

        self.logger.info(f"Closed position: {position.lower_tick} - {position.upper_tick}")

        self.open_positions_index.remove(index)
        self.closed_positions_index.append(index)

        return
