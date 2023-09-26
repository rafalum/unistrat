# How to implement your strategy?

This guide will show you how you can implement your strategy in Unistrat. Let's go!

## 1. Come up with a strategy

First we need to come up with a sensible strategy. A strategy in Uniswap v3 defines the opening and closing of liquidity positions at a specifc time. 
A position consists of three parameters: 

    1. lower tick
    2. upper tick
    3. liquidity

The goal of the strategy is that the price (or tick) always stays in the range between the lower tick and upper tick. 

For this tutorial we are going to use a very simple strategy: 
    
    - We close a position after 1 hour
    - We open a new position as long as no other position is open and the standard deviation of the past two hours is below a certain threshold
    - Once we open a position, we calculate the lower and upper tick to be the the current tick +- one hourly standard deviation

With that, we can go and implement our strategy.

## 2. Implement the strategy

The strategy is defined in `src/strategy.py`. There we have the following function:
```python
def _strategy(self, past_swap_data: np.ndarray, past_mint_data: np.ndarray, past_burn_data: np.ndarray, current_block: int, current_tick: int) -> None:
```

The function has access to the past swap, mint and burn data as well as the current block and current tick to make a decision. Let's implement our example strategy!

We said we want to close an open position after 1 hour. Here is the code snipped that implements that logic:
```python
for index in self.position_manager.open_positions_index:
    if self.position_manager.positions_meta_data[index]["block"] + 60 * 5 <= current_block:
        self.position_manager.close_position(index)
```

We first query the position manager to get a list of all open positions. Then we check the block number when the position was created using the `positions_meta_data` member variable. If 300 or more blocks (~1 hour if we assume a block time of 12 sec) have passed since the creation time, we cose the position by calling the position managers `close_position` method.

Next we want to evaluate the creation of a new position. We first reduce the swap data to a minute-by-minute data:
```python
data = pd.DataFrame(past_swap_data)
reduced_data = data.groupby(data.iloc[:,0] // 5).apply(lambda x: x.iloc[-1]).to_numpy()
```
We wrap the `past_swap_data` into a pandas dataframe and then extract the last swap of every fifth block. This ensures that we get a minute-by-minute tick (or price).

Next, we check that we have at least two hours of past swap data.
```python
if reduced_data.shape[0] < 120:
    return

# consider the last 2 hours
ticks_last_2_hours = reduced_data[-120:, self.state.TICK_INDEX]
```
If this is the case, we extract the minute-by-minute tick values of the past two hours.

Now starts the fun part, we want to analyze how much the price fluctuated and based on that infer the next range of our new position. 

```python
delta = np.diff(ticks_last_2_hours)
std = np.std(delta)
```
We first calculate how much the ticks change from one minute to the next. Then we calculate the standard deviation of this change. Expressed in words, around 63% of the minute-by-minute change is below the value of `std`, i.e. the probability that the tick in the next minute is above `std` is around 37%.

Next, we check if point two of our strategy holds:
```python
if std > 10 or len(self.position_manager.open_positions_index) > 0:
    # no new position opened
    return
```
We do not open a new position if the `std` is above 10 or we still have an open position. If this is not the case, we calculate the range of our new position and open it.
```python
upper_tick = round_tick((current_tick + std * math.sqrt(60)))
lower_tick = round_tick((current_tick - std * math.sqrt(60)))

self.position_manager.open_position(lower_tick, upper_tick, y_real=10**18)
```
As the standard deviation scales with the square root of the time, we calculate the upper tick (lower tick) by adding (subtracting) the minute-by-minute std multiplied by the square root of time we want to have the position open. We defined this to be 60 minutes. For the liquidity we use a static amount of 2 ether. Finally, we can call the position manager to open the position for us.

Congrats you codified your strategy in Unistrat.

## 3. Backtest your strategy

In order to see how effective your strategy is, make sure to backtest it on past Uniswap data. To do that just run the following command:
```python
python3 run.py --backtest --from_block 17000001 --to_block 17005000 --save_performance performance_17000001_17005000
```
This backtests your strategy between block 17000001 and 17005000 and saves the performance in performance_17000001_17005000.pkl.