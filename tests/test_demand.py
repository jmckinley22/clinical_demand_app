import math
import os
import sys

# Ensure project root is on sys.path so tests can import local modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from clinical_demand import DosingParams, calculate_group_demand


def test_calculate_group_demand_basic():
    params = DosingParams(patients=10, products=1, product_amount=50.0, admin_points=1, days=1, buffer_pct=0)
    assert math.isclose(calculate_group_demand(params), 10 * 1 * 50.0 * 1 * 1)


def test_calculate_group_demand_with_buffer():
    params = DosingParams(patients=5, products=2, product_amount=10.0, admin_points=2, days=3, buffer_pct=10)
    base = 5 * 2 * 10.0 * 2 * 3
    expected = base * 1.10
    assert math.isclose(calculate_group_demand(params), expected)
