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


    def __init__(self, provider, init=[], max_state_size=5000):

        self.provider = provider

        self.current_block = None
        self.current_tick = None
        self.current_liquidity = None

        # Event data
        self.swap_data = init
        self.mint_data = []
        self.burn_data = []

        self.tick_states = {}

        self.max_state_size = max_state_size

        self.collect = False
        self.thread = threading.Thread(target=self._collect)

        self.logger = logging.getLogger('logger2')
        self.logger.setLevel(logging.INFO)
        handler = logging.FileHandler('state.log')
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)


    def _collect(self):

        while self.collect:
            
            # restrict state size
            state_size = len(self.swap_data)
            if state_size > self.max_state_size:
                self.swap_data = self.swap_data[state_size-self.max_state_size:]

            # get the current block
            next_block = self.provider.get_current_block()

            if self.current_block == next_block:
                if not self.provider.backtest:
                    time.sleep(5)
                continue

            self.current_block = next_block

            self.logger.info(f"#### Current block: {self.current_block} ####")

            # Swap events
            swap_events = self.provider.get_events(self.current_block, "Swap")
            self.swap_data += swap_events

            # state currently empty -> wait for first event
            if len(self.swap_data) == 0:
                time.sleep(5)
                continue

            # Just for logging
            for swap_event in swap_events:
                self.logger.info(f"#### Swap event: {swap_event[1]} ####")


            # TODO: Mint events
            # TODO: Burn events
            new_burn_or_mint = False
            
            
            if new_burn_or_mint or self.current_tick != self.swap_data[-1][1]:

                self.current_liquidity = self.provider.get_liquidity(self.current_block)

                thread = threading.Thread(target=self._get_tick_states, args=(self.swap_data[-1][1], self.current_block, new_burn_or_mint), daemon=True)
                thread.start()

            self.current_tick = self.swap_data[-1][1]

            if not self.provider.backtest:
                time.sleep(12)
            else:
                time.sleep(1)

    def _get_tick_states(self, current_tick, block_number, get_all=False, tick_range=100) -> None:

        tick_below = int(current_tick // 10 * 10)

        if get_all or self.tick_states == {}:
            self.tick_states = {}
            for tick in range(tick_below - tick_range, tick_below + tick_range + 10, 10):
                tick_state = self.provider.get_tick_state(tick, block_number)
                self.tick_states[tick] = tick_state
        else:
            for tick in range(tick_below - tick_range, tick_below + tick_range + 10, 10):
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





