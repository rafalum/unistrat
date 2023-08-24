import os
import math
import json
import numpy as np

from web3 import Web3
from dotenv import load_dotenv

from uniwap_math import calculate_fee_inside, tick_to_price, tick_to_sqrt_price

load_dotenv()

USDC_ETH_POOL_ADDRESS = "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"
WBTC_ETH_POOL_ADDRESS = "0xCBCdF9626bC03E24f779434178A73a0B4bad62eD"

def get_env_variable(var_name):
    return os.environ.get(var_name)

def get_provider():
    provider_url = get_env_variable("MAINNET_PROVIDER")

    return Web3(Web3.HTTPProvider(provider_url))

def get_contract():
    w3 = get_provider()

    return w3.eth.contract(address=USDC_ETH_POOL_ADDRESS, abi=load_abi("pool"))

def load_abi(name: str) -> str:
    path = f"{os.path.dirname(os.path.abspath(__file__))}/../assets/"
    with open(os.path.abspath(path + f"{name}.json")) as f:
        abi: str = json.load(f)
    return abi


def real_reservers_to_virtal_reserves(lower_tick, upper_tick, current_tick, x_real=None, y_real=None):

    lower_sqrtPrice = tick_to_sqrt_price(lower_tick)
    current_sqrtPrice = tick_to_sqrt_price(current_tick)
    upper_sqrtPrice = tick_to_sqrt_price(upper_tick)

    if y_real:
        y_real_inv = math.pow(y_real, -1)

        liquidity_inv = y_real_inv * (current_sqrtPrice - lower_sqrtPrice)
        liquidity = math.pow(liquidity_inv, -1)

        real = liquidity *(1 / current_sqrtPrice - 1 / upper_sqrtPrice) # x_real
        
    elif x_real:
        x_real_inv = math.pow(x_real, -1)

        liquidity_inv = x_real_inv * (1 / current_sqrtPrice - 1 / upper_sqrtPrice)
        liquidity = math.pow(liquidity_inv, -1)

        real = liquidity * (current_sqrtPrice * lower_sqrtPrice) # y_real

    else:
        return None, None

    x_virt = liquidity / current_sqrtPrice
    y_virt = liquidity * current_sqrtPrice

    return x_virt, y_virt, real

def virtual_reserves_to_real_reserves(current_tick, liquidity):

    lower_sqrtPrice = tick_to_sqrt_price(current_tick - 5)
    sqrtPrice = tick_to_sqrt_price(current_tick)
    upper_sqrtPrice = tick_to_sqrt_price(current_tick + 5)

    x_virt = liquidity / sqrtPrice
    y_virt = liquidity * sqrtPrice

    x_real = x_virt - liquidity / upper_sqrtPrice
    y_real = y_virt - liquidity * lower_sqrtPrice

    return x_real, y_real
    

def total_value_in_tick(current_tick, sqrtPrice, liquidity):

    lower_sqrtPrice = tick_to_sqrt_price(current_tick - 5)
    upper_sqrtPrice = tick_to_sqrt_price(current_tick + 5)

    x_virt = liquidity / sqrtPrice
    y_virt = liquidity * sqrtPrice

    x_real = x_virt - liquidity / upper_sqrtPrice
    y_real = y_virt - liquidity * lower_sqrtPrice

    return x_real, y_real

def get_fee_growth_inside_last(lower_tick_state, upper_tick_state, lower_tick, upper_tick, current_tick, fee_growth_global_0, fee_growth_global_1):
        
    upper_tick_fee_growth_outside_0 = upper_tick_state[2] / (1 << 128)
    upper_tick_fee_growth_outside_1 = upper_tick_state[3] / (1 << 128)
    
    lower_tick_fee_growth_outside_0 = lower_tick_state[2] / (1 << 128)
    lower_tick_fee_growth_outside_1 = lower_tick_state[3] / (1 << 128)

    fee_growth_inside_0_last = calculate_fee_inside(lower_tick, upper_tick, current_tick, lower_tick_fee_growth_outside_0, upper_tick_fee_growth_outside_0, fee_growth_global_0)
    fee_growth_inside_1_last = calculate_fee_inside(lower_tick, upper_tick, current_tick, lower_tick_fee_growth_outside_1, upper_tick_fee_growth_outside_1, fee_growth_global_1)

    return fee_growth_inside_0_last, fee_growth_inside_1_last

def get_volume_in_last_blocks(swap_data, block_interval_size=12, number_volume=64):

    swap_data_np = np.stack(swap_data, axis=0)

    last_block = int(swap_data_np[-1, 0])

    volume = []
    block_interval = []
    for _ in range(number_volume):

        interval_lower_bound = last_block - last_block % block_interval_size
        interval_upper_bound = last_block + 1

        # Selects all rows that are in the current interval
        swap_data_last_interval = swap_data_np[(swap_data_np[:, 0] >= interval_lower_bound) & (swap_data_np[:, 0] < interval_upper_bound)]

        # Sum all swap volumes of y
        volume.append(np.sum(np.abs(swap_data_last_interval[:, 5])) / 10**18)

        block_interval.append((interval_lower_bound, interval_upper_bound))

        last_block = interval_lower_bound - 1
            
    return volume, block_interval

def get_total_value_locked_in_tick(tick, liquidity):

    x_real, y_real = virtual_reserves_to_real_reserves(tick, liquidity)

    total_value_locked = x_real * tick_to_price(tick) / 10**18 + y_real / 10**18

    return total_value_locked

def get_value_locked_for_tick_range(current_tick, current_liquidity, tick_states, tick_range=100):
        
    current_tick_rounded = current_tick // 10 * 10

    liquidities = [None for _ in range(0, 2 * tick_range + 10, 10)]
    ticks = [current_tick - i for i in range(10, tick_range + 10, 10)] + [current_tick] + [current_tick + i for i in range(10, tick_range + 10, 10)]

    liquidities[tick_range // 10] = current_liquidity

    liquidity_tick_below = current_liquidity
    liquidity_tick_above = current_liquidity


    for i in range(0, tick_range, 10):

        tick_state_below = tick_states[current_tick_rounded - i]
        tick_state_above = tick_states[current_tick_rounded + 10 + i]

        if tick_state_below:
            liquidity_net_below = tick_state_below[1]
            liquidity_tick_below = liquidity_tick_below - liquidity_net_below
            liquidities[(tick_range - i - 10) // 10] = liquidity_tick_below
        else:
            liquidities[(tick_range - i - 10) // 10] = liquidity_tick_below
            
        if tick_state_above:
            liquidity_net_above = tick_state_above[1]
            liquidity_tick_above = liquidity_tick_above + liquidity_net_above
            liquidities[(tick_range + i + 10) // 10] = liquidity_tick_above
        else:
            liquidities[(tick_range + i + 10) // 10] = liquidity_tick_above


    value_locked = []
    for tick, liquidity in zip(ticks, liquidities):
        value_locked.append(get_total_value_locked_in_tick(tick, liquidity))

    return value_locked