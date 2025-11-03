"""Streamlit front-end for Clinical Trial Patient Demand Calculator.

This provides a usable UI for non-technical users to configure trials and
calculate total patient-level demand. It leverages `clinical_demand.calculate_group_demand`.
"""
import streamlit as st

# Must set page config before any other Streamlit commands
st.set_page_config(
    page_title="Clinical Trial Demand Calculator",
    layout="wide",  # Use full screen width
    initial_sidebar_state="expanded",  # Show sidebar by default
    menu_items={
        'Get Help': 'https://github.com/jmckinley22/dad_math',
        'Report a bug': 'https://github.com/jmckinley22/dad_math/issues',
        'About': 'Clinical Trial Patient Demand Calculator - Calculate total product demand across multiple trials.'
    }
)

from dataclasses import asdict
from io import StringIO
import csv
from typing import List, Optional
import os
from datetime import datetime
import smtplib
from email.message import EmailMessage
import re

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


def format_csv(rows: List[dict], summary: Optional[dict] = None) -> str:
    """Return CSV string of rows with optional summary header lines.

    If summary is provided, key,value pairs are written at the top as comment-style lines,
    followed by a blank line and then the regular CSV table.
    """
    if not rows and not summary:
        return ""

    output = StringIO()
    # Write summary lines first
    if summary:
        for k, v in summary.items():
            output.write(f"# {k}: {v}\n")
        output.write("\n")

    if rows:
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


def slugify(value: str) -> str:
    """Simple filename-safe slugifier: keep alphanum and underscores."""
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9 _-]", "", value)
    value = re.sub(r"[\s-]+", "_", value)
    return value


def list_saved_csvs(directory: str = "outputs") -> List[str]:
    if not os.path.isdir(directory):
        return []
    files = [f for f in os.listdir(directory) if f.lower().endswith(".csv")]
    files = sorted(files, key=lambda f: os.path.getmtime(os.path.join(directory, f)), reverse=True)
    return files


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
    st.title("Clinical Trial Demand Calculator")
    st.write("")  # Add space after title
    st.markdown(
        "Use the controls to model trials and treatment groups. Results show total product administrations needed (including buffer)."
    )
    st.write("")  # Add space after intro

    col1, col2 = st.columns([2, 3])  # More balanced ratio

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
        summary = {
            "Title": st.session_state.get("scenario_title", ""),
            "GeneratedAtUTC": datetime.utcnow().isoformat(),
            "TotalDemand": int(round(total_demand)),
            "NumTrials": int(num_trials),
        }

        csv_content = format_csv(all_groups, summary=summary)
        # Persist the latest generated CSV in session state so reloads or
        # reruns (which Streamlit does on page refresh) still have access to it.
        try:
            st.session_state["_last_csv"] = csv_content
        except Exception:
            # If session state isn't available for some reason, continue without persisting.
            pass

        if show_breakdown and all_groups:
            st.markdown("### Demand breakdown by trial and group")
            st.dataframe(all_groups)
            st.download_button("Download breakdown CSV", data=csv_content, file_name="demand_breakdown.csv", mime="text/csv")

            # Save to server button (with optional title included in filename)
            if st.button("Save breakdown to server (outputs/)"):
                try:
                    title = st.session_state.get("scenario_title")
                    filename = None
                    if title:
                        filename = f"{slugify(title)}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.csv"
                    saved_path = save_csv_to_disk(csv_content, filename=filename)
                    st.success(f"Saved CSV to {saved_path}")
                except Exception as e:
                    st.error(f"Error saving CSV: {e}")

    # Sidebar: saved files listing and email/send options
    with st.sidebar:
        st.markdown("### Saved CSVs & Email")
        st.write("")  # Add space for readability
        st.markdown("#### Saved Files")
        saved = list_saved_csvs()
        selected = None
        selected_path = None
        if saved:
            selected = st.selectbox("Select a saved CSV", options=saved)
            selected_path = os.path.join("outputs", selected)
            st.write("Saved file:", selected)
            # Download selected file
            try:
                with open(selected_path, "rb") as fh:
                    data_bytes = fh.read()
                st.download_button("Download selected CSV", data=data_bytes, file_name=selected, mime="text/csv")
            except Exception:
                st.info("Unable to read selected file (it may have been removed).")

            st.markdown("---")
        else:
            st.info("No saved CSVs found in outputs/")

        st.markdown("### Email (send current or selected CSV)")
        st.markdown("Send the CSV as an email attachment. You can either send the currently generated CSV or a previously saved file.")
        # Allow environment variables to pre-fill SMTP settings for safer automation.
        env_smtp_server = os.environ.get("SMTP_SERVER", "")
        env_smtp_port = os.environ.get("SMTP_PORT", "")
        try:
            default_smtp_port = int(env_smtp_port) if env_smtp_port and env_smtp_port.isdigit() else 587
        except Exception:
            default_smtp_port = 587
        env_smtp_user = os.environ.get("SMTP_USER", "")
        env_smtp_pass = os.environ.get("SMTP_PASS", "")
        env_from_email = os.environ.get("FROM_EMAIL", "")

        smtp_server = st.text_input("SMTP server (e.g. smtp.gmail.com)", value=env_smtp_server, key="smtp_server")
        smtp_port = st.number_input("SMTP port", value=default_smtp_port, min_value=1, max_value=65535, key="smtp_port")
        smtp_user = st.text_input("SMTP username", value=env_smtp_user, key="smtp_user")
        smtp_pass = st.text_input("SMTP password", type="password", value=env_smtp_pass, key="smtp_pass")
        from_email = st.text_input("From email address", value=env_from_email, key="from_email")
        to_email = st.text_input("To email address (comma-separated)", key="to_email")
        subject = st.text_input("Email subject", value="Clinical trial demand results", key="email_subject")
        message = st.text_area("Email body", value="Attached is the demand breakdown CSV.", key="email_body")

        choice = st.radio("Attachment to send", options=("Current CSV", "Saved CSV"), key="email_choice")
        if st.button("Send email with attachment"):
            try:
                # determine attachment bytes
                if choice == "Saved CSV":
                    if not saved or not selected_path:
                        st.error("No saved file available to send.")
                        st.stop()
                    try:
                        with open(selected_path, "rb") as fh:
                            attachment_bytes = fh.read()
                        attachment_name = selected
                    except Exception as e:
                        st.error(f"Error reading selected file: {e}")
                        st.stop()
                else:
                    # Prefer the last persisted CSV in session state (survives reruns)
                    attachment_str = st.session_state.get("_last_csv")
                    if not attachment_str:
                        attachment_str = csv_content if 'csv_content' in locals() else None
                    attachment_bytes = attachment_str.encode("utf-8") if attachment_str else None
                    attachment_name = f"demand_breakdown_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.csv"

                if not attachment_bytes:
                    st.error("No attachment available to send.")
                    st.stop()

                if not smtp_server or not smtp_user or not smtp_pass or not from_email or not to_email:
                    st.error("Please fill in all SMTP and email fields before sending.")
                    st.stop()

                recipients = [addr.strip() for addr in to_email.split(",") if addr.strip()]
                send_email_with_attachment(smtp_server=smtp_server, smtp_port=int(smtp_port), username=smtp_user, password=smtp_pass, from_addr=from_email, to_addr=", ".join(recipients), subject=subject, body=message, attachment_bytes=attachment_bytes, attachment_name=attachment_name)
                st.success(f"Email sent to: {', '.join(recipients)}")
            except Exception as e:
                # Catch-all to ensure a reload doesn't raise an uncaught exception
                st.error(f"Error sending email: {e}")
