"""Core calculation logic for clinical trial patient demand.

This module defines simple dataclasses and functions to compute product-level
and group-level demand. The main public function used by the Streamlit app is
`calculate_group_demand` which returns (total_mg, {product_name: mg}).
"""
from dataclasses import dataclass
from typing import List, Dict, Tuple


@dataclass
class ProductParams:
    name: str
    product_amount: float  # mg per administration
    admin_points: int      # administrations per day
    days: int              # total days of administration


@dataclass
class DosingParams:
    patients: int
    products: List[ProductParams]  # List of product-specific parameters
    buffer_pct: int = 0


def calculate_product_demand(patients: int, params: ProductParams, buffer_pct: int = 0) -> float:
    """Calculate demand (mg) for a single product configuration.

    Returns the total mg required for `patients` participants for the given
    product parameters, including buffer percentage.
    """
    base = patients * params.product_amount * params.admin_points * params.days
    return base * (1 + buffer_pct / 100.0)


def calculate_group_demand(params: DosingParams) -> Tuple[float, Dict[str, float]]:
    """Calculate total demand and per-product breakdown for a group.

    Returns a tuple (total_mg, by_product) where by_product maps product
    names to their respective mg totals.
    """
    total = 0.0
    by_product: Dict[str, float] = {}

    for product in params.products:
        if not product:
            continue
        amount = calculate_product_demand(params.patients, product, params.buffer_pct)
        by_product[product.name] = by_product.get(product.name, 0.0) + amount
        total += amount

    return total, by_product


if __name__ == "__main__":
    # Quick self-check
    p = DosingParams(patients=10, products=[ProductParams(name="A", product_amount=50.0, admin_points=1, days=28)])
    print(calculate_group_demand(p))
