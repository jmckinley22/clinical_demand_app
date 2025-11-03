"""Streamlit front-end for Clinical Trial Patient Demand Calculator.

This provides a usable UI for non-technical users to configure trials and
calculate total patient-level demand. It leverages `clinical_demand.calculate_group_demand`.
"""
# Standard library imports first
from dataclasses import asdict
from io import StringIO
import csv
from typing import List, Optional, Dict, Tuple
import os
from datetime import datetime
import smtplib
from email.message import EmailMessage
import re

# Third-party imports
import pandas as pd
import streamlit as st

# Local imports
from clinical_demand import DosingParams, ProductParams, calculate_group_demand

# Must set page config before creating any UI elements
st.set_page_config(
    page_title="Clinical Trial Demand Calculator",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/jmckinley22/clinical_demand_app#readme',
        'Report a bug': 'https://github.com/jmckinley22/clinical_demand_app/issues/new',
        'About': '''
        Clinical Trial Patient Demand Calculator
        
        Calculate total product demand across multiple trials and treatment groups.
        Source code: https://github.com/jmckinley22/clinical_demand_app
        '''
    }
)


def product_inputs(prefix: str, index: int):
    st.markdown(f"#### Product {index}")
    # Product name selector (choose existing or add new)
    def get_product_names() -> List[str]:
        if "product_names" not in st.session_state:
            st.session_state.product_names = []
        return st.session_state.product_names

    def add_product_name(name: str) -> None:
        if name and name not in get_product_names():
            st.session_state.product_names.append(name)

    def select_or_add_product(key: str, label: str = "Product name") -> str:
        names = get_product_names()
        options = ["Add New Product..."] + names
        choice = st.selectbox(label, options=options, key=f"{key}_select")
        if choice == "Add New Product...":
            new_name = st.text_input("Enter new product name", key=f"{key}_new")
            if new_name:
                add_product_name(new_name)
                return new_name
            return ""
        return choice

    product_name = select_or_add_product(f"{prefix}_prod{index}")
    product_amount = st.number_input("Product per administration (mg)",
                                   min_value=0.0, value=50.0, step=0.1, format="%.2f",
                                   key=f"{prefix}_product{index}_amount")
    admin_points = st.number_input("Administration points / day",
                                 min_value=1, max_value=24, value=1, step=1,
                                 key=f"{prefix}_product{index}_points")
    days = st.number_input("Days of administration",
                          min_value=1, max_value=365, value=28, step=1,
                          key=f"{prefix}_product{index}_days")

    # If the user hasn't provided a product name yet, return None so the caller
    # can filter out incomplete product entries.
    if not product_name:
        return None

    return ProductParams(
        name=product_name,
        product_amount=float(product_amount),
        admin_points=int(admin_points),
        days=int(days)
    )

