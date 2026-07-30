import streamlit as st
import pandas as pd
import math
import sys
import os

# -------------------------------------------------------------
# 1. PAGE CONFIGURATION & FORCE LIGHT THEME OVERRIDES
# -------------------------------------------------------------
st.set_page_config(
    page_title="Everseen India Operations Calculator",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling to establish Everseen Indigo branding,
# force Light Mode defaults globally, style input elements,
# and construct elegant metrics cards that will NEVER truncate ("...").
st.markdown("""
<style>
    /* 1. Force Clean Light Theme Background & Fonts Globally */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #FAFAFC !important;
        color: #1E0B3E !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
    }

    /* 2. Everseen Title Logo Styling */
    .everseen-logo {
        font-size: 3.2rem;
        font-weight: 800;
        color: #241571;
        letter-spacing: -1.5px;
        margin-bottom: -5px;
        font-family: 'Inter', -apple-system, sans-serif !important;
    }
    .everseen-sub {
        font-size: 1.1rem;
        color: #7A70A6;
        margin-bottom: 25px;
        font-family: 'Inter', -apple-system, sans-serif !important;
    }

    /* 3. Section Headings (Everseen Indigo #241571) */
    .section-header {
        color: #241571 !important;
        font-weight: 700 !important;
        font-size: 1.4rem !important;
        margin-top: 10px;
        margin-bottom: 15px;
        border-bottom: 2px solid #EAEAF0;
        padding-bottom: 6px;
        font-family: 'Inter', -apple-system, sans-serif !important;
    }

    /* 4. Streamlit Default Input Styling Overrides to match Everseen Theme */
    div[data-baseweb="select"] {
        border-color: #E2E8F0 !important;
    }
    div[data-baseweb="select"] * {
        color: #241571 !important; /* Force interactive dropdown texts and chevrons */
        font-weight: 600 !important;
    }
    div[data-testid="stExpander"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E6E6ED !important;
        border-radius: 8px !important;
        box-shadow: 0 2px 4px rgba(36, 21, 113, 0.04) !important;
    }
    div[data-testid="stExpander"] [role="button"] {
        background-color: #F8FAFC !important; /* Header light background shade */
        color: #241571 !important;
        font-weight: 700 !important;
    }

    /* 5. Custom Metric Cards (Responsive, Anti-Ellipsis Wrap) */
    .everseen-metric-row {
        display: flex;
        flex-wrap: wrap;
        gap: 16px;
        margin-top: 15px;
        margin-bottom: 20px;
    }
    .everseen-card {
        flex: 1;
        min-width: 220px;
        background: #FFFFFF;
        border-left: 5px solid #241571;
        border-radius: 8px;
        padding: 18px 20px;
        box-shadow: 0 4px 12px rgba(36, 21, 113, 0.05);
        border-top: 1px solid #EAEAF0;
        border-right: 1px solid #EAEAF0;
        border-bottom: 1px solid #EAEAF0;
    }
    .everseen-cost-gradient-card {
        flex: 1;
        min-width: 220px;
        background: linear-gradient(135deg, #241571 0%, #4E54E5 50%, #D946EF 100%);
        border-radius: 8px;
        padding: 18px 20px;
        box-shadow: 0 6px 16px rgba(36, 21, 113, 0.15);
        color: #FFFFFF !important;
    }
    .card-label {
        font-size: 0.85rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .everseen-card .card-label {
        color: #6B7280;
    }
    .everseen-cost-gradient-card .card-label {
        color: rgba(255, 255, 255, 0.85);
    }
    .card-val {
        font-size: 1.85rem;
        font-weight: 800;
        line-height: 1.15;
        white-space: normal !important; /* Allows natural wrapping */
        word-break: break-word !important; /* Forces break on word boundaries */
    }
    .everseen-card .card-val {
        color: #1E0B3E;
    }
    .everseen-cost-gradient-card .card-val {
        color: #FFFFFF;
    }
    .card-desc {
        font-size: 0.8rem;
        margin-top: 6px;
    }
    .everseen-card .card-desc {
        color: #9CA3AF;
    }
    .everseen-cost-gradient-card .card-desc {
        color: rgba(255, 255, 255, 0.75);
    }

    /* 6. Custom Info banner style */
    .everseen-info-box {
        background-color: #F5F3FF;
        border: 1px solid #DDD6FE;
        border-radius: 8px;
        padding: 15px;
        margin-top: 15px;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------------------
# 2. DATA DICTIONARIES (SIMPLIFIED BACKEND BASELINE)
# -------------------------------------------------------------
# Maps Team to Processes
TEAM_MAPPING = {
    "Data & Reporting": ["Recall", "SPM"],
    "Annotations": [
        "Image-Fresh Annotations", 
        "Image-ReAnnotation", 
        "Video- Evercheck", 
        "Video- NextGen"
    ],
    "Tech Support (L1)": ["L1 Support Engineers"]
}

# Default items per hour (Baseline values)
DEFAULT_HOURLY_RATES = {
    "Recall": 35,
    "SPM": 21,
    "Image-Fresh Annotations": 11,
    "Image-ReAnnotation": 43,
    "Video- Evercheck": 4,
    "Video- NextGen": 5,
    "L1 Support Engineers": 4
}

# Cost per single item (in Euros)
COST_MAPPING = {
    "Recall": 0.06,
    "SPM": 0.10,
    "Image-Fresh Annotations": 0.19,
    "Image-ReAnnotation": 0.05,
    "Video- Evercheck": 0.51,
    "Video- NextGen": 0.43,
    "L1 Support Engineers": 0.20
}

# Standard productive operating hours multiplier to calculate Items/Day
# Regular tasks have 7 hours of productive work; L1 Tech Support has 21 hours
MULTIPLIER_MAPPING = {
    "Recall": 7,
    "SPM": 7,
    "Image-Fresh Annotations": 7,
    "Image-ReAnnotation": 7,
    "Video- Evercheck": 7,
    "Video- NextGen": 7,
    "L1 Support Engineers": 21
}

# Assumed Unit input labels based on selected Process (Process-Specific)
UNIT_MAPPING = {
    "Recall": "Non-Alerted Transactions",
    "SPM": "Alerted Transactions",
    "Image-Fresh Annotations": "Images",
    "Image-ReAnnotation": "Images",
    "Video- Evercheck": "Videos",
    "Video- NextGen": "Videos",
    "L1 Support Engineers": "L1 Tickets"
}

# -------------------------------------------------------------
# 3. HEADER & LOGO
# -------------------------------------------------------------
st.markdown('<div class="everseen-logo">everseen</div>', unsafe_allow_html=True)
st.markdown('<div class="everseen-sub">India Operations Cost & Effort Capacity Planner</div>', unsafe_allow_html=True)

# -------------------------------------------------------------
# 4. EDITABLE OPERATIONAL DISCLAIMER
# -------------------------------------------------------------
with st.expander("📝 Operational Baseline Disclaimer (Editable)", expanded=True):
    st.markdown(
        "Modify the baseline **Items/Hour** metrics below directly in the table to dynamically refactor calculators across the workspace."
    )

    # Initialize editable dataframe in session state
    if "editable_db" not in st.session_state:
        default_df = pd.DataFrame([
            {"Process": proc, "Items/Hour": rate}
            for proc, rate in DEFAULT_HOURLY_RATES.items()
        ])
        st.session_state.editable_db = default_df

    # Render editable table
    edited_df = st.data_editor(
        st.session_state.editable_db,
        key="baseline_editor",
        hide_index=True,
    )
    st.session_state.editable_db = edited_df

    st.markdown(
        "*Note: items per hour are calculated for 7hr efforts after removing data allocation and breaks (21hrs for L1 Support)*",
        help="Adjusting these rates automatically updates the dependent target workloads (Items/Day) used to estimate effort timelines."
    )

# -------------------------------------------------------------
# 5. DYNAMIC MAP INTERPRETATION FROM USER EDITS
# -------------------------------------------------------------
current_rates = {}
for idx, row in edited_df.iterrows():
    current_rates[row["Process"]] = int(row["Items/Hour"]) if pd.notna(row["Items/Hour"]) else 1

# -------------------------------------------------------------
# 6. STEP-BY-STEP CONFIGURATION & LAYOUT
# -------------------------------------------------------------
st.markdown('<div class="section-header">📋 Step-by-Step Configuration</div>', unsafe_allow_html=True)

col_input, col_results = st.columns(2, gap="large")

with col_input:
    # Step 1: Team Dropdown
    selected_team = st.selectbox(
        "1. Select Team / Department",
        options=list(TEAM_MAPPING.keys()),
        index=0
    )

    # Step 2: Dynamic Process Dropdown
    available_processes = TEAM_MAPPING[selected_team]
    selected_process = st.selectbox(
        "2. Select Process",
        options=available_processes,
        index=0
    )

    # Step 3: Total Available FTEs
    available_fte = st.number_input(
        "3. Total Available FTEs",
        min_value=1,
        value=5,
        step=1,
        help="Input the active headcount size allocated to this process backlog."
    )

    # Step 4: Volume Input (Context-aware labels from selected process)
    assumed_unit = UNIT_MAPPING[selected_process]
    item_volume = st.number_input(
        f"4. Total Volume to Process (Assumed Unit: {assumed_unit})",
        min_value=1,
        value=5000,
        step=100,
        help="Total task volume requiring active processing."
    )

    # Optional Side Settings (Conversion Currency Rates)
    st.markdown("---")
    eur_to_inr_rate = st.number_input(
        "EUR (€) to INR (₹) Exchange Rate",
        min_value=1.0,
        value=90.0,
        step=0.5,
        help="Set the active operational currency exchange rate."
    )

# -------------------------------------------------------------
# 7. METRICS & ENGINE CALCULATIONS (DECIMAL-FREE TIMELINES)
# -------------------------------------------------------------
# Retrieve dynamically edited operational parameters
hourly_rate = current_rates[selected_process]
productive_hours = MULTIPLIER_MAPPING[selected_process]
items_per_day = hourly_rate * productive_hours  # Target Items/Day
unit_cost_eur = COST_MAPPING[selected_process]

# Projections Engine
total_cost_eur = item_volume * unit_cost_eur
total_cost_inr = total_cost_eur * eur_to_inr_rate

effort_hours = int(round(item_volume / hourly_rate)) if hourly_rate > 0 else 0
fte_days_required = int(round(item_volume / items_per_day)) if items_per_day > 0 else 0

# Timeline Projections - CEIL ROUNDING FOR ETA WORKING DAYS
# Utilizes math.ceil to force-round up partial days to the next full working day
eta_days = int(math.ceil(fte_days_required / available_fte)) if available_fte > 0 else 0

# -------------------------------------------------------------
# 8. PRESENT RESULTS (PREMIUM VISUAL METRICS)
# -------------------------------------------------------------
with col_results:
    st.markdown('<div class="section-header">📊 Operational & Schedule Projections</div>', unsafe_allow_html=True)

    # HTML Row 1: Timeline Projections
    st.markdown(f"""
    <div class="everseen-metric-row">
        <div class="everseen-card">
            <div class="card-label">
                <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                Estimated Delivery ETA
            </div>
            <div class="card-val">{eta_days:,} Working Days</div>
            <div class="card-desc">Based on {available_fte:,} assigned FTEs (rounded up to next full day)</div>
        </div>
        <div class="everseen-card">
            <div class="card-label">
                <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"></path></svg>
                Total Required Effort
            </div>
            <div class="card-val">{fte_days_required:,} FTE-Days</div>
            <div class="card-desc">Equivalent to {effort_hours:,} total productive hours</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # HTML Row 2: Budget Projections
    st.markdown(f"""
    <div class="everseen-metric-row">
        <div class="everseen-cost-gradient-card">
            <div class="card-label">
                <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                Total Estimated Cost
            </div>
            <div class="card-val">€ {total_cost_eur:,.2f}</div>
            <div class="card-desc">₹ {total_cost_inr:,.2f} (approx. equivalent)</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Details Breakdown Table
    st.markdown("### Detailed Process Metrics")
    breakdown_data = {
        "Configuration Metric": [
            "Department Name", 
            "Target Process Flow", 
            "Target Item Volume", 
            "Calculated Items/Day Target", 
            "Unit Operational Cost"
        ],
        "Active Values": [
            str(selected_team),
            str(selected_process),
            f"{item_volume:,} {assumed_unit}",
            f"{items_per_day:,} items",
            f"€ {unit_cost_eur:.2f} per unit"
        ]
    }
    breakdown_df = pd.DataFrame(breakdown_data)
    st.dataframe(breakdown_df, hide_index=True)

    # Instant CSV Exporter
    csv_export_df = pd.DataFrame([{
        "Team": selected_team,
        "Process": selected_process,
        "Assigned_FTE": available_fte,
        "Target_Volume": item_volume,
        "Items_Per_Hour_Edited": hourly_rate,
        "Calculated_Items_Per_Day": items_per_day,
        "Productive_Hours_Required": effort_hours,
        "Total_FTE_Days_Required": fte_days_required,
        "Calculated_ETA_Working_Days": eta_days,
        "Total_Cost_EUR": round(total_cost_eur, 2),
        "Total_Cost_INR": round(total_cost_inr, 2)
    }])

    csv_bytes = csv_export_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Export Calculation Summary (CSV)",
        data=csv_bytes,
        file_name=f"everseen_ops_estimate_{selected_process.lower().replace(' ', '_')}.csv",
        mime="text/csv",
    )

# -------------------------------------------------------------
# 9. PYCHARM LOCAL PLAYBACK ENTRYPOINT (SAFE SHIELD CHECK)
# -------------------------------------------------------------
if __name__ == '__main__':
    # Safeguards against double-boot runtime exceptions in Streamlit
    if not st.runtime.exists():
        try:
            from streamlit.web import cli as stcli
            sys.argv = ["streamlit", "run", __file__]
            sys.exit(stcli.main())
        except ImportError:
            pass
