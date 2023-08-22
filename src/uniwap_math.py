import math


def calculate_fee_above(tick, current_tick, fee_growth_outside, fee_growth_global):

    if current_tick >= tick:
        return fee_growth_global - fee_growth_outside
    else:
        return fee_growth_outside
    
def calculate_fee_below(tick, current_tick, fee_growth_outside, fee_growth_global):

    if current_tick >= tick:
        return fee_growth_outside
    else:

        return fee_growth_global - fee_growth_outside
    
def calculate_fee_inside(lower_tick, upper_tick, current_tick, lower_tick_fee_growth_outside, upper_tick_fee_growth_outside, fee_growth_global):

    fee_below = calculate_fee_below(lower_tick, current_tick, lower_tick_fee_growth_outside, fee_growth_global)
    fee_above = calculate_fee_above(upper_tick, current_tick, upper_tick_fee_growth_outside, fee_growth_global)

    return fee_growth_global - fee_below - fee_above


def tick_to_sqrt_price(tick):
    return math.pow(1.0001, tick // 2)

def tick_to_price(tick):
    return math.pow(1.0001, tick)