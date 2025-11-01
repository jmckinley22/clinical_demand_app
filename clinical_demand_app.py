"""Streamlit front-end for Clinical Trial Patient Demand Calculator.

This provides a usable UI for non-technical users to configure trials and
calculate total patient-level demand. It leverages `clinical_demand.calculate_group_demand`.
"""
from dataclasses import asdict
from io import StringIO
import csv
from typing import List

import streamlit as st

from clinical_demand import DosingParams, calculate_group_demand


def group_inputs(prefix: str):
    patients = st.number_input("Patients", min_value=1, max_value=10000, value=50, step=1, key=f"{prefix}_patients")
    products = st.number_input("Products per trial", min_value=1, max_value=20, value=1, step=1, key=f"{prefix}_products")
    product_amount = st.number_input("Product per administration (mg)", min_value=0.0, value=50.0, step=0.1, format="%.2f", key=f"{prefix}_amount")
    admin_points = st.number_input("Administration points / day", min_value=1, max_value=24, value=1, step=1, key=f"{prefix}_points")
    days = st.number_input("Days of administration", min_value=1, max_value=365, value=28, step=1, key=f"{prefix}_days")
    buffer_pct = st.number_input("Contingency buffer (%)", min_value=0, max_value=100, value=0, step=1, key=f"{prefix}_buffer")
    return DosingParams(
        patients=int(patients),
        products=int(products),
        product_amount=float(product_amount),
        admin_points=int(admin_points),
        days=int(days),
        buffer_pct=int(buffer_pct),
    )


def trial_section(trial_index: int):
    st.subheader(f"Trial {trial_index}")
    num_groups = st.number_input(f"Number of treatment groups (Trial {trial_index})", min_value=1, max_value=12, value=2, step=1, key=f"trial_{trial_index}_groups")
    trial_total = 0.0
    groups: List[dict] = []

    for group_index in range(1, int(num_groups) + 1):
        with st.expander(f"Group {group_index}"):
            prefix = f"trial{trial_index}_group{group_index}"
            params = group_inputs(prefix)
            demand = calculate_group_demand(params)
            trial_total += demand
            groups.append({**asdict(params), "demand": int(round(demand)), "trial": trial_index, "group": group_index})
            st.markdown(f"**Group demand:** {int(round(demand)):,}")

    return trial_total, groups


def format_csv(rows: List[dict]) -> str:
    if not rows:
        return ""
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def main():
    st.set_page_config(page_title="Clinical Trial Demand Calculator", layout="wide")
    st.title("Clinical Trial Patient Demand Calculator")

    st.markdown(
        "Use the controls to model trials and treatment groups. Results show total product administrations needed (including buffer)."
    )

    col1, col2 = st.columns([1, 3])

    with col1:
        num_trials = st.number_input("Number of trials to model", min_value=1, max_value=10, value=1, step=1)
        show_breakdown = st.checkbox("Show per-group breakdown (CSV)", value=True)
        st.markdown("---")
        st.markdown("Quick actions:")
        if st.button("Reset to defaults"):
            st.experimental_rerun()

    all_groups = []
    total_demand = 0.0

    with col2:
        for t in range(1, int(num_trials) + 1):
            trial_total, groups = trial_section(t)
            total_demand += trial_total
            all_groups.extend(groups)

        st.markdown("---")
        st.metric("Total Patient Demand (all trials)", f"{int(round(total_demand)):,}")

        if show_breakdown and all_groups:
            st.markdown("### Demand breakdown by trial and group")
            st.dataframe(all_groups)
            csv_content = format_csv(all_groups)
            st.download_button("Download breakdown CSV", data=csv_content, file_name="demand_breakdown.csv", mime="text/csv")

    st.sidebar.markdown("---")
    st.sidebar.markdown("Made with ❤️ — enter trial parameters and download results.")


if __name__ == "__main__":
    main()
