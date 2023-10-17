import unittest
import math
from src.position import Position
from src.uniwap_math import tick_to_sqrt_price
from src.utils import real_reservers_to_virtal_reserves

class TestPosition(unittest.TestCase):

    def setUp(self):

        x_virt, y_virt, x_real = real_reservers_to_virtal_reserves(90000, 110000, 100000, tick_to_sqrt_price(100000) * 2**96, y_real=10**18)

        self.x_real = x_real
        self.y_real = 10**18

        self.liquidity = math.sqrt(x_virt * y_virt)

        self.position = Position(
            init=100000,
            lower=90000,
            upper=110000,
            liquidity=self.liquidity,
            fee_growth_inside_0_last=0,
            fee_growth_inside_1_last=0
        )

    def test_amount_x_in_range(self):
        current_tick = 100000
        amount_x = self.position.amount_x(current_tick)
        self.assertAlmostEqual(amount_x, self.x_real, places=12)

    def test_amount_x_below_range(self):
        current_tick = 80000
        amount_x = self.position.amount_x(current_tick)
        self.assertAlmostEqual(amount_x, 120310024470657.6, places=12)

    def test_amount_x_above_range(self):
        current_tick = 120000
        amount_x = self.position.amount_x(current_tick)
        self.assertAlmostEqual(amount_x, 0, places=12)

    def test_amount_y_in_range(self):
        current_tick = 100000
        amount_y = self.position.amount_y(current_tick)
        self.assertAlmostEqual(amount_y, self.y_real, places=18)

    def test_amount_y_below_range(self):
        current_tick = 80000
        amount_x = self.position.amount_y(current_tick)
        self.assertAlmostEqual(amount_x, 0, places=18)

    def test_amount_y_above_range(self):
        current_tick = 120000
        amount_x = self.position.amount_y(current_tick)
        self.assertAlmostEqual(amount_x, 2.6486800559310853e+18, places=18)


if __name__ == '__main__':
    unittest.main()
