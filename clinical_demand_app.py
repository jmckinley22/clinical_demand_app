"""Streamlit front-end for Clinical Trial Patient Demand Calculator.

This provides a usable UI for non-technical users to configure trials and
calculate total patient-level demand. It leverages `clinical_demand.calculate_group_demand`.
"""
from dataclasses import asdict
from io import StringIO
import csv
from typing import List
import os
from datetime import datetime
import smtplib
from email.message import EmailMessage

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
    # Allow the user to name the trial (friendly for non-technical users)
    trial_name = st.text_input(f"Trial name (for display)", value=f"Trial {trial_index}", key=f"trial_{trial_index}_name")
    st.subheader(trial_name)

    num_groups = st.number_input(f"Number of treatment groups ({trial_name})", min_value=1, max_value=12, value=2, step=1, key=f"trial_{trial_index}_groups")
    trial_total = 0.0
    groups: List[dict] = []

    for group_index in range(1, int(num_groups) + 1):
        prefix = f"trial{trial_index}_group{group_index}"
        # Allow the user to give each group a friendly name
        group_name = st.text_input(f"Group name (Trial {trial_index} - Group {group_index})", value=f"Group {group_index}", key=f"{prefix}_name")
        with st.expander(group_name):
            params = group_inputs(prefix)
            demand = calculate_group_demand(params)
            trial_total += demand
            groups.append({**asdict(params), "demand": int(round(demand)), "trial": trial_index, "trial_name": trial_name, "group": group_index, "group_name": group_name})
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


def save_csv_to_disk(csv_content: str, filename: str | None = None) -> str:
    """Save CSV content to disk under `outputs/` and return the file path."""
    os.makedirs("outputs", exist_ok=True)
    if not filename:
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        filename = f"demand_breakdown_{timestamp}.csv"
    path = os.path.join("outputs", filename)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(csv_content)
    return path


def send_email_with_attachment(smtp_server: str, smtp_port: int, username: str, password: str, from_addr: str, to_addr: str, subject: str, body: str, attachment_bytes: bytes, attachment_name: str) -> None:
    """Send an email with a single attachment using SMTP (supports STARTTLS or SSL)."""
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)
    msg.add_attachment(attachment_bytes, maintype="text", subtype="csv", filename=attachment_name)

    # Choose SSL port vs STARTTLS based on common port numbers
    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(username, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(username, password)
            server.send_message(msg)


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

        # Always prepare CSV content in case user wants to save or email it
        csv_content = format_csv(all_groups)

        if show_breakdown and all_groups:
            st.markdown("### Demand breakdown by trial and group")
            st.dataframe(all_groups)
            st.download_button("Download breakdown CSV", data=csv_content, file_name="demand_breakdown.csv", mime="text/csv")

            # Save to server button
            if st.button("Save breakdown to server (outputs/)"):
                try:
                    saved_path = save_csv_to_disk(csv_content)
                    st.success(f"Saved CSV to {saved_path}")
                except Exception as e:
                    st.error(f"Error saving CSV: {e}")

        # Email sending controls in the sidebar (keeps UI uncluttered)
        with st.sidebar.expander("Email results (SMTP)"):
            st.markdown("Send the generated CSV as an email attachment. Enter SMTP details below.")
            smtp_server = st.text_input("SMTP server (e.g. smtp.gmail.com)")
            smtp_port = st.number_input("SMTP port", value=587, min_value=1, max_value=65535)
            smtp_user = st.text_input("SMTP username")
            smtp_pass = st.text_input("SMTP password", type="password")
            from_email = st.text_input("From email address")
            to_email = st.text_input("To email address (comma-separated)")
            subject = st.text_input("Email subject", value="Clinical trial demand results")
            message = st.text_area("Email body", value="Attached is the demand breakdown CSV.")

            if st.button("Send CSV by email"):
                if not csv_content:
                    st.error("No CSV content available to send. Ensure you have generated a breakdown first.")
                elif not smtp_server or not smtp_user or not smtp_pass or not from_email or not to_email:
                    st.error("Please fill in all SMTP and email fields before sending.")
                else:
                    try:
                        # support multiple recipients
                        recipients = [addr.strip() for addr in to_email.split(",") if addr.strip()]
                        attachment_name = f"demand_breakdown_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.csv"
                        send_email_with_attachment(smtp_server=smtp_server, smtp_port=int(smtp_port), username=smtp_user, password=smtp_pass, from_addr=from_email, to_addr=", ".join(recipients), subject=subject, body=message, attachment_bytes=csv_content.encode("utf-8"), attachment_name=attachment_name)
                        st.success(f"Email sent to: {', '.join(recipients)}")
                    except Exception as e:
                        st.error(f"Error sending email: {e}")

    st.sidebar.markdown("---")
    st.sidebar.markdown("Made with ❤️ — enter trial parameters and download results.")


if __name__ == "__main__":
    main()
