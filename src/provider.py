import os
import time
import logging
import numpy as np
from typing import Tuple, List, Union

from .position import Position
from .config import addresses
from .utils import get_contract, get_provider, get_account, check_enough_balance, tick_to_price

BLOCK_INDEX = 0

class Provider:
    def __init__(self, pool_address, network, sim=False, backtest=False, swap_data=None, mint_data=None, burn_data=None, local=False):

        if backtest and not swap_data:
            raise ValueError("Backtest set to true -> please specify data file")

        self.provider = get_provider(test=local)

        self.pool_contract = get_contract("POOL", pool_address, test=local)
        self.router_contract = get_contract("UNISWAP_ROUTER", addresses[network]["UNISWAP_ROUTER"], test=local)
        self.nft_contract = get_contract("NFT_POSITION_MANAGER", addresses[network]["NFT_POSITION_MANAGER"], test=local)

        self.fee = self.pool_contract.functions.fee().call()
        self.tick_spacing = self.pool_contract.functions.tickSpacing().call()

        self.token0_address = self.pool_contract.functions.token0().call()
        self.token1_address = self.pool_contract.functions.token1().call()

        self.token0_contract = get_contract("token0", self.token0_address, test=local)
        self.token1_contract = get_contract("token1", self.token1_address,test=local)

        self.token0_symbol = self.token0_contract.functions.symbol().call()
        self.token1_symbol = self.token1_contract.functions.symbol().call()

        self.token0_decimals = self.token0_contract.functions.decimals().call()
        self.token1_decimals = self.token1_contract.functions.decimals().call()

        self.weth = addresses[network]["WETH"]

        self.token0_is_WETH = self.token0_address == self.weth
        self.token1_is_WETH = self.token1_address == self.weth

        self.account = get_account(test=local)

        self.sim = sim
        self.backtest = backtest

        if backtest:
            self.swap_data = np.loadtxt(swap_data, delimiter=",", dtype=float)
            self.mint_data = np.loadtxt(mint_data, delimiter=",", dtype=float)
            self.burn_data = np.loadtxt(burn_data, delimiter=",", dtype=float)

            self.block_number = self.swap_data[0, 0]
            self.last_block = self.swap_data[-1, 0]

        self.logger = logging.getLogger('logger3')
        self.logger.setLevel(logging.INFO)
        os.makedirs(os.path.dirname('src/logs/provider.log'), exist_ok=True)
        handler = logging.FileHandler('src/logs/provider.log')
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        self.logger.info(f"Token0: {self.token0_symbol}")
        self.logger.info(f"Token1: {self.token1_symbol}")
  
    
    def get_tick_state(self, tick, block_number) -> List[Union[int, bool]]:

        tick_state = self.pool_contract.functions.ticks(int(tick)).call(block_identifier=int(block_number))

        if tick_state[-1]:
            return tick_state
        else:
            return None
        
    def get_current_block(self) -> int:

        if self.backtest:
            current_block = self.block_number
            self.block_number += 1

            if current_block > self.last_block:
                return -1
            
            return current_block
        else:
            return self.provider.eth.block_number
        
    def get_current_sqrt_price(self, block) -> int:

        slot0 = self.pool_contract.functions.slot0().call(block_identifier=int(block))
        return slot0[0]
    
    def get_current_tick(self, block) -> int:
        
        slot0 = self.pool_contract.functions.slot0().call(block_identifier=int(block))
        return slot0[1]
        
    def get_events(self, last_block, current_block, type):

        if self.backtest:
            if type == "Swap":
                swap_events = self.swap_data[self.swap_data[:, BLOCK_INDEX] == current_block]
                event_data = swap_events.tolist()
            elif type == "Mint":
                mint_events = self.mint_data[self.mint_data[:, BLOCK_INDEX] == current_block]
                event_data = mint_events.tolist()
            elif type == "Burn":
                burn_events = self.burn_data[self.burn_data[:, BLOCK_INDEX] == current_block]
                event_data = burn_events.tolist()

        else:
            event_filter = self.pool_contract.events[type].create_filter(fromBlock=last_block, toBlock=current_block+1)
            events = event_filter.get_all_entries()
            
            event_data = []
            for event in events:
                if type == "Swap":
                    event_data.append([event.blockNumber, event.args['tick'], event.args['liquidity'], event.args['sqrtPriceX96'], event.args['amount0'], event.args['amount1']])
                elif type == "Mint":
                    event_data.append([event.blockNumber, event.args['tickLower'], event.args['tickUpper'], event.args['amount0'], event.args['amount1']])
                elif type == "Burn":
                    event_data.append([event.blockNumber, event.args['tickLower'], event.args['tickUpper'], event.args['amount0'], event.args['amount1']])

        return event_data
    
    def get_growth_global(self, block_number) -> Tuple:

        fee_growth_global_0 = self.pool_contract.functions.feeGrowthGlobal0X128().call(block_identifier=int(block_number)) / (1 << 128)
        fee_growth_global_1 = self.pool_contract.functions.feeGrowthGlobal1X128().call(block_identifier=int(block_number)) / (1 << 128)

        return fee_growth_global_0, fee_growth_global_1
    
    def get_liquidity(self, block_number) -> int:

        liquidity = self.pool_contract.functions.liquidity().call(block_identifier=int(block_number))

        return liquidity
    
    def sign_and_broadcast_transaction(self, transaction):
        # Sign the transaction
        signed_txn = self.provider.eth.account.sign_transaction(transaction, self.account.key)

        # Send the transaction
        txn_hash = self.provider.eth.send_raw_transaction(signed_txn.rawTransaction)
        self.logger.info(f'Transaction hash: {txn_hash.hex()}')

        # Wait for the transaction to be mined
        txn_receipt = self.provider.eth.wait_for_transaction_receipt(txn_hash)
        self.logger.info(f'Transaction receipt: {txn_receipt}')

        return txn_hash, txn_receipt
    
    def approve_token(self, address, amount, contract) -> None:

        approved_balance = contract.functions.allowance(self.account.address, address).call()
        # check if amount already approved
        if approved_balance < amount:

            approve_token_tx = contract.functions.approve(address, int(amount - approved_balance)).build_transaction({
                'from': self.account.address,
                'gas': 100000,
                'nonce': self.provider.eth.get_transaction_count(self.account.address)
            })

            txn_hash, _ = self.sign_and_broadcast_transaction(approve_token_tx)
        
        return 
    
    def swap_token(self, token_in, token_out, swap_token_amount, eth) -> None:

        swap_token_tx = self.router_contract.functions.exactInputSingle((
                token_in,
                token_out,
                500,
                self.account.address,
                int(time.time()) + 10 * 60,
                int(swap_token_amount),
                0,
                0
            )).build_transaction({
                'from': self.account.address,
                'gas': 500000,
                'nonce': self.provider.eth.get_transaction_count(self.account.address),
                'value': swap_token_amount if eth else 0
            })

        txn_hash, _ = self.sign_and_broadcast_transaction(swap_token_tx)
        
        return 
    
    def wrap_token(self, token_contract, amount) -> None:

        wrap_token_tx = token_contract.functions.deposit().build_transaction({
            'from': self.account.address,
            'gas': 500000,
            'nonce': self.provider.eth.get_transaction_count(self.account.address),
            'value': amount
        })

        txn_hash, _ = self.sign_and_broadcast_transaction(wrap_token_tx)

        return

    
    def mint_position(self, position: Position, current_tick, current_sqrt_price) -> Tuple:

        lower_tick = int(position.lower_tick)
        upper_tick = int(position.upper_tick)

        amount_token0 = int(position.amount_x(current_tick, current_sqrt_price))
        amount_token1 = int(position.amount_y(current_tick, current_sqrt_price))

        balance_token0 = self.token0_contract.functions.balanceOf(self.account.address).call()
        balance_token1 = self.token1_contract.functions.balanceOf(self.account.address).call()

        balance_token0 = balance_token0 + self.provider.eth.get_balance(self.account.address) if self.token0_is_WETH else balance_token0
        balance_token1 = balance_token1 + self.provider.eth.get_balance(self.account.address) if self.token1_is_WETH else balance_token1

        self.logger.info(f"Balance token0: {balance_token0}")
        self.logger.info(f"Balance token1: {balance_token1}")

        self.logger.info(self.token0_is_WETH)
        self.logger.info(self.token1_is_WETH)

        eth_balance = self.provider.eth.get_balance(self.account.address)

        self.logger.info(f"ETH balance: {eth_balance}")

        enough_balance = check_enough_balance(current_tick, balance_token0, balance_token1, int(amount_token0 * 1.01), int(amount_token1 * 1.01))
        if enough_balance == False:
            self.logger.info("Not enough balance to open position")
            return None, None

        if balance_token0 < amount_token0:
            self.logger.info("Not enough balance of token0 -> swapping token1 to token0")
            swap_token1_amount = (amount_token0 - balance_token0) * tick_to_price(current_tick)
            swap_token1_amount = int(swap_token1_amount * 1.01) 

            if not self.token1_is_WETH:
                self.approve_token(self.router_contract.address, swap_token1_amount, self.token1_contract)
            self.swap_token(self.token1_address, self.token0_address, swap_token1_amount, self.token1_is_WETH)

        elif balance_token1 < amount_token1:
            self.logger.info("Not enough balance of token1 -> swapping token0 to token1")
            swap_token0_amount = (amount_token1 - balance_token1) / tick_to_price(current_tick)
            swap_token0_amount = int(swap_token0_amount * 1.01)

            # swapping ERC20 tokens -> approve router contract to spend tokens
            if not self.token0_is_WETH:
                self.approve_token(self.router_contract.address, swap_token0_amount, self.token0_contract)
            self.swap_token(self.token0_address, self.token1_address, swap_token0_amount, self.token0_is_WETH)

        # check if one of the tokens is WETH and wrap it if necessary
        if self.token0_is_WETH or self.token1_is_WETH:
            if self.token0_is_WETH:
                balance_token0 = self.token0_contract.functions.balanceOf(self.account.address).call()
                amount_to_wrap = amount_token0 - balance_token0

                if amount_to_wrap > 0:
                    self.logger.info("Not enough WETH: Wrapping token0")
                    self.wrap_token(self.token0_contract, amount_to_wrap)

            elif self.token1_is_WETH:
                balance_token1 = self.token1_contract.functions.balanceOf(self.account.address).call()
                amount_to_wrap = amount_token1 - balance_token1

                if amount_to_wrap > 0:
                    self.logger.info("Not enough WETH: Wrapping token1")
                    self.wrap_token(self.token1_contract, amount_to_wrap)
            
        # approve token0 and token1 to be spent by nft manager contract
        self.approve_token(self.nft_contract.address, amount_token0, self.token0_contract)
        self.approve_token(self.nft_contract.address, amount_token1, self.token1_contract)
            

        mint_tx = self.nft_contract.functions.mint((
            self.token0_address,
            self.token1_address,
            self.fee,
            lower_tick,
            upper_tick,
            amount_token0,
            amount_token1,
            0,
            0,
            self.account.address,
            int(time.time()) + 10 * 60  # deadline
        )).build_transaction({
            'from': self.account.address,
            'gas': 500000,
            'nonce': self.provider.eth.get_transaction_count(self.account.address)
        })

        mint_tx_hash, mint_tx_receipt = self.sign_and_broadcast_transaction(mint_tx)

        return mint_tx_hash, mint_tx_receipt
    
    def burn_position(self, position: Position, current_tick):

        token_id = position.token_id

        position = self.nft_contract.functions.positions(token_id).call()

        # 1. decrease liquidity
        self.logger.info(f"Decreasing liquidity of position {token_id}")
        liquidity = position[7]

        decrease_liquidity_tx = self.nft_contract.functions.decreaseLiquidity((
            token_id,
            liquidity,
            0,
            0,
            int(time.time()) + 10 * 60
        )).build_transaction({
            'from': self.account.address,
            'gas': 500000,
            'nonce': self.provider.eth.get_transaction_count(self.account.address)
        })

        txn_hash, _ = self.sign_and_broadcast_transaction(decrease_liquidity_tx)

        # 2. collect fees
        self.logger.info(f"Collecting fees of position {token_id}")
        collect_tx = self.nft_contract.functions.collect((
            token_id,
            self.account.address,
            2 ** 128 - 1,
            2 ** 128 - 1
        )).build_transaction({
            'from': self.account.address,
            'gas': 500000,
            'nonce': self.provider.eth.get_transaction_count(self.account.address)
        })

        collect_txn_hash, collect_tx_receipt  = self.sign_and_broadcast_transaction(collect_tx)

        # 3. burn position
        self.logger.info(f"Burning position {token_id}")
        burn_tx = self.nft_contract.functions.burn((token_id)).build_transaction({
            'from': self.account.address,
            'gas': 500000,
            'nonce': self.provider.eth.get_transaction_count(self.account.address)
        })

        burn_tx_hash, burn_tx_receipt = self.sign_and_broadcast_transaction(burn_tx)

        return burn_tx_hash, burn_tx_receipt, collect_tx_receipt
