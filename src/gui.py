import sys
import time
import random
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QPainter, QBrush, QFont
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QBarSeries, QBarSet, QBarCategoryAxis
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QGridLayout

from utils import get_contract, get_provider, get_volume_in_last_blocks, get_value_locked_for_tick_range

from strategy import Strategy
from provider import Provider
from position import Position
from protocol_state import ProtocolState
from position_manager import PositionManager

class MainWindow(QMainWindow):
    def __init__(self, state, position_manager):
        super().__init__()

        self.state = state
        self.position_manager = position_manager

        self.previous_block = None
        self.previous_tick = None

        self.series = QLineSeries()
        self.chart = QChart()

        self.upper_tick_line = QLineSeries()
        self.lower_tick_line = QLineSeries()

        self.chart.addSeries(self.upper_tick_line)
        self.chart.addSeries(self.lower_tick_line)

        self.chart.addSeries(self.series)
        self.chart.createDefaultAxes()
        self.chart.setTitle("Price Chart")
        self.chart.legend().hide()

        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)

        self.info_label = QLabel("Latest Price: N/A")
        self.info_label.setFont(QFont("Arial", 16))

        self.counter = 0

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_chart)
        self.timer.start(500)  # update every 1000 ms (1 second)

        self.x_axis = self.chart_view.chart().axes(Qt.Horizontal)[0]
        self.y_axis = self.chart_view.chart().axes(Qt.Vertical)[0]

        # Create rotated bar plot (vertical)
        self.tick_bar_series = QBarSeries()
        self.tick_bar_set = QBarSet("Liquidity per tick")
        self.tick_bar_series.append(self.tick_bar_set)
        self.tick_chart = QChart()
        self.tick_chart.addSeries(self.tick_bar_series)
        self.tick_chart.createDefaultAxes()
        self.tick_chart_view = QChartView(self.tick_chart)
        self.tick_chart_view.setRenderHint(QPainter.Antialiasing)
        self.tick_chart_view.setMaximumWidth(200)  # Set the maximum width
        self.tick_chart_view.rotate(90)  # Rotate the view 90 degrees

        # Create horizontal bar plot
        self.volume_bar_series = QBarSeries()
        self.volume_bar_set = QBarSet("Volume per 12 blocks")
        self.volume_bar_series.append(self.volume_bar_set)
        self.volume_chart = QChart()
        self.volume_chart.addSeries(self.volume_bar_series)
        self.volume_chart.createDefaultAxes()
        self.volume_chart_view = QChartView(self.volume_chart)
        self.volume_chart_view.setRenderHint(QPainter.Antialiasing)
        self.volume_chart_view.setMaximumHeight(200)  # Set the maximum height


        # Create a grid layout
        grid_layout = QGridLayout()

        # Add the rotated bar plot to the grid layout at row 0, column 0
        grid_layout.addWidget(self.tick_chart_view, 0, 0)

        # Add the main chart to the grid layout at row 0, column 1
        grid_layout.addWidget(self.chart_view, 0, 1)

        # Add the horizontal bar plot to the grid layout at row 1, column 1
        grid_layout.addWidget(self.volume_chart_view, 1, 1)

        # Add the info label to the grid layout at row 1, column 0
        grid_layout.addWidget(self.info_label, 0, 2)

        # Create a container and set it as the central widget
        container = QWidget()
        container.setLayout(grid_layout)
        self.setCentralWidget(container)


    def update_chart(self):

        current_block = self.state.current_block
        current_tick = self.state.current_tick
        liquidities = self.state.liquidity_around_tick

        if current_block == self.previous_block or current_tick == None:
            return


        self.upper_tick_line.append(0, 0)
        self.upper_tick_line.append(0, 0)

        self.lower_tick_line.append(0, 0)
        self.lower_tick_line.append(0, 0)

        for index in self.position_manager.open_positions_index:

            position = self.position_manager.positions[index]
            meta_data = self.position_manager.positions_meta_data[index]

            lower_tick = position.lower_tick
            upper_tick = position.upper_tick

            value_position = position.value_position(current_tick) / 10**18
            value_hold = position.value_hold(current_tick) / 10**18

            self.lower_tick_line.replace([QPointF(meta_data["block"], lower_tick), QPointF(current_block, lower_tick)])
            self.upper_tick_line.replace([QPointF(meta_data["block"], upper_tick), QPointF(current_block, upper_tick)])

            self.info_label.setText(f"Value Position: {value_position:.2f} | Value Hold: {value_hold:.2f} | Difference: {value_hold - value_position:.4f}")

        # Get value locked in the ticks around the current tick
        value_locked = get_value_locked_for_tick_range(current_tick, liquidities)
        print(value_locked)
        tick_categories = [str(x) for x in range(int(current_tick) - 10, int(current_tick) + 11)]
        tick_heights = [0 for _ in range(9)] + value_locked + [0 for _ in range(9)]

        # Update tick_bar_set
        tick_axis_x = self.tick_chart_view.chart().axes(Qt.Horizontal)[0]
        tick_axis_x.clear()
        tick_axis_x.append(tick_categories)
        tick_axis_x.setLabelsAngle(270)
        self.tick_bar_set.remove(0, self.tick_bar_set.count())
        for height in tick_heights:
            self.tick_bar_set << height

        tick_axis_y = self.tick_chart_view.chart().axes(Qt.Vertical)[0]
        tick_axis_y.setRange(0, max(tick_heights))


        # Get the volumes in the last 12 blocks
        volume_data, interval_data = get_volume_in_last_blocks(self.state.swap_data, number_volume=300//12)
        volume_categories = [str(x) for x, y in interval_data[::-1]]
        volume_heights = volume_data[::-1]

        # Update volume_bar_set
        volume_axis_x = self.volume_chart_view.chart().axes(Qt.Horizontal)[0]
        volume_axis_x.clear()
        volume_axis_x.append(volume_categories)
        self.volume_bar_set.remove(0, self.volume_bar_set.count())
        for height in volume_heights:
            self.volume_bar_set << height

        volume_axis_y = self.volume_chart_view.chart().axes(Qt.Vertical)[0]
        volume_axis_y.setRange(0, max(volume_heights))


        self.series.append(current_block, current_tick)


        if self.counter > 300:  # keep a maximum of 20 points and remove older ones
            self.series.remove(0)
            for i in range(self.series.count()):
                point = self.series.at(i)
                x = point.x()
                y = point.y() 
                self.series.replace(i, x-1, y)


        self.x_axis.setRange(current_block - 300, current_block)
        self.y_axis.setRange(self.series.at(0).y() - 100, self.series.at(0).y() + 100)

        self.counter += 1
        self.previous_block = current_block

        return

if __name__ == '__main__':
    app = QApplication(sys.argv)

    contract = get_contract()
    node = get_provider()
    
    provider = Provider(node, contract, backtest=True, data="../tinker/data/USDC_ETH_SWAPS_reduced.csv")
    state = ProtocolState(provider)
    position_manager = PositionManager(provider, state)
    strategy = Strategy(provider, state, position_manager)

    state.start()
    strategy.start()

    window = MainWindow(state, position_manager)
    window.setWindowTitle("Styled Real-time Price Chart")
    window.setGeometry(100, 100, 800, 600)
    window.show()

    exit_code = app.exec()

    strategy.stop()
    state.stop()

    sys.exit(exit_code)
