import unittest
from calc import add, subtract, multiply, divide

class TestCalc(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(1, 2), 3)
        self.assertEqual(add(-1, 1), 0)
        self.assertEqual(add(-1, -1), -2)

    def test_subtract(self):
        self.assertEqual(subtract(1, 2), -1)
        self.assertEqual(subtract(-1, 1), -2)
        self.assertEqual(subtract(-1, -1), 0)

    def test_multiply(self):
        self.assertEqual(multiply(1, 2), 2)
        self.assertEqual(multiply(-1, 1), -1)
        self.assertEqual(multiply(-1, -1), 1)

    def test_divide(self):
        self.assertEqual(divide(3, 6), 0.5)
        self.assertEqual(divide(-3, 6), -0.5)
        self.assertIsNone(divide(3, 0), None)

if __name__ == '__main__':
    unittest.main()
