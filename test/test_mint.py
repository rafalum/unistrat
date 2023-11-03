import os
import time
import math
import psutil
import signal
import unittest
import subprocess
from web3 import Web3

from src.utils import get_contract, get_account, get_provider, get_env_variable, real_reservers_to_virtal_reserves
from src.position import Position
from src.provider import Provider

from test.utils import TestUtil

WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

class TestMint(unittest.TestCase, TestUtil):

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

    def testMintPositionOnlyToken0(self):

        balance_token0 = self.token0_contract.functions.balanceOf(self.account.address).call()
        balance_token1 = self.token1_contract.functions.balanceOf(self.account.address).call()

        self.assertEqual(balance_token0, 0)
        self.assertEqual(balance_token1, 0)

        if self.token0_address == WETH_ADDRESS:
            self._wrap_token(self.token0_contract, 100 * 10**18, self.account)
        else:
            self._swap(WETH_ADDRESS, self.token0_address, 100 * 10**18, True, self.account)

        balance_token0 = self.token0_contract.functions.balanceOf(self.account.address).call()
        balance_token1 = self.token1_contract.functions.balanceOf(self.account.address).call()

        self.assertEqual(balance_token1, 0)
        self.assertGreater(balance_token0, 0)

        provider = Provider(pool_address="0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640", network="mainnet", local=True)

        current_block = provider.get_current_block()
        current_tick = provider.get_current_tick(current_block)
        current_sqrt_price = provider.get_current_sqrt_price(current_block)

        lower_tick = int(current_tick // 10 * 10 - 100)
        upper_tick = int(current_tick // 10 * 10 + 100)

        y_real = 1 * 10**self.token1_decimals
        x_virt, y_virt, x_real = real_reservers_to_virtal_reserves(lower_tick, upper_tick, current_tick, current_sqrt_price, y_real=y_real)
        liquidity = math.sqrt(x_virt * y_virt)

        position = Position(current_tick, lower_tick, upper_tick, liquidity, None, None)

        expected_amount_token0 = position.amount_x(current_tick, current_sqrt_price)
        expected_amount_token1 = position.amount_y(current_tick, current_sqrt_price)

        _, txn_receipt = provider.mint_position(position, current_tick, current_sqrt_price)

        token_id = int.from_bytes(txn_receipt["logs"][3]["topics"][-1], byteorder="big")

        actual_amount_token0 = int.from_bytes(txn_receipt["logs"][0]["data"][-32:])
        actual_amount_token1 = int.from_bytes(txn_receipt["logs"][1]["data"][-32:])

        actual_liquidity = int.from_bytes(txn_receipt["logs"][4]["data"][:32])

        # TODO: fix: delta should be way smaller
        self.assertAlmostEqual(expected_amount_token0, actual_amount_token0, delta=100*10**self.token0_decimals)
        self.assertAlmostEqual(expected_amount_token1, actual_amount_token1, delta=0.001*10**self.token1_decimals)

        self.assertAlmostEqual(liquidity, actual_liquidity, delta=0.001*10**self.token1_decimals)

    def testMintPositionOnlyToken1(self):

        balance_token0 = self.token0_contract.functions.balanceOf(self.account.address).call()
        balance_token1 = self.token1_contract.functions.balanceOf(self.account.address).call()

        self.assertEqual(balance_token0, 0)
        self.assertEqual(balance_token1, 0)

        if self.token1_address == WETH_ADDRESS:
            self._wrap_token(self.token1_contract, 100 * 10**18, self.account)
        else:
            self._swap(WETH_ADDRESS, self.token1_address, 100 * 10**18, True, self.account)

        balance_token0 = self.token0_contract.functions.balanceOf(self.account.address).call()
        balance_token1 = self.token1_contract.functions.balanceOf(self.account.address).call()

        self.assertEqual(balance_token0, 0)
        self.assertGreater(balance_token1, 0)

        provider = Provider(pool_address="0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640", network="mainnet", local=True)

        current_block = provider.get_current_block()
        current_tick = provider.get_current_tick(current_block)
        current_sqrt_price = provider.get_current_sqrt_price(current_block)

        lower_tick = int(current_tick // 10 * 10 - 100)
        upper_tick = int(current_tick // 10 * 10 + 100)

        y_real = 1 * 10**self.token1_decimals
        x_virt, y_virt, x_real = real_reservers_to_virtal_reserves(lower_tick, upper_tick, current_tick, current_sqrt_price, y_real=y_real)
        liquidity = math.sqrt(x_virt * y_virt)

        position = Position(current_tick, lower_tick, upper_tick, liquidity, None, None)

        expected_amount_token0 = position.amount_x(current_tick, current_sqrt_price)
        expected_amount_token1 = position.amount_y(current_tick, current_sqrt_price)

        _, txn_receipt = provider.mint_position(position, current_tick, current_sqrt_price)

        token_id = int.from_bytes(txn_receipt["logs"][3]["topics"][-1], byteorder="big")

        actual_amount_token0 = int.from_bytes(txn_receipt["logs"][0]["data"][-32:])
        actual_amount_token1 = int.from_bytes(txn_receipt["logs"][1]["data"][-32:])

        actual_liquidity = int.from_bytes(txn_receipt["logs"][4]["data"][:32])

        # TODO: fix: delta should be way smaller
        self.assertAlmostEqual(expected_amount_token0, actual_amount_token0, delta=100*10**self.token0_decimals)
        self.assertAlmostEqual(expected_amount_token1, actual_amount_token1, delta=0.001*10**self.token1_decimals)

        self.assertAlmostEqual(liquidity, actual_liquidity, delta=0.001*10**self.token1_decimals)

    def testMintPositionOnlyETH(self):

        balance_token0 = self.token0_contract.functions.balanceOf(self.account.address).call()
        balance_token1 = self.token1_contract.functions.balanceOf(self.account.address).call()

        self.assertEqual(balance_token0, 0)
        self.assertEqual(balance_token1, 0)

        provider = Provider(pool_address="0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640", network="mainnet", local=True)

        current_block = provider.get_current_block()
        current_tick = provider.get_current_tick(current_block)
        current_sqrt_price = provider.get_current_sqrt_price(current_block)

        lower_tick = int(current_tick // 10 * 10 - 100)
        upper_tick = int(current_tick // 10 * 10 + 100)

        y_real = 1 * 10**self.token1_decimals
        x_virt, y_virt, x_real = real_reservers_to_virtal_reserves(lower_tick, upper_tick, current_tick, current_sqrt_price, y_real=y_real)
        liquidity = math.sqrt(x_virt * y_virt)

        position = Position(current_tick, lower_tick, upper_tick, liquidity, None, None)

        expected_amount_token0 = position.amount_x(current_tick, current_sqrt_price)
        expected_amount_token1 = position.amount_y(current_tick, current_sqrt_price)

        _, txn_receipt = provider.mint_position(position, current_tick, current_sqrt_price)

        token_id = int.from_bytes(txn_receipt["logs"][3]["topics"][-1], byteorder="big")

        actual_amount_token0 = int.from_bytes(txn_receipt["logs"][0]["data"][-32:])
        actual_amount_token1 = int.from_bytes(txn_receipt["logs"][1]["data"][-32:])

        actual_liquidity = int.from_bytes(txn_receipt["logs"][4]["data"][:32])

        # TODO: fix: delta should be way smaller
        self.assertAlmostEqual(expected_amount_token0, actual_amount_token0, delta=100*10**self.token0_decimals)
        self.assertAlmostEqual(expected_amount_token1, actual_amount_token1, delta=0.001*10**self.token1_decimals)

        self.assertAlmostEqual(liquidity, actual_liquidity, delta=0.001*10**self.token1_decimals)