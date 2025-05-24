
import streamlit as st
import pandas as pd

# --- App Configuration ---
st.set_page_config(page_title="Comprehensive IV Fluid & Electrolyte Calculator", layout="wide")

# --- Helper Functions ---
def estimate_tbw(weight, gender, obese, malnourished):
    """
    Estimate Total Body Water (TBW) based on gender and adjustments.
    - Male: 60% of body weight; Female: 50%
    - Obese: subtract 15% of TBW; Malnourished: add 10% of TBW
    """
    base_fraction = 0.6 if gender == "Male" else 0.5
    tbw = base_fraction * weight
    if obese:
        tbw *= 0.85
    if malnourished:
        tbw *= 1.10
    return tbw  # in liters

def calculate_maintenance(weight):
    """
    4-2-1 rule for hourly rate and daily volume.
    """
    m1 = min(weight, 10) * 4
    m2 = min(max(weight - 10, 0), 10) * 2
    m3 = max(weight - 20, 0) * 1
    rate_h = m1 + m2 + m3  # mL/h
    return rate_h, rate_h * 24  # mL/h and mL per 24h

def calculate_deficit(rate_h, npo_hours):
    """
    Fluid deficit from NPO time: maintenance rate * NPO hours.
    """
    return rate_h * npo_hours

def calculate_electrolyte_deficits(tbw, na, k, hco3):
    """
    Estimate deficits:
    - Sodium deficit (mEq): TBW * (140 - Na)
    - Potassium deficit (mEq): 0.4 * weight * (4 - K)
    - Base deficit (mEq): 0.3 * weight * (24 - HCO3)
    """
    na_def = max(0, tbw * (140 - na))
    k_def = max(0, 0.4 * weight * (4.0 - k))
    hco3_def = max(0, 0.3 * weight * (24 - hco3))
    return na_def, k_def, hco3_def

# Fluid compositions per liter
fluid_composition = {
    "Lactated Ringer's": {"Na":130, "K":4, "Cl":109, "HCO3_pre":28},
    "0.9% NaCl": {"Na":154, "Cl":154},
    "D5NS": {"Na":154, "Cl":154, "Glucose_g":50},
    "D5LR": {"Na":130, "K":4, "Cl":109, "HCO3_pre":28, "Glucose_g":50}
}

# --- Sidebar Inputs ---
st.sidebar.header("Patient Demographics & Labs")
age = st.sidebar.number_input("Age (years)", min_value=0, value=25)
gender = st.sidebar.selectbox("Gender", ["Male", "Female"])
weight = st.sidebar.number_input("Weight (kg)", min_value=0.0, value=110.0)
obese = st.sidebar.checkbox("Obese (adjust TBW ↓15%)")
malnourished = st.sidebar.checkbox("Malnourished (adjust TBW ↑10%)")
npo_hours = st.sidebar.number_input("NPO duration (hours)", min_value=0, value=12)
serum_na = st.sidebar.number_input("Serum Na⁺ (mEq/L)", value=130.0)
serum_k = st.sidebar.number_input("Serum K⁺ (mEq/L)", value=5.0)
serum_hco3 = st.sidebar.number_input("Serum HCO₃⁻ (mEq/L)", value=22.0)
blood_glucose = st.sidebar.number_input("Blood glucose (mg/dL)", value=100.0)
chf = st.sidebar.checkbox("CHF / Pulmonary Edema (restrict fluids)")
pediatric = st.sidebar.checkbox("Pediatric patient (<18 years)")
insulin_infusion = st.sidebar.checkbox("On insulin infusion (add dextrose)")
long_npo = st.sidebar.checkbox("Prolonged NPO (>24h)")

# --- Calculations ---
if st.sidebar.button("Generate Plan"):
    # TBW estimation
    tbw = estimate_tbw(weight, gender, obese, malnourished)

    # Maintenance and deficit
    rate_h, maint_24 = calculate_maintenance(weight)
    if chf:
        rate_h *= 0.5  # restrict by half for CHF
        maint_24 = rate_h * 24
    deficit = calculate_deficit(rate_h, npo_hours)
    total_24 = maint_24 + deficit

    # Electrolyte deficits
    na_def, k_def, hco3_def = calculate_electrolyte_deficits(tbw, serum_na, serum_k, serum_hco3)

    # Determine fluid type
    if pediatric:
        fluid = "D5LR" if long_npo else "D5NS"
    else:
        if serum_na < 130 or deficit > 0:
            fluid = "0.9% NaCl"
        else:
            fluid = "Lactated Ringer's"
        if (long_npo or insulin_infusion or malnourished) and "D5" not in fluid:
            fluid = "D5LR" if "LR" in fluid else "D5NS"

    # Potassium supplementation
    k_supplement = "Add KCl 20 mEq per L" if serum_k < 3.5 else "No extra KCl"

    # Display Results
    st.title("24-Hour Fluid & Electrolyte Plan")
    st.markdown("### Volumes")
    st.markdown(f"- **TBW**: {tbw:.1f} L")
    st.markdown(f"- **Maintenance**: {maint_24:.0f} mL/24h ({rate_h:.0f} mL/h)")
    st.markdown(f"- **Deficit** (NPO {npo_hours}h): {deficit:.0f} mL")
    st.markdown(f"- **Total** for 24h: {total_24:.0f} mL")

    st.markdown("### Electrolyte Deficits (24h)")
    deficits_df = pd.DataFrame({
        "Electrolyte": ["Sodium", "Potassium", "Base (HCO₃⁻)"],
        "Deficit (mEq)": [f"{na_def:.0f}", f"{k_def:.0f}", f"{hco3_def:.0f}"]
    })
    st.table(deficits_df)

    # Maintenance electrolyte intake from chosen fluid
    comp = fluid_composition[fluid]
    intake = {}
    for key, val in comp.items():
        if key in ["Na", "K", "Cl", "HCO3_pre", "Glucose_g"]:
            intake[key] = val * (maint_24 / 1000)
    maint_df = pd.DataFrame({
        "Component": list(intake.keys()),
        "Intake (24h)": [f"{v:.1f}" for v in intake.values()]
    })
    st.markdown("### Electrolyte Intake from Maintenance Fluid (24h)")
    st.table(maint_df)

    st.markdown("### Recommended IV Fluid Order")
    order = f"{fluid} infusion at {rate_h:.0f} mL/hr for 24h via pump"
    if "D5" in fluid:
        order += " (contains dextrose)"
    if "KCl" in k_supplement:
        order += "; add 20 mEq KCl per L"
    st.code(order)

    st.markdown("### When to Add Glucose")
    st.markdown("""
- **Children**: always dextrose-containing fluids (e.g. D5LR).  
- **Prolonged NPO (>24h)**: add 50–100 g glucose/day (e.g. D5 solutions).  
- **Insulin Infusion**: co-infuse dextrose to maintain euglycemia.  
- **Malnourished/Refeeding**: include dextrose and thiamine to prevent ketosis.
""")

    st.markdown("**Rationale:** Based on Neal, *Schwartz’s Surgery*, Chapter 3: isotonic fluids for volume deficits; balanced crystalloids over NS to avoid hyperchloremia; dextrose for prolonged fasting/pediatrics/insulin; adjusted for CHF by fluid restriction.")
