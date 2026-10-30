"""
Unit tests for deterministic financial calculations using Python standard library unittest.
"""

import unittest


def calculate_savings_rate(income: float, expense: float) -> float:
    if income <= 0:
        return 0.0
    net = income - expense
    return round((net / income) * 100, 1)


def calculate_student_safe_daily_budget(balance: float, days_left: int) -> float:
    if days_left <= 0:
        return 0.0
    safe_balance = max(0.0, balance)
    return round(safe_balance / days_left, 2)


def calculate_scenario_roi(initial_cost: float, net_monthly: float, horizon_months: int):
    total_net = (net_monthly * horizon_months) - initial_cost
    roi = round((total_net / initial_cost * 100), 2) if initial_cost > 0 else 0.0
    break_even = round(initial_cost / net_monthly, 1) if net_monthly > 0 and initial_cost > 0 else None
    return roi, break_even


class TestFinancialCalculations(unittest.TestCase):
    def test_savings_rate(self):
        self.assertEqual(calculate_savings_rate(100000.0, 70000.0), 30.0)
        self.assertEqual(calculate_savings_rate(0.0, 500.0), 0.0)
        self.assertEqual(calculate_savings_rate(50000.0, 60000.0), -20.0)

    def test_student_burn_rate(self):
        # 15,000 allowance with 15 days remaining = 1,000/day
        self.assertEqual(calculate_student_safe_daily_budget(15000.0, 15), 1000.0)
        self.assertEqual(calculate_student_safe_daily_budget(0.0, 10), 0.0)
        self.assertEqual(calculate_student_safe_daily_budget(-500.0, 10), 0.0)

    def test_scenario_roi_and_breakeven(self):
        roi, break_even = calculate_scenario_roi(100000.0, 25000.0, 12)
        self.assertEqual(roi, 200.0)
        self.assertEqual(break_even, 4.0)


if __name__ == "__main__":
    unittest.main()
