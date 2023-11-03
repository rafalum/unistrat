import os
import time
import math
import psutil
import signal
import unittest
import subprocess

from src.uniwap_math import tick_to_price
from src.utils import get_contract, get_account, get_provider, get_env_variable, real_reservers_to_virtal_reserves
from src.position import Position
from src.provider import Provider

from test.utils import TestUtil

WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

class TestBurn(unittest.TestCase, TestUtil):

    def setUp(self):

        API_KEY = get_env_variable("PROVIDER_URL")
            
        # spin up Ethereum node
        self.node_process = subprocess.Popen(["npx", "hardhat", "node", "--fork", API_KEY])

        if self.node_process.returncode == None:
            print("Hardhat fork started successfully")
        else:
            print(f"Error starting Hardhat fork. Exit code: {self.node_process.returncode}")

        time.sleep(10)

        self.w3 = get_provider(test=True)
        self.account = get_account(test=True)

        self.pool_contract = get_contract("USDC_ETH_POOL", address="0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640", test=True)
        self.router_contract = get_contract("UNISWAP_ROUTER", address="0xE592427A0AEce92De3Edee1F18E0157C05861564", test=True)
        self.nft_contract = get_contract("NFT_POSITION_MANAGER", address="0xC36442b4a4522E871399CD717aBDD847Ab11FE88", test=True)

        self.token0_address = self.pool_contract.functions.token0().call()
        self.token1_address = self.pool_contract.functions.token1().call()
        self.fee = self.pool_contract.functions.fee().call()

        self.token0_contract = get_contract("token0", self.token0_address, test=True)
        self.token1_contract = get_contract("token1", self.token1_address, test=True) 

        self.token0_decimals = self.token0_contract.functions.decimals().call()
        self.token1_decimals = self.token1_contract.functions.decimals().call()

        self.token0_is_WETH = self.token0_address == WETH_ADDRESS
        self.token1_is_WETH = self.token1_address == WETH_ADDRESS
        

    def tearDown(self):
        
        # stop Ethereum node
        node_process_pid = self.node_process.pid

        parent_process = psutil.Process(node_process_pid)
        child_processes = parent_process.children(recursive=True)

        self.node_process.terminate()

        # kill all child processes
        for child in child_processes:
            if parent_process.pid != child.pid:
                os.kill(child.pid, signal.SIGTERM)

    def testBurn(self):

        provider = Provider(pool_address="0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640", network="mainnet", local=True)

        current_block = provider.get_current_block()
        current_tick = provider.get_current_tick(current_block)
        current_sqrt_price = provider.get_current_sqrt_price(current_block)

        lower_tick = int(current_tick // 10 * 10 - 100)
        upper_tick = int(current_tick // 10 * 10 + 100)

        y_real = 10 * 10**self.token1_decimals
        x_virt, y_virt, x_real = real_reservers_to_virtal_reserves(lower_tick, upper_tick, current_tick, current_sqrt_price, y_real=y_real)
        liquidity = math.sqrt(x_virt * y_virt)

        position = Position(current_tick, lower_tick, upper_tick, liquidity, None, None)
        _, txn_receipt = provider.mint_position(position, current_tick, current_sqrt_price)

        amount_token0 = int.from_bytes(txn_receipt["logs"][0]["data"][-32:])
        amount_token1 = int.from_bytes(txn_receipt["logs"][1]["data"][-32:])

        token_id = int.from_bytes(txn_receipt["logs"][3]["topics"][-1], byteorder="big")

        position.token_id = token_id

        current_block = provider.get_current_block()
        tick_before_burn = provider.get_current_tick(current_block)
        current_sqrt_price = provider.get_current_sqrt_price(current_block)

        # create dummy swaps

        # define a trader account: this is the second test private key from the hardhat node
        trader = self.w3.eth.account.from_key("0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d")

        # convert ETH to token1 if necessary
        if not self.token1_is_WETH:
            self._swap(WETH_ADDRESS, self.token1_address, 1000 * self.token1_decimals, True, trader)

        # Swap 1: from token1 to token0
        self._swap(self.token1_address, self.token0_address, 1000 * 10**self.token1_decimals, self.token1_is_WETH, trader)

        current_block = provider.get_current_block()
        sqrt_price_after_swap1 = provider.get_current_sqrt_price(current_block)

        self.assertGreater(sqrt_price_after_swap1, current_sqrt_price)

        # Swap 2: from token 0 to token1
        self._approve_token(self.router_contract.address, trader, int((999.9 * 10**self.token1_decimals) / math.pow(sqrt_price_after_swap1 / 2**96, 2)), True)
        self._swap(self.token0_address, self.token1_address, int((999.9 * 10**self.token1_decimals) / math.pow(sqrt_price_after_swap1 / 2**96, 2)), False, trader)

        current_block = provider.get_current_block()
        sqrt_price_after_swap2 = provider.get_current_sqrt_price(current_block)

        self.assertLess(sqrt_price_after_swap2, sqrt_price_after_swap1)

        # Burn the position
        burn_tx, burn_tx_receipt, collect_tx_receipt = provider.burn_position(position, tick_before_burn)

        fees_token0 = collect_tx_receipt.logs[3].data[-64:-32]
        fees_token1 = collect_tx_receipt.logs[3].data[-32:]

        fees_token0 = int.from_bytes(fees_token0, byteorder='big')
        fees_token1 = int.from_bytes(fees_token1, byteorder='big')

        self.assertGreater(fees_token0, 0)
        self.assertGreater(fees_token1, 0)

        current_block = provider.get_current_block()
        tick_after_burn = provider.get_current_tick(current_block)

        self.assertEqual(tick_after_burn, tick_before_burn)

        acquired_fees_in_token0 = (fees_token0 - amount_token0) + (fees_token1 - amount_token1) / tick_to_price(tick_after_burn)

        self.assertGreater(acquired_fees_in_token0, 0)