def group_inputs(prefix: str):
    patients = st.number_input("Patients", min_value=1, max_value=10000, value=50, step=1, key=f"{prefix}_patients")
    num_products = st.number_input("Number of distinct products", min_value=1, max_value=20, value=1, step=1, key=f"{prefix}_num_products")
    buffer_pct = st.number_input("Contingency buffer (%)", min_value=0, max_value=100, value=0, step=1, key=f"{prefix}_buffer")
    
    products = []
    if num_products > 1:
        st.markdown("### Product-specific parameters")
        st.info("Configure dosing for each distinct product in this treatment group")
    
    for i in range(1, int(num_products) + 1):
        with st.expander(f"Product {i} Configuration", expanded=(i == 1)):
            product = product_inputs(prefix, i)
            products.append(product)
    
    return DosingParams(
        patients=int(patients),
        products=products,
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
            # calculate_group_demand now returns (total, by_product)
            group_total, group_by_product = calculate_group_demand(params)
            trial_total += group_total
            # Store group details and per-product breakdown for CSV/inspection
            group_record = {**asdict(params), "demand_mg": int(round(group_total)), "trial": trial_index, "trial_name": trial_name, "group": group_index, "group_name": group_name, "product_breakdown": group_by_product}
            groups.append(group_record)
            st.markdown(f"**Group demand:** {int(round(group_total)):,} mg")
            if group_by_product:
                st.markdown("**Product breakdown:**")
                for pname, amt in group_by_product.items():
                    st.markdown(f"- {pname}: {int(round(amt)):,} mg")

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
        # Write rows assuming they are already expanded to include per-product mg columns
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return output.getvalue()


def expand_product_rows(rows: List[dict]) -> Tuple[List[dict], Dict[str, str]]:
    """Return expanded rows + mapping of original product name -> sanitized name.

    Expanded rows will have one column per sanitized product name with suffix
    '_mg'. The function also returns a mapping from original product name to
    sanitized token so callers can generate matching summary rows.
    """
    if not rows:
        return [], {}

    # Collect all product names across rows
    product_names = set()
    for r in rows:
        pb = r.get("product_breakdown")
        if isinstance(pb, dict):
            product_names.update(pb.keys())

    # Create sanitized column names using slugify (defined elsewhere). Handle collisions.
    sanitized_map: Dict[str, str] = {}
    used = set()
    for name in sorted(product_names):
        san = slugify(name)
        base = san
        i = 1
        while san in used:
            san = f"{base}_{i}"
            i += 1
        used.add(san)
        sanitized_map[name] = san

    expanded: List[dict] = []
    for r in rows:
        # Exclude nested breakdown, per-group aggregate keys, and the
        # raw `products` list from CSV rows (we expand products into
        # separate per-product _mg columns instead).
        newr = {k: v for k, v in r.items() if k not in ("product_breakdown", "demand_mg", "demand", "products")}
        # Ensure consistent types for CSV (primitives)
        for k, v in list(newr.items()):
            if isinstance(v, (list, dict)):
                newr[k] = str(v)

        pb = r.get("product_breakdown") or {}
        for orig_name, san in sorted(sanitized_map.items(), key=lambda kv: kv[1]):
            col = f"{san}_mg"
            amt = pb.get(orig_name, 0.0)
            newr[col] = int(round(amt)) if amt is not None else 0

        expanded.append(newr)

    return expanded, sanitized_map


def coerce_arrow_friendly_dataframe(rows: List[dict]) -> "pd.DataFrame":
    """Return a DataFrame with column types coerced for Arrow compatibility.

    Streamlit relies on Arrow tables for fast rendering. Mixed object columns
    (like ints plus empty strings) trigger conversion errors. We replace empty
    strings with NA, coerce numeric-like columns to numeric dtypes, and cast the
    remaining object columns to pandas' nullable string dtype.
    """
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    for col in df.columns:
        if df[col].dtype != object:
            continue

        series = df[col].replace("", pd.NA)
        non_na = series.dropna()

        if not non_na.empty:
            numeric_coerced = pd.to_numeric(non_na, errors="coerce")
            if not numeric_coerced.isna().any():
                df[col] = pd.to_numeric(series, errors="coerce")
                # If values are all whole numbers, use pandas nullable Int64 dtype.
                if pd.api.types.is_float_dtype(df[col]) and not df[col].dropna().mod(1).any():
                    df[col] = df[col].astype("Int64")
                continue

        df[col] = series.astype("string")

    return df


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


def inject_custom_css(dark_mode: bool = False) -> None:
        """Inject custom CSS for scroll snapping and optional dark mode.

        The CSS attempts to target common Streamlit scrollable containers and
        force children to snap to the left/start when horizontally scrolling.
        Dark mode overrides a few key variables for a comfortable dark theme.
        """
        base_css = r"""
        /* Force horizontal scroll containers to snap to start (left) */
        [style*='overflow'] {
            scroll-snap-type: x mandatory !important;
            -webkit-overflow-scrolling: touch !important;
        }
        [style*='overflow'] > * {
            scroll-snap-align: start !important;
            scroll-padding-left: 0 !important;
        }

        /* Dataframe and table wrappers (common Streamlit containers) */
        .stDataFrame, .element-container, .css-1d391kg, .streamlit-expander {
            scroll-snap-type: x mandatory !important;
        }

        /* Make sure content is left-aligned inside scrollable areas */
        .stDataFrame div[role='table'], .stDataFrame table, .stDataFrame tbody, .stDataFrame thead {
            text-align: left !important;
        }

        /* Slight smoothing for scroll snapping */
        html {
            scroll-behavior: smooth;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }
        """

        dark_css = r"""
        /* Basic dark mode overrides */
        :root { --bg: #0b1220; --card: #0f1724; --text: #e6eef8; --accent: #2b8cff; }
        .stApp, .stApp .main, .stApp .block-container {
            background-color: var(--bg) !important;
            color: var(--text) !important;
        }
        .stMarkdown, .stMetric, .stDataFrame, .stExpander {
            color: var(--text) !important;
        }
        .css-1d391kg, .element-container, .streamlit-expander {
            background: var(--card) !important;
            color: var(--text) !important;
        }
        a { color: var(--accent) !important; }
        """

        css = base_css
        if dark_mode:
                css = dark_css + "\n" + base_css

        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


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
    st.markdown("Made by Jackson McKinley - github.com/jmckinley22/clinical_demand_app")
    st.markdown(
        "Use the controls to model trials and treatment groups. Results show total product administrations needed (including buffer)."
    )
    st.write("")  # Add space after intro
    # Top-level trial selector (appear above per-trial/group controls)
    num_trials = st.number_input("Number of trials to model", min_value=1, max_value=10, value=1, step=1)

    # Track whether totals should be shown. We default to not showing totals
    # until the user chooses to calculate them. When the user increases the
    # number of trials we automatically enable calculation so totals reflect
    # the newest trial set.
    if "_prev_num_trials" not in st.session_state:
        st.session_state["_prev_num_trials"] = int(num_trials)
    # If the user changed the number of trials, mark for automatic calculation
    if int(num_trials) != int(st.session_state.get("_prev_num_trials", num_trials)):
        st.session_state["_prev_num_trials"] = int(num_trials)
        st.session_state["_show_totals"] = True

    # Ensure the flag exists (default hidden until user chooses)
    if "_show_totals" not in st.session_state:
        st.session_state["_show_totals"] = False

    # Actions dropdown in the sidebar (serves as the "menu dropdown" for quick actions)
    action = st.sidebar.selectbox("Actions", options=("None", "Reset to defaults"))
    if action == "Reset to defaults":
        # Clear session state fully and rerun to present a clean slate.
        for k in list(st.session_state.keys()):
            try:
                del st.session_state[k]
            except Exception:
                pass
        st.rerun()

    # Dark mode toggle in the sidebar (controls CSS injection)
    dark_mode = st.sidebar.checkbox("Dark mode", value=False, key="dark_mode")

    # Inject CSS after the user's theme choice is known
    inject_custom_css(dark_mode=dark_mode)

    # Render trials and groups at full page width so they match the width of
    # the top-level `num_trials` control above.
    all_groups = []
    total_demand = 0.0

    for t in range(1, int(num_trials) + 1):
        trial_total, groups = trial_section(t)
        total_demand += trial_total
        all_groups.extend(groups)

        st.markdown("---")

        # Compute per-product totals across all groups
        product_totals: dict = {}
        for g in all_groups:
            pb = g.get("product_breakdown") or {}
            for pname, amt in pb.items():
                product_totals[pname] = product_totals.get(pname, 0.0) + amt

        # Prepare summary header (include product totals; omit overall TotalDemand)
        summary = {
            "Title": st.session_state.get("scenario_title", ""),
            "GeneratedAtUTC": datetime.utcnow().isoformat(),
            "NumTrials": int(num_trials),
        }
        # Add product totals into summary with clear keys
        for pname, amt in sorted(product_totals.items()):
            summary[f"{pname}_total_mg"] = int(round(amt))

        # Expand per-group product breakdown into separate columns for display and CSV
        expanded_rows, sanitized_map = expand_product_rows(all_groups)

        # Append a bottom summary row with per-product totals (sanitized column names)
        if expanded_rows:
            keys = list(expanded_rows[0].keys())
            summary_row = {k: "" for k in keys}
            # Prefer to label the summary row in a present label column
            label_key = None
            for candidate in ("group_name", "trial_name", "group", "trial"):
                if candidate in summary_row:
                    label_key = candidate
                    break
            if label_key:
                summary_row[label_key] = "TOTAL"
            else:
                summary_row[keys[0]] = "TOTAL"

            # Fill product totals using sanitized map
            for orig_name, san in sanitized_map.items():
                col = f"{san}_mg"
                amt = product_totals.get(orig_name, 0.0)
                summary_row[col] = int(round(amt)) if amt is not None else 0

            # Also fill the total number of patients across all groups if a
            # `patients` column exists in the expanded rows. Compute total
            # patients from the original `all_groups` records which include
            # the `patients` field coming from asdict(params).
            try:
                total_patients = sum(int(g.get("patients", 0)) for g in all_groups)
            except Exception:
                total_patients = 0
            if "patients" in summary_row:
                summary_row["patients"] = int(total_patients)

            expanded_rows.append(summary_row)

        csv_content = format_csv(expanded_rows, summary=summary)
        # Persist the latest generated CSV in session state so reloads or
        # reruns (which Streamlit does on page refresh) still have access to it.
        try:
            st.session_state["_last_csv"] = csv_content
        except Exception:
            # If session state isn't available for some reason, continue without persisting.
            pass

        # Show product totals in a prominent summary layout only when the
        # user has chosen to calculate totals (or when auto-enabled by adding
        # a trial). This avoids showing intermediate values while the user
        # is still editing trial inputs.
        if product_totals and st.session_state.get("_show_totals", False):
            st.markdown("### Product Totals Summary")
            # Stack product totals vertically (one per row) for easier scanning
            for pname, amt in sorted(product_totals.items()):
                st.metric(label=f"Total {pname}", value=f"{int(round(amt)):,} mg")

    # Allow the user to toggle the CSV/table breakdown display near the
    # bottom of the page (moved from the left column per request).
    # Provide an explicit key to avoid duplicate-element errors when the
    # page renders multiple times or when trials are added dynamically.
    show_breakdown = st.checkbox("Show per-group breakdown (CSV)", value=True, key="show_breakdown")

    if show_breakdown and expanded_rows:
        st.markdown("### Demand breakdown by trial and group")
        breakdown_df = coerce_arrow_friendly_dataframe(expanded_rows)
        st.dataframe(breakdown_df)
        # Allow the user to name the file before downloading. Persist the
        # choice in session state so it survives reruns.
        default_name = st.session_state.get(
            "_download_name",
            f"demand_breakdown_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.csv",
        )
        download_name = st.text_input("Download filename", value=default_name, help="Enter a filename (will be sanitized and saved with .csv)")

        # Sanitize and ensure .csv extension
        raw = (download_name or "").strip()
        if raw.lower().endswith(".csv"):
            base = raw[:-4]
        else:
            base = raw
        safe_download_name = f"{slugify(base)}.csv" if base else f"demand_breakdown_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.csv"
        try:
            st.session_state["_download_name"] = safe_download_name
        except Exception:
            pass

        st.download_button("Download breakdown CSV", data=csv_content, file_name=safe_download_name, mime="text/csv")

        # Save to server button (with optional title included in filename)
        if st.button("Save breakdown to server (outputs/)"):
            try:
                title = st.session_state.get("scenario_title")
                # Prefer the explicitly chosen download name when saving to server
                filename = st.session_state.get("_download_name")
                if not filename:
                    if title:
                        filename = f"{slugify(title)}_{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.csv"
                    else:
                        filename = None
                saved_path = save_csv_to_disk(csv_content, filename=filename)
                st.success(f"Saved CSV to {saved_path}")
            except Exception as e:
                st.error(f"Error saving CSV: {e}")

        # Calculate/Hide totals controls moved here so they appear with the
        # CSV/download controls at the bottom of the page. Use explicit keys
        # to avoid duplicate widget id issues when multiple trials are present.
        btn_col1, btn_col2 = st.columns([1, 1])
        with btn_col1:
            if st.button("Calculate totals", key="calculate_totals_btn"):
                st.session_state["_show_totals"] = True
        with btn_col2:
            if st.button("Hide totals", key="hide_totals_btn"):
                st.session_state["_show_totals"] = False

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

if __name__ == "__main__":
    main()
