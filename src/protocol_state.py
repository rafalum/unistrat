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

        # Event data
        self.swap_data = init
        self.mint_data = []
        self.burn_data = []

        self.liquidity_around_tick = []

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
                thread = threading.Thread(target=self._get_liquidity_around_tick, args=(self.swap_data[-1][1], self.current_block), daemon=True)
                thread.start()

            self.current_tick = self.swap_data[-1][1]

            if not self.provider.backtest:
                time.sleep(12)
            else:
                time.sleep(0.2)

    def _get_liquidity_around_tick(self, tick, block_number) -> None:

        liquidity = self.provider.get_liquidity(block_number)

        tick_below = tick // 10 * 10
        tick_above = tick_below + 10

        tick_state_below = self.provider.get_tick_state(tick_below, block_number)
        tick_state_above = self.provider.get_tick_state(tick_above, block_number)

        if tick_state_below:
            liquidity_net_below = tick_state_below[1]
            liquidity_tick_below = liquidity - liquidity_net_below
            liquidity_tick_below
        else:
            liquidity_tick_below = liquidity
            
        if tick_state_above:
            liquidity_net_above = tick_state_above[1]
            liquidity_tick_above = liquidity + liquidity_net_above
        else:
            liquidity_tick_above = liquidity

        self.liquidity_around_tick = [liquidity_tick_below, liquidity, liquidity_tick_above]

        return


    def start(self):
        self.collect = True
        self.thread.start()

    def stop(self):

        self.collect = False
        self.thread.join()





