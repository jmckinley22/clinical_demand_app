import math
import os
import sys

# Ensure project root is on sys.path so tests can import local modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from clinical_demand import DosingParams, ProductParams, calculate_group_demand


def test_calculate_group_demand_basic():
    # Single product, no buffer
    prod = ProductParams(name="A", product_amount=50.0, admin_points=1, days=1)
    params = DosingParams(patients=10, products=[prod], buffer_pct=0)
    total, by_product = calculate_group_demand(params)
    assert math.isclose(total, 10 * 50.0 * 1 * 1)
    assert math.isclose(by_product.get("A", 0.0), 10 * 50.0 * 1 * 1)


def test_calculate_group_demand_with_buffer():
    # Two products, with buffer
    p1 = ProductParams(name="p1", product_amount=10.0, admin_points=2, days=3)
    p2 = ProductParams(name="p2", product_amount=10.0, admin_points=2, days=3)
    params = DosingParams(patients=5, products=[p1, p2], buffer_pct=10)
    # Each product: 5 * 10 * 2 * 3 = 300, with 10% buffer => 330
    expected_each = 5 * 10.0 * 2 * 3 * 1.10
    total, by_product = calculate_group_demand(params)
    assert math.isclose(total, expected_each * 2)
    assert math.isclose(by_product.get("p1", 0.0), expected_each)
    assert math.isclose(by_product.get("p2", 0.0), expected_each)
