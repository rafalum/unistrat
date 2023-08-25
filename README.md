# UniBot: A UniSwap LP strategy framework

### What is UniBot?

UniBot is a tool for liquidity providers in UniSwap v3. It has been shown that most LPs in Uniswap are loosing money as they are effectively selling short puts on the market (see [Guillaumes blog series](https://lambert-guillaume.medium.com/uniswap-v3-lp-tokens-as-perpetual-put-and-call-options-5b66219db827)).
Without active management and careful choosing of the liquidity positions, most LPs are destined to loose money. UniBot tries to give LPs a way to codify and backtest their strategies.

![GUI](./gui.png)

### Structure

All the code lives in `src/` and contains the following components:

    - `provider.py`: is the interface to an Ethereum node and fetches all the relevant data
    - `protocol_state.py`: represents the current state of the UniSwap pool
    - `strategy.py`: codifies the strategy to provide liquidity
    - `position.py`: represents a UniSwap LP position
    - `position_manager.py`: manages the open and closed positions
    - `gui.py`: simple visual interface to display all relevant informations


![Structure](./structure.png)