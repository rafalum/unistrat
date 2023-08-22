import os
import math
import json

from web3 import Web3
from dotenv import load_dotenv

from uniwap_math import calculate_fee_inside

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

def tick_to_sqrtPrice(tick):
    return math.pow(1.0001, tick // 2)

def real_reservers_to_virtal_reserves(lower_tick, upper_tick, current_tick, x_real=None, y_real=None):

    lower_sqrtPrice = tick_to_sqrtPrice(lower_tick)
    current_sqrtPrice = tick_to_sqrtPrice(current_tick)
    upper_sqrtPrice = tick_to_sqrtPrice(upper_tick)

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
    

def total_value_in_tick(current_tick, sqrtPrice, liquidity):

    lower_sqrtPrice = tick_to_sqrtPrice(current_tick - 5)
    upper_sqrtPrice = tick_to_sqrtPrice(current_tick + 5)

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