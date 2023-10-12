import os
import time
import math
import psutil
import signal
import unittest
import subprocess
from web3 import Web3

from src.utils import get_contract, get_account, get_provider, get_env_variable

WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

class TestMint(unittest.TestCase):

    def setUp(self):

        if os.getenv('GITHUB_ACTIONS') == 'true':
            print('Running within GitHub Actions')
            API_KEY = os.getenv('INFURA_KEY')
        else:
            print('Not running within GitHub Actions')
            API_KEY = get_env_variable("MAINNET_PROVIDER")
            

        # spin up Ethereum node
        self.node_process = subprocess.Popen(["npx", "hardhat", "node", "--fork", API_KEY])

        if self.node_process.returncode == None:
            print("Hardhat fork started successfully")
        else:
            print(f"Error starting Hardhat fork. Exit code: {self.node_process.returncode}")

        time.sleep(10)

        if os.getenv('GITHUB_ACTIONS') == 'true':

            self.w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
            self.account = self.w3.eth.account.from_key(os.getenv('TEST_ACCOUNT_PRIVATE_KEY'))

            self.pool_contract = get_contract("USDC_ETH_POOL", address="0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640", test=True)
            self.router_contract = get_contract("UNISWAP_ROUTER", address="0xE592427A0AEce92De3Edee1F18E0157C05861564", test=True)
            self.nft_contract = get_contract("NFT_POSITION_MANAGER", address="0xC36442b4a4522E871399CD717aBDD847Ab11FE88", test=True)

            self.token0_address = self.pool_contract.functions.token0().call()
            self.token1_address = self.pool_contract.functions.token1().call()
            self.fee = self.pool_contract.functions.fee().call()

            self.token0_contract = get_contract("token0", self.token0_address, test=True)
            self.token1_contract = get_contract("token1", self.token1_address, test=True) 
        else:
            self.w3 = get_provider(test=True)
            self.account = get_account(test=True)

            self.pool_contract = get_contract("USDC_ETH_POOL", test=True)
            self.router_contract = get_contract("UNISWAP_ROUTER", test=True)
            self.nft_contract = get_contract("NFT_POSITION_MANAGER", test=True)

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
            self._wrap_token(self.token0_contract, 10**18)
        else:
            self._swap(WETH_ADDRESS, self.token0_address, 10**18, True)

        balance_token0 = self.token0_contract.functions.balanceOf(self.account.address).call()
        balance_token1 = self.token1_contract.functions.balanceOf(self.account.address).call()

        self.assertEqual(balance_token1, 0)
        self.assertGreater(balance_token0, 0)

    """
    def testMintPositionOnlyToken1(self):

        balance_token0 = self.token0_contract.functions.balanceOf(self.account.address).call()
        balance_token1 = self.token1_contract.functions.balanceOf(self.account.address).call()

        self.assertEqual(balance_token0, 0)
        self.assertEqual(balance_token1, 0)

        if self.token1_address == WETH_ADDRESS:
            self._wrap_token(self.token1_contract, 10**18)
        else:
            self._swap(WETH_ADDRESS, self.token1_address, 10**18, True)

        balance_token0 = self.token0_contract.functions.balanceOf(self.account.address).call()
        balance_token1 = self.token1_contract.functions.balanceOf(self.account.address).call()

        self.assertEqual(balance_token0, 0)
        self.assertGreater(balance_token1, 0)
    """

    def _swap(self, token_in, token_out, swap_token_amount, eth) -> None:

        swap_token_tx = self.router_contract.functions.exactInputSingle((
                token_in,
                token_out,
                self.fee,
                self.account.address,
                int(time.time()) + 10 * 60,
                int(swap_token_amount),
                0,
                0
            )).build_transaction({
                'from': self.account.address,
                'gas': 500000,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'value': swap_token_amount if eth else 0
            })

        txn_hash, _ = self._sign_and_broadcast_transaction(swap_token_tx)
        
        return
    
    def _wrap_token(self, token_contract, amount) -> None:

        wrap_token_tx = token_contract.functions.deposit().build_transaction({
            'from': self.account.address,
            'gas': 500000,
            'nonce': self.w3.eth.get_transaction_count(self.account.address),
            'value': amount
        })

        txn_hash, _ = self._sign_and_broadcast_transaction(wrap_token_tx)

        return
    
    def _sign_and_broadcast_transaction(self, transaction):
        # Sign the transaction
        signed_txn = self.w3.eth.account.sign_transaction(transaction, self.account.key)

        # Send the transaction
        txn_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)

        # Wait for the transaction to be mined
        txn_receipt = self.w3.eth.wait_for_transaction_receipt(txn_hash)

        return txn_hash, txn_receipt