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

    def open_position(self, lower_tick, upper_tick, x_real=None, y_real=None) -> None:

        current_block = self.state.current_block
        current_tick = self.provider.get_current_tick(current_block)
        current_sqrt_price = self.provider.get_current_sqrt_price(current_block)

        upper_tick_state = self.provider.get_tick_state(upper_tick, current_block)
        lower_tick_state = self.provider.get_tick_state(lower_tick, current_block)

        if not upper_tick_state or not lower_tick_state:
            # tick not initialized -> discard position if simulation
            if self.provider.backtest:
                return
        
        fee_growth_global_0, fee_growth_global_1 = self.provider.get_growth_global(current_block)

        fee_growth_inside_0_last, fee_growth_inside_1_last = get_fee_growth_inside_last(lower_tick_state, upper_tick_state, lower_tick, upper_tick, current_tick, fee_growth_global_0, fee_growth_global_1)

        if x_real is None:
            x_virt, y_virt, x_real = real_reservers_to_virtal_reserves(lower_tick, upper_tick, current_tick, current_sqrt_price, y_real=y_real)
        elif y_real is None:
            x_virt, y_virt, x_real = real_reservers_to_virtal_reserves(lower_tick, upper_tick, current_tick, current_sqrt_price, x_real=x_real)
        
        liquidity = math.sqrt(x_virt * y_virt)

        position = Position(current_tick, lower_tick, upper_tick, liquidity, fee_growth_inside_0_last, fee_growth_inside_1_last)

        if self.provider.backtest or self.provider.sim:

            actual_amount_token0 = x_real
            actual_amount_token1 = y_real

            token_id = len(self.positions) - 1

            position.token_id = token_id

        else:

            mint_tx_hash, mint_tx_receipt = self.provider.mint_position(position, current_tick, current_sqrt_price)

            actual_amount_token0 = int.from_bytes(mint_tx_receipt["logs"][0]["data"][-32:])
            actual_amount_token1 = int.from_bytes(mint_tx_receipt["logs"][1]["data"][-32:])

            token_id = int.from_bytes(mint_tx_receipt["logs"][3]["topics"][-1], byteorder="big")

            position.token_id = token_id

        self.logger.info(f"Opened position - TokenID: {token_id} - Range: {lower_tick} - {upper_tick}")
            
        self.positions.append(position)
        self.open_positions_index.append(len(self.positions) - 1)
        self.positions_meta_data.append({"block": current_block, "tick": current_tick, "token_id": token_id, "amount_token0": actual_amount_token0, "amount_token1": actual_amount_token1})

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

        # TODO: get actual performance metrics from the blockchain if not simulation
        accumulated_fees = position.accumulated_fees(current_tick, fee_growth_inside_0_last, fee_growth_inside_1_last)
        value_hold = position.value_hold(current_tick)
        value_position = position.value_position(current_tick)

        self.performance.append({"accumulated_fees": accumulated_fees, "value_hold": value_hold, "value_position": value_position})

        if self.provider.backtest or self.provider.sim:
            burn_tx_receipt = None
            collect_tx_receipt = None
        
        else:
            burn_tx, burn_tx_receipt, collect_tx_receipt = self.provider.burn_position(position, current_tick)

        self.logger.info(f"Closed position: {position.lower_tick} - {position.upper_tick}")

        self.open_positions_index.remove(index)
        self.closed_positions_index.append(index)

        return
