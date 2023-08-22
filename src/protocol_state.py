import time
import logging
import threading



class ProtocolState:
    def __init__(self, provider, init=[], max_state_size=5000):

        self.provider = provider

        self.current_block = None
        self.current_tick = None

        # Event data
        self.swap_data = init
        self.mint_data = []
        self.burn_data = []

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

            time.sleep(0.2)

            state_size = len(self.swap_data)
            if state_size > self.max_state_size:
                self.swap_data = self.swap_data[state_size-self.max_state_size:]


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

            # Just for logging
            for swap_event in swap_events:
                self.logger.info(f"#### Swap event: {swap_event[1]} ####")


            # TODO: Mint events
            # TODO: Burn events

            self.current_tick = self.swap_data[-1][1]

            if not self.provider.backtest:
                time.sleep(12)


    def start(self):
        self.collect = True
        self.thread.start()

    def stop(self):

        self.collect = False
        self.thread.join()





