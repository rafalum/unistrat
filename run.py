import sys
import time
import pickle
import argparse
from PySide6.QtWidgets import QApplication

from src.collect_events import collect_events
from src.utils import get_contract, check_data_exists

from src.gui import MainWindow
from src.strategy import Strategy
from src.provider import Provider
from src.protocol_state import ProtocolState
from src.position_manager import PositionManager


def main():
    parser = argparse.ArgumentParser(description="Your program description here.")

    parser.add_argument(
        "pool_address",
        type=str,
        help="Specify Uniswap pool address to be used."
    )
    
    parser.add_argument(
        "network",
        type=str,
        choices=["mainnet", "goerli", "optimism"],
        help="Specify the network to be used."
    )

    parser.add_argument(
        "--gui",
        action='store_true',
        default=False,
        help="Activate the GUI.",
    )

    parser.add_argument(
        "--simulate",
        action='store_true',
        default=False,
        help="Real time execution but without making trades.",
    )

    parser.add_argument(
        "--backtest",
        action='store_true',
        default=False,
        help="Enable backtesting mode.",
    )

    parser.add_argument(
        "--from_block",
        type=str,
        help="Specify the first block to be used for backtesting."
    )

    parser.add_argument(
        "--to_block",
        type=str,
        help="Specify the last block to be used for backtesting."
    )

    parser.add_argument(
        "--save_performance",
        type=str,
        help="Save the perforamance to a file."
    )

    args = parser.parse_args()

    if args.backtest:
        if args.from_block is None or args.to_block is None:
            parser.error("--backtest requires --from_block and --to_block.")
        
        print("Running in backtest mode")

        data_exists = check_data_exists(int(args.from_block), int(args.to_block), args.pool_address)

        if not data_exists:
            print("Collecting data...")
            collect_events(get_contract("POOL", args.pool_address), int(args.from_block), int(args.to_block))
    else:
        print("Running in normal mode")
    
    provider = Provider(args.pool_address, args.network, sim=args.simulate, backtest=args.backtest, swap_data="data/Swap.csv", mint_data="data/Mint.csv", burn_data="data/Burn.csv")
    state = ProtocolState(provider)
    position_manager = PositionManager(provider, state)
    strategy = Strategy(provider, state, position_manager)

    state.start()
    strategy.start()

    if args.gui:
        app = QApplication(sys.argv)

        window = MainWindow(provider, state, position_manager, backtest=args.backtest)
        window.setWindowTitle(f"UniSwap v3 {provider.token0_symbol}-{provider.token1_symbol} Interface")
        window.setGeometry(100, 100, 800, 600)
        window.show()

        exit_code = app.exec()

        strategy.stop()
        state.stop()

        if args.save_performance:
            with open(args.save_performance + ".pkl", "wb") as f:
                pickle.dump(position_manager.performance, f)

        sys.exit(exit_code)

    else:
        while True:

            if args.backtest and state.current_block == -1:

                state.stop()
                strategy.stop()

                if args.save_performance:
                    with open(args.save_performance + ".pkl", "wb") as f:
                        pickle.dump(position_manager.performance, f)

                break

            time.sleep(20)

if __name__ == "__main__":
    main()