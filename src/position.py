import math
import numpy as np

from .uniwap_math import tick_to_sqrt_price, tick_to_price

class Position:

    def __init__(self, init, lower, upper, liquidity, fee_growth_inside_0_last, fee_growth_inside_1_last) -> None:

        self.init_tick = init

        self.upper_tick = upper
        self.lower_tick = lower

        self.liquidity = liquidity

        self.fee_growth_inside_0_last = fee_growth_inside_0_last
        self.fee_growth_inside_1_last = fee_growth_inside_1_last

        self.token_id = None

    def __str__(self):

        return f"Lower Tick: {self.lower_tick}, Init Tick: {self.init_tick}, Upper Tick: {self.upper_tick}, Liquidity: {self.liquidity}"

    def tick_to_price(self, tick):
        return math.pow(1.0001, tick)

    
    def amount_x(self, current_tick, current_sqrt_price=None):

        price_lower_tick = tick_to_sqrt_price(self.lower_tick)
        price_upper_tick = tick_to_sqrt_price(self.upper_tick)

        # if the exact sqrt price is given, use it
        if current_sqrt_price:
            price_current_tick = current_sqrt_price
        else:
            price_current_tick = tick_to_sqrt_price(current_tick)


        if current_tick < self.lower_tick:
            value = 1 / price_lower_tick - 1 / price_upper_tick

        elif current_tick >= self.upper_tick:
            value = 0
        
        else:
            value = 1 / price_current_tick - 1 / price_upper_tick

        return self.liquidity * value
    
    def amount_y(self, current_tick, current_sqrt_price=None):

        price_lower_tick = tick_to_sqrt_price(self.lower_tick)
        price_upper_tick = tick_to_sqrt_price(self.upper_tick)

        # if the exact sqrt price is given, use it
        if current_sqrt_price:
            price_current_tick = current_sqrt_price
        else:
            price_current_tick = tick_to_sqrt_price(current_tick)

        if current_tick < self.lower_tick:
            value = 0

        elif current_tick >= self.upper_tick:
            value = price_upper_tick - price_lower_tick
        
        else:
            value = price_current_tick - price_lower_tick

        return self.liquidity * value

    # 
    #
    # @ret: value of the position in y
    def value_position(self, current_tick):

        price_lower_tick = tick_to_price(self.lower_tick)
        price_current_tick = tick_to_price(current_tick)
        price_upper_tick = tick_to_price(self.upper_tick)

        if current_tick < self.lower_tick:      # y fully depleted
            value = price_current_tick * (1 / math.sqrt(price_lower_tick) - 1 / math.sqrt(price_upper_tick))

        elif current_tick >= self.upper_tick:
            value = (math.sqrt(price_upper_tick) - math.sqrt(price_lower_tick))

        else:                                   # x fully depleted
            value = (2 * math.sqrt(price_current_tick) - math.sqrt(price_lower_tick) - price_current_tick / math.sqrt(price_upper_tick))
        
        return self.liquidity * value
    
    # 
    #
    # @ret: value if the initial amount were simply held in y
    def value_hold(self, current_tick):

        price_lower_tick = tick_to_price(self.lower_tick)
        price_current_tick = tick_to_price(current_tick)
        price_upper_tick = tick_to_price(self.upper_tick)
        price_init_tick = tick_to_price(self.init_tick)

        if self.init_tick < self.lower_tick:
            value = price_current_tick * (1 / math.sqrt(price_lower_tick) - 1 / math.sqrt(price_upper_tick))

        elif self.init_tick >= self.upper_tick:
            value = (math.sqrt(price_upper_tick) - math.sqrt(price_lower_tick))

        else:
            value = ((price_init_tick + price_current_tick) / math.sqrt(price_init_tick) - math.sqrt(price_lower_tick) - price_current_tick / math.sqrt(price_upper_tick))

        return self.liquidity * value
    
    def impermantent_loss(self, current_tick):

        v_pos = self.value_position(current_tick)
        v_hold = self.value_hold(current_tick)

        return (v_pos - v_hold) / v_hold
    
    # 
    #
    # @ret: accumulated fees of the position in y
    def accumulated_fees(self, current_tick, fee_growth_inside_0_present, fee_growth_inside_1_present):

        accumulated_fees_0 = self.liquidity * (fee_growth_inside_0_present - self.fee_growth_inside_0_last) * tick_to_price(current_tick)
        accumulated_fees_1 = self.liquidity * (fee_growth_inside_1_present - self.fee_growth_inside_1_last)

        return accumulated_fees_0, accumulated_fees_1

        





