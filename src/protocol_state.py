import os
import time
import logging
import threading

class ProtocolState:

    BLOCK_INDEX = 0
    TICK_INDEX = 1
    LIQUIDITY_INDEX = 2
    SQRT_PRICE_INDEX = 3
    AMOUNT0_INDEX = 4
    AMOUNT1_INDEX = 5

    NUM_BLOCKS = 5

    def __init__(self, provider, max_state_size=5000):

        self.provider = provider

        self.current_block = None
        self.current_tick = None
        self.current_liquidity = None

        # Event data
        self.swap_data = []
        self.mint_data = []
        self.burn_data = []

        self.tick_states = {}

        self.max_state_size = max_state_size

        self.collect = False
        self.thread = threading.Thread(target=self._collect)

        self.logger = logging.getLogger('logger2')
        self.logger.setLevel(logging.INFO)
        os.makedirs(os.path.dirname('src/logs/state.log'), exist_ok=True)
        handler = logging.FileHandler('src/logs/state.log')
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)


    def _collect(self):

        last_block = self.provider.get_current_block()
        self.current_block = self.provider.get_current_block()

        while self.collect:
            
            # restrict state size
            swap_state_size = len(self.swap_data)
            mint_state_size = len(self.mint_data)
            burn_state_size = len(self.burn_data)

            if swap_state_size > self.max_state_size:
                self.swap_data = self.swap_data[swap_state_size-self.max_state_size:]
            if mint_state_size > self.max_state_size:
                self.mint_data = self.mint_data[mint_state_size-self.max_state_size:]
            if burn_state_size > self.max_state_size:
                self.burn_data = self.burn_data[burn_state_size-self.max_state_size:]
            

            # get the current block
            while True:
                self.current_block = self.provider.get_current_block()
                if last_block != self.current_block:
                    break
                else:
                    time.sleep(12)

            # Swap events
            swap_events = self.provider.get_events(last_block, self.current_block, "Swap")
            self.swap_data += swap_events

            # Mint events
            mint_events = self.provider.get_events(last_block, self.current_block, "Mint")
            self.mint_data += mint_events

            # Burn events
            burn_events = self.provider.get_events(last_block, self.current_block, "Burn")
            self.burn_data += burn_events


            # Just for logging
            for i in range(int(last_block) + 1, int(self.current_block) + 1):
                self.logger.info(f"#### Block: {i} ####")

                for swap_event in swap_events:
                    if swap_event[self.BLOCK_INDEX] == i:
                        self.logger.info(f"#### Swap event: {swap_event[1]} ####")
                for mint_event in mint_events:
                    if mint_event[self.BLOCK_INDEX] == i:
                        self.logger.info(f"#### Mint event: {mint_event[1]} - {mint_event[2]} ####")
                for burn_event in burn_events:
                    if burn_event[self.BLOCK_INDEX] == i:
                        self.logger.info(f"#### Burn event: {burn_event[1]} - {burn_event[2]} ####")

            last_block = self.current_block

            if swap_events == []:
                continue

            new_burn_or_mint = burn_events != [] or mint_events != []
            
            # compute new liquidity and value locked if there is a new tick or a mint or burn event
            if new_burn_or_mint or self.current_tick != self.swap_data[-1][1]:

                self.current_liquidity = self.provider.get_liquidity(self.current_block)

                thread = threading.Thread(target=self._get_tick_states, args=(self.swap_data[-1][1], self.current_block, new_burn_or_mint), daemon=True)
                thread.start()

            self.current_tick = self.swap_data[-1][1]

            if self.provider.backtest:
                time.sleep(0.2)
            else:
                time.sleep(1)

    def _get_tick_states(self, current_tick, block_number, get_all=False, tick_range=100) -> None:

        tick_below = int(current_tick // self.provider.tick_spacing * self.provider.tick_spacing)

        if get_all or self.tick_states == {}:
            self.tick_states = {}
            for tick in range(tick_below - tick_range, tick_below + tick_range + self.provider.tick_spacing, self.provider.tick_spacing):
                tick_state = self.provider.get_tick_state(tick, block_number)
                self.tick_states[tick] = tick_state
        else:
            for tick in range(tick_below - tick_range, tick_below + tick_range + self.provider.tick_spacing, self.provider.tick_spacing):
                if tick not in self.tick_states:
                    tick_state = self.provider.get_tick_state(tick, block_number)
                    self.tick_states[tick] = tick_state

        return


    def start(self):
        self.collect = True
        self.thread.start()

    def stop(self):

        self.collect = False
        self.thread.join()





