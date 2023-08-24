import sys
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QPainter, QBrush, QFont
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QBarSeries, QBarSet, QValueAxis, QCategoryAxis
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QGridLayout, QGraphicsTextItem, QTableWidget, QTableWidgetItem, QHeaderView, QLabel

from uniwap_math import tick_to_price
from utils import get_contract, get_provider, get_volume_in_last_blocks, get_value_locked_for_tick_range

from strategy import Strategy
from provider import Provider
from position import Position
from protocol_state import ProtocolState
from position_manager import PositionManager

class MainWindow(QMainWindow):
    def __init__(self, state, position_manager, backtest=False):
        super().__init__()

        self.state = state
        self.position_manager = position_manager
        self.backtest = backtest

        self.previous_block = None
        self.previous_tick = None

        # Tick Chart
        self.series = QLineSeries()
        self.chart = QChart()

        self.chart.addSeries(self.series)
        self.chart.createDefaultAxes()
        self.chart.setTitle("Tick Chart")
        self.chart.legend().hide()

        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)

        x_axis = self.chart_view.chart().axes(Qt.Horizontal)[0]
        self.chart.removeAxis(x_axis)
        self.new_x_axis = QValueAxis()
        self.chart.addAxis(self.new_x_axis, Qt.AlignBottom)
        self.series.attachAxis(self.new_x_axis)

        y_axis = self.chart_view.chart().axes(Qt.Vertical)[0]
        self.chart.removeAxis(y_axis)
        self.new_y_axis = QValueAxis()
        self.chart.addAxis(self.new_y_axis, Qt.AlignLeft)
        self.series.attachAxis(self.new_y_axis)

        # Position bounds
        self.upper_tick_line = QLineSeries()
        self.lower_tick_line = QLineSeries()

        self.chart.addSeries(self.upper_tick_line)
        self.chart.addSeries(self.lower_tick_line)

        self.upper_tick_line.attachAxis(self.new_x_axis)
        self.upper_tick_line.attachAxis(self.new_y_axis)

        self.lower_tick_line.attachAxis(self.new_x_axis)
        self.lower_tick_line.attachAxis(self.new_y_axis)
        
        # Information text
        self.text_item = QGraphicsTextItem("Waiting for data...")
        self.text_item.setFont(QFont("Arial", 16))
        self.chart.scene().addItem(self.text_item)

        # Positions table
        self.open_positions_table = QTableWidget()
        self.open_positions_table.setColumnCount(5)
        self.open_positions_table.setHorizontalHeaderLabels(["ID", "USDC", "ETH", "Value in ETH", "IL"])
        self.open_positions_table.setMaximumWidth(600)
        self.open_positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.closed_positions_table = QTableWidget()
        self.closed_positions_table.setColumnCount(4)
        self.closed_positions_table.setHorizontalHeaderLabels(["ID", "Fees in ETH", "Value in ETH", "P/L"])
        self.closed_positions_table.setMaximumWidth(600)
        self.closed_positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.open_positions_title = QLabel("Open Positions")
        self.open_positions_title.setMaximumWidth(600)
        self.open_positions_title.setAlignment(Qt.AlignCenter)
        self.open_positions_title.setFont(QFont("Arial", 16))

        self.closed_positions_title = QLabel("Closed Positions")
        self.closed_positions_title.setMaximumWidth(600)
        self.closed_positions_title.setAlignment(Qt.AlignCenter)
        self.closed_positions_title.setFont(QFont("Arial", 16))

        self.table_layout = QVBoxLayout()
        self.table_layout.addWidget(self.open_positions_title)
        self.table_layout.addWidget(self.open_positions_table)
        self.table_layout.addWidget(self.closed_positions_title)
        self.table_layout.addWidget(self.closed_positions_table)

        self.counter = 0

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_chart)
        if backtest:
            self.timer.start(200)  # update every 1000 ms (1 second)
        else:
            self.timer.start(5000)


        # Create rotated bar plot (vertical)
        self.tick_bar_series = QBarSeries()
        self.tick_bar_set = QBarSet("")
        self.tick_bar_series.append(self.tick_bar_set)
        self.tick_chart = QChart()
        self.tick_chart.addSeries(self.tick_bar_series)
        self.tick_chart.createDefaultAxes()
        self.tick_chart_view = QChartView(self.tick_chart)
        self.tick_chart_view.setRenderHint(QPainter.Antialiasing)
        self.tick_chart_view.setMaximumWidth(300)  # Set the maximum width
        self.tick_chart_view.rotate(90)  # Rotate the view 90 degrees
        self.tick_chart.legend().hide() # Hide the legend

        # Replace the existing y-axis
        axisY = self.tick_chart_view.chart().axes(Qt.Vertical)[0]
        self.tick_chart.removeAxis(axisY)
        new_axisY = QValueAxis()
        # Add the new y-axis to the right side of the chart
        self.tick_chart.addAxis(new_axisY, Qt.AlignRight)
        # Attach the series to the new y-axis
        self.tick_bar_series.attachAxis(new_axisY)

        self.tick_chart_label = QLabel("Value locked in ticks")
        self.tick_chart_label.setMaximumWidth(300)
        self.tick_chart_label.setAlignment(Qt.AlignCenter)
        self.tick_chart_label.setFont(QFont("Arial", 8))

        self.tick_chart_layout = QVBoxLayout()
        self.tick_chart_layout.addWidget(self.tick_chart_label)
        self.tick_chart_layout.addWidget(self.tick_chart_view)

        # Create horizontal bar plot
        self.volume_bar_series = QBarSeries()
        self.volume_bar_set = QBarSet("Volume per 12 blocks")
        self.volume_bar_series.append(self.volume_bar_set)
        self.volume_chart = QChart()
        self.volume_chart.addSeries(self.volume_bar_series)
        self.volume_chart.createDefaultAxes()
        self.volume_chart_view = QChartView(self.volume_chart)
        self.volume_chart_view.setRenderHint(QPainter.Antialiasing)
        self.volume_chart_view.setMaximumHeight(300)  # Set the maximum height
        self.volume_chart.legend().hide() # Hide the legend

        self.volume_chart_label = QLabel("Volume per 12 blocks")
        self.volume_chart_label.setMaximumHeight(10)
        self.volume_chart_label.setAlignment(Qt.AlignCenter)
        self.volume_chart_label.setFont(QFont("Arial", 8))

        self.volume_chart_layout = QVBoxLayout()
        self.volume_chart_layout.addWidget(self.volume_chart_view)
        self.volume_chart_layout.addWidget(self.volume_chart_label)
        
        # Create a grid layout
        grid_layout = QGridLayout()

        # Add the rotated bar plot to the grid layout at row 0, column 0
        grid_layout.addLayout(self.tick_chart_layout, 0, 0)

        # Add the main chart to the grid layout at row 0, column 1
        grid_layout.addWidget(self.chart_view, 0, 1)

        # Add the horizontal bar plot to the grid layout at row 1, column 1
        grid_layout.addLayout(self.volume_chart_layout, 1, 1)

        # Add the table layout to the grid layout at row 0, column 2
        grid_layout.addLayout(self.table_layout, 0, 2)


        # Create a container and set it as the central widget
        container = QWidget()
        container.setLayout(grid_layout)
        self.setCentralWidget(container)


    def update_chart(self):

        current_block = self.state.current_block
        current_tick = self.state.current_tick
        tick_states = self.state.tick_states
        liquidity = self.state.current_liquidity

        if current_tick == None:

            chart_rect = self.chart.plotArea()
            self.text_item.setPos(chart_rect.center().x() - self.text_item.boundingRect().width() / 2,
                          chart_rect.center().y() - self.text_item.boundingRect().height() / 2)
            return
        elif self.previous_block == current_block:
            return
        
        # remove the text item
        self.text_item.setPlainText("")
        self.text_item.setPos(0, 0)

        self.upper_tick_line.append(0, 0)
        self.upper_tick_line.append(0, 0)

        self.lower_tick_line.append(0, 0)
        self.lower_tick_line.append(0, 0)

        # Clear the table
        self.open_positions_table.setRowCount(0)
        self.closed_positions_table.setRowCount(0)
        
        # Populate the table with open positions
        for index in self.position_manager.open_positions_index:

            position = self.position_manager.positions[index]
            meta_data = self.position_manager.positions_meta_data[index]

            lower_tick = position.lower_tick
            upper_tick = position.upper_tick

            value_hold = position.value_hold(current_tick) / 10**18
            value_position = position.value_position(current_tick) / 10**18

            diff = value_position - value_hold

            amount_x = position.amount_x(current_tick) / 10**6
            amount_y = position.amount_y(current_tick) / 10**18

            self.lower_tick_line.replace([QPointF(meta_data["block"], lower_tick), QPointF(current_block, lower_tick)])
            self.upper_tick_line.replace([QPointF(meta_data["block"], upper_tick), QPointF(current_block, upper_tick)])
            
            row_position = self.open_positions_table.rowCount()
            self.open_positions_table.insertRow(row_position)

            # Create QTableWidgetItem and set text alignment to center
            index_item = QTableWidgetItem(str(index))
            index_item.setTextAlignment(Qt.AlignCenter)

            amount_x_item = QTableWidgetItem(f"{amount_x:.2f}")
            amount_x_item.setTextAlignment(Qt.AlignCenter)

            amount_y_item = QTableWidgetItem(f"{amount_y:.6f}")
            amount_y_item.setTextAlignment(Qt.AlignCenter)

            value_position_item = QTableWidgetItem(f"{value_position:.6f}")
            value_position_item.setTextAlignment(Qt.AlignCenter)

            diff_item = QTableWidgetItem(f"{diff:.6f}")
            diff_item.setTextAlignment(Qt.AlignCenter)

            # Add items to the table
            self.open_positions_table.setItem(row_position, 0, index_item)
            self.open_positions_table.setItem(row_position, 1, amount_x_item)
            self.open_positions_table.setItem(row_position, 2, amount_y_item)
            self.open_positions_table.setItem(row_position, 3, value_position_item)  # Changed column index from 2 to 3
            self.open_positions_table.setItem(row_position, 4, diff_item)

        # Populate the table with closed positions
        for index in self.position_manager.closed_positions_index:

            position = self.position_manager.positions[index]
            performance = self.position_manager.performance[index]

            value_position = performance["value_position"] / 10**18
            value_hold = performance["value_hold"] / 10**18

            accumulated_fees = performance["accumulated_fees"]

            accumulated_fees_0 = accumulated_fees[0] / 10**18
            accumulated_fees_1 = accumulated_fees[1] / 10**18

            fees_total = accumulated_fees_0 + accumulated_fees_1
            
            row_position = self.closed_positions_table.rowCount()
            self.closed_positions_table.insertRow(row_position)

            # Create QTableWidgetItem and set text alignment to center
            index_item = QTableWidgetItem(str(index))
            index_item.setTextAlignment(Qt.AlignCenter)

            fees_total_item = QTableWidgetItem(f"{fees_total:.6f}")
            fees_total_item.setTextAlignment(Qt.AlignCenter)

            value_position_item = QTableWidgetItem(f"{value_position:.6f}")
            value_position_item.setTextAlignment(Qt.AlignCenter)

            performance_item = QTableWidgetItem(f"{(fees_total + value_position - value_hold):.6f}")
            performance_item.setTextAlignment(Qt.AlignCenter)

            # Add items to the table
            self.closed_positions_table.setItem(row_position, 0, index_item)
            self.closed_positions_table.setItem(row_position, 1, fees_total_item)
            self.closed_positions_table.setItem(row_position, 2, value_position_item)
            self.closed_positions_table.setItem(row_position, 3, performance_item)

        # Get value locked in the ticks around the current tick
        value_in_ticks, ticks = get_value_locked_for_tick_range(current_tick, liquidity, tick_states)
        if ticks != []:
            tick_categories = [str(int(t // 10 * 10)) for t in ticks[::-1]]
            tick_heights = value_in_ticks[::-1]

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
            tick_axis_y.setLabelsAngle(270)

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

        if self.counter > 300:  # keep a maximum of 300 points and remove older ones
            self.series.remove(0)
            for i in range(self.series.count()):
                point = self.series.at(i)
                x = point.x()
                y = point.y() 
                self.series.replace(i, x-1, y)


        self.new_x_axis.setRange(current_block - 300, current_block)
        self.new_x_axis.setTickCount(300 // 12)
        self.new_x_axis.setLabelFormat("%d")

        self.new_y_axis.setRange(current_tick - 100, current_tick + 100)
        self.new_y_axis.setTickCount(210 // 10)
        self.new_y_axis.setLabelFormat("%d")


        self.counter += 1
        self.previous_block = current_block

        return

if __name__ == '__main__':
    app = QApplication(sys.argv)

    contract = get_contract()
    node = get_provider()
    
    provider = Provider(node, contract, backtest=True, swap_data="data/Swap.csv", mint_data="data/Mint.csv", burn_data="data/Burn.csv")
    state = ProtocolState(provider)
    position_manager = PositionManager(provider, state)
    strategy = Strategy(provider, state, position_manager)

    state.start()
    strategy.start()

    window = MainWindow(state, position_manager, backtest=True)
    window.setWindowTitle("UniSwap v3 USDC-ETH Interface")
    window.setGeometry(100, 100, 800, 600)
    window.show()

    exit_code = app.exec()

    strategy.stop()
    state.stop()

    sys.exit(exit_code)
