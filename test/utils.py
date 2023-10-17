import time

class TestUtil():

    def _swap(self, token_in, token_out, swap_token_amount, eth, account) -> None:

        swap_token_tx = self.router_contract.functions.exactInputSingle((
                token_in,
                token_out,
                self.fee,
                account.address,
                int(time.time()) + 10 * 60,
                int(swap_token_amount),
                0,
                0
            )).build_transaction({
                'from': self.account.address,
                'gas': 500000,
                'nonce': self.w3.eth.get_transaction_count(account.address),
                'value': swap_token_amount if eth else 0
            })

        txn_hash, _ = self._sign_and_broadcast_transaction(swap_token_tx, account)
        
        return
    
    def _wrap_token(self, token_contract, amount, account) -> None:

        wrap_token_tx = token_contract.functions.deposit().build_transaction({
            'from': account.address,
            'gas': 500000,
            'nonce': self.w3.eth.get_transaction_count(account.address),
            'value': amount
        })

        txn_hash, _ = self._sign_and_broadcast_transaction(wrap_token_tx, account)

        return
    
    def _sign_and_broadcast_transaction(self, transaction, account):
        # Sign the transaction
        signed_txn = self.w3.eth.account.sign_transaction(transaction, account.key)

        # Send the transaction
        txn_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)

        # Wait for the transaction to be mined
        txn_receipt = self.w3.eth.wait_for_transaction_receipt(txn_hash)

        return txn_hash, txn_receipt