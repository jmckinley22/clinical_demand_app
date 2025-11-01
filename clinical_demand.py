from dataclasses import dataclass


@dataclass
class DosingParams:
    patients: int
    products: int
    product_amount: float
    admin_points: int
    days: int
    buffer_pct: int


def calculate_group_demand(params: DosingParams) -> float:
    """Calculate total product amount needed for a dosing group.

    Mirrors the logic used in the notebook's Streamlit app.
    """
    base = (
        params.patients
        * params.products
        * params.product_amount
        * params.admin_points
        * params.days
    )
    return base * (1 + params.buffer_pct / 100.0)


def _example():
    # Example usage
    p = DosingParams(patients=10, products=1, product_amount=50.0, admin_points=1, days=28, buffer_pct=0)
    print(calculate_group_demand(p))


if __name__ == "__main__":
    _example()
