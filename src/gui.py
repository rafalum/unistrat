import sys
import time
import random
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QPainter, QBrush, QFont
from PySide6.QtCharts import QChart, QChartView, QLineSeries
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel

from utils import get_contract, get_provider

from strategy import Strategy
from provider import Provider
from position import Position
from protocol_state import ProtocolState
from position_manager import PositionManager

class MainWindow(QMainWindow):
    def __init__(self, state, position_manager):
        super().__init__()

        # Styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: #333;
            }
            QChartView {
                border: none;
            }
            QLabel {
                font-size: 16px;
                color: white;
            }
        """)

        self.state = state
        self.position_manager = position_manager

        self.series = QLineSeries()
        self.chart = QChart()

        self.upper_tick_line = QLineSeries()
        self.lower_tick_line = QLineSeries()

        self.chart.addSeries(self.upper_tick_line)
        self.chart.addSeries(self.lower_tick_line)

        # Chart styling
        self.chart.setBackgroundBrush(QBrush(Qt.darkGray))
        self.chart.setTitleBrush(QBrush(Qt.white))

        self.chart.addSeries(self.series)
        self.chart.createDefaultAxes()
        self.chart.setTitle("Price Chart")
        self.chart.legend().hide()

        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(QPainter.Antialiasing)

        self.info_label = QLabel("Latest Price: N/A")
        self.info_label.setFont(QFont("Arial", 16))
        self.info_label.setStyleSheet("color: white;")

        self.counter = 0

        layout = QVBoxLayout()
        layout.addWidget(self.info_label)
        layout.addWidget(self.chart_view)

        container = QWidget()
        container.setLayout(layout)

        self.setCentralWidget(container)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_chart)
        self.timer.start(1000)  # update every 1000 ms (1 second)

        self.x_axis = self.chart_view.chart().axes(Qt.Horizontal)[0]
        self.y_axis = self.chart_view.chart().axes(Qt.Vertical)[0]


    def update_chart(self):
        current_block = self.state.current_block
        current_tick = self.state.current_tick

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


        self.series.append(current_block, current_tick)


        if self.counter > 300:  # keep a maximum of 20 points and remove older ones
            self.series.remove(0)
            for i in range(self.series.count()):
                point = self.series.at(i)
                x = point.x()
                y = point.y() 
                self.series.replace(i, x-1, y)


        self.x_axis.setRange(current_block - 300, current_block)
        self.y_axis.setRange(self.series.at(0).y() - 200, self.series.at(0).y() + 200)

        self.counter += 1

if __name__ == '__main__':
    app = QApplication(sys.argv)

    contract = get_contract()
    node = get_provider()
    
    provider = Provider(node, contract, backtest=True, data="../tinker/data/USDC_ETH_SWAPS_reduced.csv")
    state = ProtocolState(provider)
    position_manager = PositionManager(provider, state)
    strategy = Strategy(provider, state, position_manager)

    state.start()
    time.sleep(5)
    strategy.start()

    window = MainWindow(state, position_manager)
    window.setWindowTitle("Styled Real-time Price Chart")
    window.setGeometry(100, 100, 800, 600)
    window.show()

    exit_code = app.exec()

    strategy.stop()
    state.stop()

    sys.exit(exit_code)
