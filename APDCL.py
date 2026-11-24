import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re
from datetime import datetime, timedelta, date
import calendar
import io
import os
import glob
import hmac
import numpy as np
import json
import base64
import requests
import streamlit.components.v1 as components

# ==============================================================================
# 1. PAGE CONFIGURATION (MUST BE THE VERY FIRST COMMAND)
# ==============================================================================
st.set_page_config(
    page_title="APDCL Dashboard",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# 1b. ACCESS CONTROL (PUBLIC VIEWER BY DEFAULT, OPTIONAL SINGLE ADMIN LOGIN)
# ==============================================================================
ADMIN_KEY = "apdcl_is_admin"

def _get_config(section, key, env_name=None):
    """Read a value from st.secrets first, then from an environment variable."""
    try:
        value = st.secrets[section][key]
        if value:
            return value
    except Exception:
        pass
    return os.environ.get(env_name) if env_name else None

def get_admin_password():
    return _get_config("admin", "password", "APDCL_ADMIN_PASSWORD")

SUPABASE_URL = _get_config("supabase", "url", "SUPABASE_URL")
SUPABASE_KEY = _get_config("supabase", "key", "SUPABASE_KEY")
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

if ADMIN_KEY not in st.session_state:
    st.session_state[ADMIN_KEY] = False

# ==============================================================================
# 2. INITIALIZATION & SESSION STATE (RUNS IMMEDIATELY)
# ==============================================================================
if 'init_done' not in st.session_state:
    now = datetime.now()
    m3_date = now 
    m2_date = (m3_date.replace(day=1) - timedelta(days=1))
    m1_date = (m2_date.replace(day=1) - timedelta(days=1))
    
    # Define ALL default keys here to prevent KeyErrors later
    defaults = {
        'default_n1': m1_date.strftime("%B %Y").upper(),
        'default_n2': m2_date.strftime("%B %Y").upper(),
        'default_n3': m3_date.strftime("%B %Y").upper(),
        'n1': m1_date.strftime("%B %Y").upper(),
        'n2': m2_date.strftime("%B %Y").upper(),
        'n3': m3_date.strftime("%B %Y").upper(),
        'c_n1': 0, 'j_n1': 0,
        'c_n2': 0, 'j_n2': 0,
        'c_n3': 0, 'j_n3': 0,
        'd_c': 0, 'd_j': 0,
        # Ensure quarterly_labels ALWAYS has 3 items to prevent ValueError
        'quarterly_labels': [m1_date.strftime("%B %Y").upper(), m2_date.strftime("%B %Y").upper(), m3_date.strftime("%B %Y").upper()],
        'daily_tdc_data': [{"Sub-division": "CHILAPATHAR", "Value":0}, {"Sub-division": "JONAI", "Value":0}],
        'report_date_key': now.date(), 
        'report_date_val': now.date(), # Persistent Date
        'report_time_val': now.time()  # Persistent Time
    }
    
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val
            
    st.session_state['init_done'] = True

# ==============================================================================
# 3. CSS STYLING (DARKER, BOLD, & PRINT OPTIMIZED)
# ==============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;700;900&display=swap');
    
    .stApp { background-color: #f8fafc; font-family: 'Roboto', sans-serif; color: #0f172a; }
    h1, h2, h3 { color: #0f172a !important; font-weight: 900 !important; }
    
    .main-heading { font-size: 3.5rem; font-weight: 900; color: #1e3a8a; margin: 0; line-height: 1; }
    .sub-heading { font-size: 1.6rem; font-weight: 800; color: #d97706; margin: 5px 0 0 0; text-transform: uppercase; }
    .meta-text { font-size: 1.1rem; color: #475569; margin-top: 5px; font-weight: 700; }
    
    .metric-card { background-color: white; padding: 25px; border-radius: 12px; border: 1px solid #cbd5e1; box-shadow: 0 4px 10px rgba(0,0,0,0.08); margin-bottom: 25px; color: #0f172a; }
    .section-title { color: #1e3a8a; font-size: 1.8rem; font-weight: 900; margin-top: 20px; margin-bottom: 15px; border-left: 8px solid #F58220; padding-left: 20px; background: white; padding-top: 15px; padding-bottom: 15px; width: 100%; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    .subdiv-banner { background: linear-gradient(135deg, #1e3a8a 0%, #172554 100%); color: white; padding: 15px 25px; font-size: 1.3rem; font-weight: 900; border-radius: 10px 10px 0 0; margin-top: 30px; display: flex; justify-content: space-between; align-items: center; }
    .verdict-box { background-color: #f1f5f9; border: 2px solid #94a3b8; border-radius: 10px; padding: 15px; text-align: center; color: #0f172a; font-weight: 700; }
    .ai-box { background-color: #f0fdf4; border: 2px solid #16a34a; border-radius: 10px; padding: 15px; color: #14532d; font-size: 1rem; font-weight: 600; margin-top: 15px; }
    .ai-box.warning { background-color: #fff7ed; border: 2px solid #ea580c; color: #7c2d12; }
    
    .tdc-table { width: 100%; border-collapse: collapse; margin-bottom: 10px; }
    .tdc-table th { background-color: #1e3a8a; color: white; font-weight: 900; padding: 8px; text-align: center; }
    .tdc-table td { border: 1px solid #e2e8f0; padding: 8px 12px; text-align: center; font-weight: 700; color: #0f172a; background-color: white; }
    
    /* --- PRINT CSS: FIXED HEADER & LAYOUT --- */
    @media print {
        /* Hide UI Elements */
        [data-testid="stSidebar"], [data-testid="stToolbar"], .stButton, button, footer, header { display: none !important; }
        
        /* Reset Layout for PDF/Paper */
        .stApp, .main, .block-container { 
            background-color: white !important; 
            padding: 0 !important; 
            margin: 0 !important; 
            width: 100% !important; 
            max-width: 100% !important; 
            overflow: visible !important; /* Force all content to show */
        }
        
        /* Ensure our custom header is visible */
        #custom-print-header { display: block !important; }
        
        /* Ensure charts don't break awkwardly */
        .metric-card, .plot-container {
            break-inside: avoid;
            page-break-inside: avoid;
            box-shadow: none !important;
            border: 1px solid #ddd !important;
        }
        
        /* Font Color Fix for Print */
        * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 4. HELPER FUNCTIONS (DEFINED *BEFORE* USE TO FIX NameError)
# ==============================================================================

# --- IMAGE & FILE UTILS ---
def get_img_as_base64(file):
    try:
        with open(file, "rb") as f: data = f.read()
        return base64.b64encode(data).decode()
    except: return None

def clean_currency(value):
    if pd.isna(value): return 0.0
    str_val = str(value).replace(',', '').strip()
    try: return float(str_val)
    except ValueError: return 0.0

def format_indian_currency(value):
    if pd.isna(value) or value == 0: return "₹ 0"
    abs_value = abs(value)
    if abs_value >= 10000000: return f"₹ {value/10000000:.2f} Cr"
    elif abs_value >= 100000: return f"₹ {value/100000:.2f} L"
    else: return f"₹ {value:,.0f}"

def format_simple_number(value):
    if pd.isna(value): return "0"
    return f"{value:,.0f}"

def get_date_from_filename(filename, selected_month_date):
    match = re.search(r'(\d+)', filename)
    if match:
        day = int(match.group(1))
        # Prevent year match (e.g. 2026) being treated as day
        if day > 31: return None
        try: return datetime(selected_month_date.year, selected_month_date.month, day)
        except ValueError: return None
    return None

def parse_month_date_from_name(filename):
    try:
        clean_name = os.path.basename(filename).upper()
        month_idx = 0
        for i, m in enumerate(list(calendar.month_name)[1:], 1):
            if m.upper() in clean_name: month_idx = i; break
        if month_idx == 0:
            for i, m in enumerate(list(calendar.month_abbr)[1:], 1):
                if m.upper() in clean_name: month_idx = i; break
        year_match = re.search(r'20\d{2}', clean_name)
        year = int(year_match.group(0)) if year_match else datetime.now().year
        if month_idx > 0: return datetime(year, month_idx, 1)
    except: return None
    return None

@st.cache_data
def safe_read_file(file_input):
    if file_input is None: return None
    try:
        if isinstance(file_input, str):
            if file_input.lower().endswith('.csv'): return pd.read_csv(file_input, header=None, names=list(range(40)))
            else: return pd.read_excel(file_input, header=None)
        else:
            if file_input.name.lower().endswith('.csv'): return pd.read_csv(file_input, header=None, names=list(range(40)))
            else: return pd.read_excel(file_input, header=None)
    except: return None

# --- IMPROVED DATA EXTRACTOR (Scans more columns) ---
def extract_metrics_single(df, source_name, selected_month_date, is_debug=False):
    if df is None: return []
    targets = [("CHILAPATHAR", "CHILAPATHAR", "CHILAPATHAR"), ("JONAI", "JONAI", "JONAI")]
    data = []
    file_date = get_date_from_filename(source_name, selected_month_date) if selected_month_date else None
    
    for target_text, sub_div, code in targets:
        # SCAN COLUMNS 0 to 5 to find the Subdivision Name
        mask = pd.Series([False] * len(df))
        for col_idx in range(6): # Check first 6 columns
            if col_idx in df.columns:
                mask |= df[col_idx].astype(str).str.strip().str.contains(target_text, case=False, na=False)
        
        found_rows = df[mask]
        if not found_rows.empty:
            row = found_rows.iloc[0]
            data.append({
                "Source": source_name, "Date": file_date, "Sub-Div": sub_div, "Code": code,
                "Billing": clean_currency(row[4] if 4 < len(row) else 0),
                "Demand": clean_currency(row[8] if 8 < len(row) else 0),
                "Collection": clean_currency(row[11] if 11 < len(row) else 0)
            })
    return data

def load_local_files(folder_path):
    files = []
    if os.path.exists(folder_path):
        files.extend(glob.glob(os.path.join(folder_path, "*.xls")))
        files.extend(glob.glob(os.path.join(folder_path, "*.xlsx")))
        files.extend(glob.glob(os.path.join(folder_path, "*.csv")))
    return files

def load_daily_history_data(base_folder):
    history_data = []
    if not os.path.exists(base_folder): return []
    for month_folder in os.listdir(base_folder):
        full_month_path = os.path.join(base_folder, month_folder)
        if os.path.isdir(full_month_path):
            day_files = glob.glob(os.path.join(full_month_path, "*.*"))
            for f_path in day_files:
                f_name = os.path.basename(f_path)
                day_match = re.search(r'(\d+)', f_name)
                if day_match:
                    day_num = int(day_match.group(1))
                    if day_num > 31: continue
                    df = safe_read_file(f_path)
                    metrics = extract_metrics_single(df, f_name, datetime(2000,1,1)) # Dummy date for generic loading
                    for m in metrics:
                        history_data.append({ "Month": month_folder, "Day": day_num, "Sub-Div": m['Sub-Div'], "Collection": m['Collection'], "Demand": m['Demand'] })
    return history_data

# --- PERSISTENCE (Supabase when configured, local JSON fallback) ---
HISTORY_FILE = os.path.join("data", "tdc_history.json")

def load_history_data_json():
    if USE_SUPABASE:
        try:
            url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/apdcl_settings?select=date_key,data"
            resp = requests.get(
                url,
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                },
                timeout=15,
            )
            resp.raise_for_status()
            return {row["date_key"]: row.get("data") or {} for row in resp.json()}
        except Exception as exc:
            st.sidebar.warning(f"⚠️ Supabase load failed: {exc}. Using local data.")

    if not os.path.exists("data"):
        os.makedirs("data")
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}

def save_history_data_json(date_str, data_dict):
    history = load_history_data_json()
    if date_str not in history:
        history[date_str] = {}
    history[date_str].update(data_dict)

    if USE_SUPABASE:
        try:
            url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/apdcl_settings"
            resp = requests.post(
                url,
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "resolution=merge-duplicates,return=minimal",
                },
                json={"date_key": date_str, "data": history[date_str]},
                timeout=15,
            )
            resp.raise_for_status()
            return
        except Exception as exc:
            st.sidebar.error(f"❌ Supabase save failed: {exc}. Saving locally instead.")

    if not os.path.exists("data"):
        os.makedirs("data")
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4)

def persist_change():
    data_to_save = {
        "n1": st.session_state.input_n1, "n2": st.session_state.input_n2, "n3": st.session_state.input_n3,
        "c_n1": st.session_state.num_c_n1, "j_n1": st.session_state.num_j_n1, "c_n2": st.session_state.num_c_n2, "j_n2": st.session_state.num_j_n2,
        "c_n3": st.session_state.num_c_n3, "j_n3": st.session_state.num_j_n3, "d_c": st.session_state.num_d_c, "d_j": st.session_state.num_d_j
    }
    st.session_state.n1 = st.session_state.input_n1; st.session_state.n2 = st.session_state.input_n2; st.session_state.n3 = st.session_state.input_n3
    save_history_data_json(str(st.session_state.get('report_date_key')), data_to_save)

# --- 5. SIDEBAR LOGIC (Load Data & Fixed Editable Time) ---
with st.sidebar:
    st.header("⚙️ Dashboard Controls")

    st.markdown("### 🔐 Access")
    expected_admin_pw = get_admin_password()
    if st.session_state[ADMIN_KEY]:
        st.success("✅ Admin mode — editing enabled")
        if st.button("🔒 Log out", key="admin_logout_btn"):
            st.session_state[ADMIN_KEY] = False
            st.rerun()
    else:
        st.caption("Public read-only view. Admins can log in to edit values.")
        with st.expander("Admin login"):
            pw = st.text_input("Admin password", type="password", key="admin_password_input")
            if st.button("Login", key="admin_login_btn"):
                if not expected_admin_pw:
                    st.error("Admin password is not configured. Set it in Streamlit Secrets.")
                elif hmac.compare_digest(pw or "", expected_admin_pw):
                    st.session_state[ADMIN_KEY] = True
                    st.rerun()
                else:
                    st.error("Incorrect password.")
    st.markdown("---")

    logo_file = None
    if os.path.exists("logo.png"): logo_file = "logo.png"
    elif os.path.exists("logo.jpg"): logo_file = "logo.jpg"
    if not logo_file:
        uploaded_logo = st.file_uploader("Upload Logo (PNG/JPG)", type=['png', 'jpg', 'jpeg'])
        if uploaded_logo: logo_file = uploaded_logo
    else: st.success(f"✅ Logo Loaded")
    
    st.markdown("---")
    st.markdown("### 2. Report Settings")
    
    # Store user-edited date/time in session state so it doesn't reset to "now" on every interaction
    report_date = st.date_input("📅 Report Date", value=st.session_state['report_date_val'])
    st.session_state['report_date_val'] = report_date
    st.session_state['report_date_key'] = report_date
    
    report_time = st.time_input("⏰ Report Time", value=st.session_state['report_time_val'])
    st.session_state['report_time_val'] = report_time
    
    display_timestamp = datetime.combine(report_date, report_time).strftime("%d-%b-%Y %I:%M %p")
    
    date_key = str(report_date)
    history = load_history_data_json()
    day_data = history.get(date_key, {})
    
    # Load into inputs
    st.session_state['input_n1'] = day_data.get("n1", st.session_state['default_n1'])
    st.session_state['input_n2'] = day_data.get("n2", st.session_state['default_n2'])
    st.session_state['input_n3'] = day_data.get("n3", st.session_state['default_n3'])
    st.session_state['num_c_n1'] = day_data.get("c_n1", 0); st.session_state['num_j_n1'] = day_data.get("j_n1", 0)
    st.session_state['num_c_n2'] = day_data.get("c_n2", 0); st.session_state['num_j_n2'] = day_data.get("j_n2", 0)
    st.session_state['num_c_n3'] = day_data.get("c_n3", 0); st.session_state['num_j_n3'] = day_data.get("j_n3", 0)
    st.session_state['num_d_c'] = day_data.get("d_c", 0); st.session_state['num_d_j'] = day_data.get("d_j", 0)
    
    # Sync Main Variables
    st.session_state['n1'] = st.session_state['input_n1']
    st.session_state['n2'] = st.session_state['input_n2']
    st.session_state['n3'] = st.session_state['input_n3']
    st.session_state['c_n1'] = st.session_state['num_c_n1']; st.session_state['j_n1'] = st.session_state['num_j_n1']
    st.session_state['c_n2'] = st.session_state['num_c_n2']; st.session_state['j_n2'] = st.session_state['num_j_n2']
    st.session_state['c_n3'] = st.session_state['num_c_n3']; st.session_state['j_n3'] = st.session_state['num_j_n3']
    st.session_state['d_c'] = st.session_state['num_d_c']; st.session_state['d_j'] = st.session_state['num_d_j']
    
    st.markdown("---")

# --- HEADER RENDERER (HTML EMBEDDED LOGO) ---
def render_header_html():
    logo_html = ""
    if logo_file:
        if hasattr(logo_file, "read"):
             logo_file.seek(0); b64 = base64.b64encode(logo_file.read()).decode()
             logo_html = f'<img src="data:image/png;base64,{b64}" width="140">'
        elif isinstance(logo_file, str) and os.path.exists(logo_file):
             b64 = get_img_as_base64(logo_file)
             if b64: logo_html = f'<img src="data:image/png;base64,{b64}" width="140">'
    else: logo_html = "<h1 style='font-size:60px;'>⚡</h1>"
    st.markdown(f"""
    <div id="custom-print-header" style="display: flex; align-items: center; margin-bottom: 20px;">
        <div style="flex: 1;">{logo_html}</div>
        <div style="flex: 6; padding-left: 20px;">
            <div style="font-size: 3.5rem; font-weight: 900; color: #1e3a8a; line-height: 1;">APDCL</div>
            <div style="font-size: 1.6rem; font-weight: 800; color: #d97706;">CHILAPATHAR ELECTRICAL DIVISION</div>
            <div style="font-size: 1.1rem; color: #475569; font-weight: 700; margin-top: 5px;">
                Revenue Monitoring & Collection Forecasting System | Report Generated: {display_timestamp}
            </div>
        </div>
    </div>
    <hr style="border-top: 6px solid #F58220; margin-bottom: 30px;">
    """, unsafe_allow_html=True)

# --- 6. GLOBAL DATA FETCH ---
target_folder = report_date.strftime("%b_%Y").upper()
target_path = os.path.join("data", "daily_history", target_folder)
all_daily_global = []
if os.path.exists(target_path):
    day_files = glob.glob(os.path.join(target_path, "*.*"))
    for f_path in day_files:
        df = safe_read_file(f_path)
        all_daily_global.extend(extract_metrics_single(df, os.path.basename(f_path), report_date))
if all_daily_global:
    df_daily_g = pd.DataFrame(all_daily_global).dropna(subset=['Date'])
    if not df_daily_g.empty:
        df_daily_g = df_daily_g[df_daily_g['Date'] <= pd.to_datetime(report_date)]
        st.session_state['daily_df'] = df_daily_g
else:
    if 'daily_df' in st.session_state: del st.session_state['daily_df']

history_files = load_local_files("data/history")
history_records = []
if history_files:
    for f in history_files:
        fname = os.path.basename(f)
        dt = parse_month_date_from_name(fname)
        if dt:
            df_hist = safe_read_file(f)
            metrics = extract_metrics_single(df_hist, fname, dt)
            for m in metrics:
                history_records.append({"Date": dt, "MonthStr": dt.strftime("%b %y"), "Sub-Div": m['Sub-Div'], "Demand": m['Demand'], "Collection": m['Collection']})
if history_records:
    st.session_state['history_df'] = pd.DataFrame(history_records).sort_values("Date", ascending=True)
else:
    if 'history_df' in st.session_state: del st.session_state['history_df']

st.session_state['prev_daily_df'] = pd.DataFrame(load_daily_history_data("data/daily_history"))

quarterly_raw = []
base_dir = os.path.join("data", "daily_history")
target_day = report_date.day
# Fail safe for labels
active_labels = [st.session_state['n1'], st.session_state['n2'], st.session_state['n3']]
st.session_state['quarterly_labels'] = active_labels

for m_label in active_labels:
    folder_name = m_label
    if not os.path.exists(os.path.join(base_dir, folder_name)):
        try: dt = datetime.strptime(m_label, "%B %Y"); folder_name = dt.strftime("%b_%Y").upper()
        except: pass
    month_path = os.path.join(base_dir, folder_name)
    found_file = None
    if os.path.exists(month_path):
        possible_files = glob.glob(os.path.join(month_path, f"{target_day}.*"))
        if possible_files: found_file = possible_files[0]
    if found_file:
        df = safe_read_file(found_file)
        metrics = extract_metrics_single(df, os.path.basename(found_file), report_date)
        for m in metrics:
            quarterly_raw.append({"Month": m_label, "Sub-Div": m['Sub-Div'], "Code": m['Code'], "Category": "BILLING", "Value": m['Billing']})
            quarterly_raw.append({"Month": m_label, "Sub-Div": m['Sub-Div'], "Code": m['Code'], "Category": "DEMAND", "Value": m['Demand']})
            quarterly_raw.append({"Month": m_label, "Sub-Div": m['Sub-Div'], "Code": m['Code'], "Category": "COLLECTION", "Value": m['Collection']})

if quarterly_raw:
    for label, c_val, j_val in [(st.session_state['n1'], st.session_state['c_n1'], st.session_state['j_n1']),(st.session_state['n2'], st.session_state['c_n2'], st.session_state['j_n2']),(st.session_state['n3'], st.session_state['c_n3'], st.session_state['j_n3'])]:
        quarterly_raw.append({"Month": label, "Sub-Div": "CHILAPATHAR", "Code": "CHILAPATHAR", "Category": "TDC", "Value": c_val})
        quarterly_raw.append({"Month": label, "Sub-Div": "JONAI", "Code": "JONAI", "Category": "TDC", "Value": j_val})
    st.session_state['quarterly_df'] = pd.DataFrame(quarterly_raw)
    st.session_state['daily_tdc_data'] = [{"Sub-division": "CHILAPATHAR", "Value": st.session_state['d_c']}, {"Sub-division": "JONAI", "Value": st.session_state['d_j']}]

# --- CALC & DISPLAY FUNCTIONS ---
def calculate_smart_projection(current_val, current_day, df_history_daily, subdivision, days_in_month, target_val, report_time):
    if target_val > 0 and current_val >= target_val: return current_val * 1.01
    
    days_remaining = max(0, days_in_month - current_day)

    # 1. Intra-day End of Month Logic
    if current_day >= days_in_month:
        current_hour = report_time.hour + (report_time.minute / 60.0); start_hour, end_hour = 9.0, 24.0
        if current_hour >= end_hour: return current_val
        hours_passed = 0.5 if current_hour < start_hour else current_hour - start_hour
        hours_remaining = max(0, end_hour - max(start_hour, current_hour))
        raw_velocity = current_val / max(1, hours_passed)
        achieved_pct = current_val / target_val if target_val > 0 else 0
        efficiency_factor = 1.0 if achieved_pct > 0.85 else 0.7
        final_projection = current_val + (raw_velocity * hours_remaining * efficiency_factor)
        return min(final_projection, target_val * 1.05) if target_val > 0 else final_projection

    # 2. Historical Multiplier
    df_hist_sub = pd.DataFrame(df_history_daily)
    if not df_hist_sub.empty: df_hist_sub = df_hist_sub[df_hist_sub['Sub-Div'] == subdivision]
    growth_multipliers = []
    if not df_hist_sub.empty:
        for m in df_hist_sub['Month'].unique():
            d_month = df_hist_sub[df_hist_sub['Month'] == m]
            try:
                max_d = d_month['Day'].max(); val_end = d_month[d_month['Day'] == max_d]['Collection'].max()
                val_now_hist = d_month[d_month['Day'] <= current_day]['Collection'].max()
                if val_now_hist > 0 and val_end >= val_now_hist: growth_multipliers.append(val_end / val_now_hist)
            except: continue
            
    hist_proj = 0
    if growth_multipliers:
        avg_growth = sum(growth_multipliers) / len(growth_multipliers)
        hist_proj = current_val * avg_growth

    # 3. Linear Velocity
    linear_velocity = current_val / current_day if current_day > 0 else 0
    linear_proj = current_val + (linear_velocity * days_remaining)

    # 4. Target Gap Closure (Assuming late-month collection spike)
    target_proj = 0
    if target_val > 0:
        gap = target_val - current_val
        expected_gap_closure = min(1.0, (current_day / days_in_month) * 1.2) 
        target_proj = current_val + (gap * expected_gap_closure)

    # 5. Smart Time-Weighted Blend
    if hist_proj > 0:
        if current_day <= 10:
            proj = (hist_proj * 0.7) + (linear_proj * 0.3)
        elif current_day <= 22:
            proj = (hist_proj * 0.5) + (linear_proj * 0.2) + (target_proj * 0.3)
        else:
            proj = (hist_proj * 0.3) + (target_proj * 0.7)
    else:
        if current_day <= 15:
            proj = linear_proj
        else:
            proj = (linear_proj * 0.5) + (target_proj * 0.5)
            
    if target_val > 0:
        proj = min(proj, target_val * 1.05)
        proj = max(proj, current_val)
        
    return proj

def display_quarterly_visuals(full_df, labels, daily_tdc_data, key_suffix, hide_title=False, download_in_sidebar=False):
    n1, n2, n3 = labels if len(labels) == 3 else ("M1", "M2", "M3")
    if not hide_title:
        st.markdown(f'<div class="section-title">📊 Daily Performance Review</div>', unsafe_allow_html=True)
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.markdown("#### Consolidated Revenue Statement (Daily Breakdown)")
    pivot = full_df.pivot_table(index="Code", columns=["Category", "Month"], values="Value", aggfunc='sum')
    pivot.index.name = "Sub-division"
    desired_order = []
    for cat in ["BILLING", "DEMAND", "COLLECTION", "TDC"]:
        for mon in [n1, n2, n3]:
            if (cat, mon) in pivot.columns or cat == "TDC": desired_order.append((cat, mon))
    pivot = pivot.reindex(columns=desired_order, fill_value=0)
    
    if download_in_sidebar:
        csv_buffer = io.StringIO(); pivot.to_csv(csv_buffer)
        st.sidebar.markdown("---"); st.sidebar.download_button("📥 Download Report CSV", csv_buffer.getvalue(), f"APDCL_Report.csv", "text/csv")
    
    format_dict = {}
    for col in pivot.columns:
        cat_name = col[0]
        if cat_name in ["BILLING", "TDC"]: format_dict[col] = format_simple_number
        else: format_dict[col] = format_indian_currency
    styler = pivot.style.format(format_dict).set_properties(subset=[c for c in pivot.columns if c[0] == "BILLING"], **{'background-color': '#ffebcc', 'color': '#0f172a', 'font-weight': 'bold'}).set_properties(subset=[c for c in pivot.columns if c[0] == "DEMAND"], **{'background-color': '#dcfce7', 'color': '#0f172a', 'font-weight': 'bold'}).set_properties(subset=[c for c in pivot.columns if c[0] == "COLLECTION"], **{'background-color': '#dbeafe', 'color': '#0f172a', 'font-weight': 'bold'}).set_properties(subset=[c for c in pivot.columns if c[0] == "TDC"], **{'background-color': '#f1f5f9', 'color': '#0f172a', 'font-weight': 'bold'})
    st.dataframe(styler, width='stretch')
    
    st.markdown("---")
    st.markdown("#### Trend Analysis (Daily Comparison)")
    c_ch1, c_ch2, c_ch3, c_ch4 = st.columns(4)
    def draw_chart(cat, container, color_sequence):
        if cat not in full_df['Category'].unique(): return
        data = full_df[full_df['Category'] == cat].copy()
        month_map = {n1:1, n2:2, n3:3}; data['sort'] = data['Month'].map(month_map); data = data.sort_values('sort')
        fig = px.bar(data, x="Sub-Div", y="Value", color="Month", barmode="group", title=cat, color_discrete_sequence=color_sequence, category_orders={"Sub-Div": ["CHILAPATHAR", "JONAI"]})
        fig.update_layout(template="plotly_white", height=300, margin=dict(t=40,b=0,l=0,r=0), xaxis_title="", yaxis_title="", legend=dict(orientation="h", y=-0.2), font=dict(family="Roboto", size=14, color="#0f172a"))
        container.plotly_chart(fig, width='stretch', key=f"{cat}_{key_suffix}")
    
    chesd_val = daily_tdc_data[0]['Value']; jesd_val = daily_tdc_data[1]['Value']
    with c_ch1: st.markdown('<div style="height: 90px;"></div>', unsafe_allow_html=True); draw_chart("BILLING", c_ch1, ["#f59e0b", "#b45309", "#78350f"])
    with c_ch2: st.markdown('<div style="height: 90px;"></div>', unsafe_allow_html=True); draw_chart("DEMAND", c_ch2, ["#4ade80", "#16a34a", "#14532d"])
    with c_ch3: st.markdown('<div style="height: 90px;"></div>', unsafe_allow_html=True); draw_chart("COLLECTION", c_ch3, ["#60a5fa", "#2563eb", "#1e3a8a"])
    with c_ch4:
        st.markdown(f'<table class="tdc-table"><thead><tr><th colspan="2">DAILY TDC</th></tr></thead><tbody><tr><td class="tdc-label">CHILAPATHAR</td><td>{clean_currency(chesd_val):.0f}</td></tr><tr><td class="tdc-label">JONAI</td><td>{clean_currency(jesd_val):.0f}</td></tr></tbody></table>', unsafe_allow_html=True)
        draw_chart("TDC", c_ch4, ["#94a3b8", "#64748b", "#334155"])
    st.markdown('</div>', unsafe_allow_html=True)

def create_history_chart(df_hist, subdivision, ref_date, df_daily_backup=None, current_df=None):
    t_yoy = ref_date - pd.DateOffset(years=1); t_m2 = ref_date - pd.DateOffset(months=2); t_m1 = ref_date - pd.DateOffset(months=1); t_curr = ref_date
    targets = [t_yoy, t_m2, t_m1, t_curr]; final_rows = []
    
    for i, t_date in enumerate(targets):
        found = False; row_data = None
        if not found and current_df is not None and not current_df.empty:
             curr_sub = current_df[current_df['Sub-Div'] == subdivision].copy()
             if not curr_sub.empty:
                 curr_sub['Date'] = pd.to_datetime(curr_sub['Date'])
                 match_curr = curr_sub[(curr_sub['Date'].dt.month == t_date.month) & (curr_sub['Date'].dt.year == t_date.year)]
                 if not match_curr.empty:
                     match_curr = match_curr.sort_values(by='Date')
                     latest_row = match_curr.iloc[-1]
                     row_data = {'MonthStr': t_date.strftime('%b %y'), 'Demand': latest_row['Demand'], 'Collection': latest_row['Collection'], 'SortDate': t_date, 'Order': i}; found = True
        if not found and df_hist is not None and not df_hist.empty:
            df_hist['Date'] = pd.to_datetime(df_hist['Date'])
            match = df_hist[(df_hist['Sub-Div'] == subdivision) & (df_hist['Date'].dt.month == t_date.month) & (df_hist['Date'].dt.year == t_date.year)]
            if not match.empty:
                r = match.iloc[0]; row_data = {'MonthStr': t_date.strftime('%b %y'), 'Demand': r['Demand'], 'Collection': r['Collection'], 'SortDate': t_date, 'Order': i}; found = True
        if not found and df_daily_backup is not None and not df_daily_backup.empty:
            daily_sub = df_daily_backup[df_daily_backup['Sub-Div'] == subdivision].copy()
            m_abbr = t_date.strftime('%b').upper(); y_str = str(t_date.year)
            d_match = daily_sub[daily_sub['Month'].str.upper().str.contains(m_abbr) & daily_sub['Month'].str.contains(y_str)]
            if not d_match.empty:
                 d_match = d_match.sort_values(by='Day')
                 r = d_match.iloc[-1]
                 row_data = {'MonthStr': t_date.strftime('%b %y'), 'Demand': r['Demand'], 'Collection': r['Collection'], 'SortDate': t_date, 'Order': i}; found = True
        if row_data: final_rows.append(row_data)

    if not final_rows: return None
    df_final = pd.DataFrame(final_rows).sort_values("Order")
    df_final['Achievement %'] = (df_final['Collection'] / df_final['Demand'] * 100).fillna(0)
    df_final['X_Label'] = df_final.apply(lambda x: f"{x['MonthStr']}<br><b>{x['Achievement %']:.1f}%</b>", axis=1)
    
    max_val = max(df_final['Demand'].max(), df_final['Collection'].max())
    tick_vals = []; tick_text = []
    if max_val > 0:
        step = 1000000 if max_val < 10000000 else 5000000; curr = 0
        while curr <= max_val * 1.15:
            tick_vals.append(curr)
            if curr == 0: tick_text.append("0")
            elif curr >= 10000000: tick_text.append(f"{curr/10000000:g} Cr")
            elif curr >= 100000: tick_text.append(f"{curr/100000:g} L")
            else: tick_text.append(f"{curr/1000:g} K")
            curr += step

    fig = go.Figure()
    fig.add_trace(go.Bar(x=df_final['X_Label'], y=df_final['Demand'], name='Demand', marker_color='rgba(22, 163, 74, 0.4)', width=0.6, hovertemplate='Demand: %{y:,.0f}<extra></extra>'))
    fig.add_trace(go.Bar(x=df_final['X_Label'], y=df_final['Collection'], name='Collected', marker_color='#1e3a8a', width=0.35, hovertemplate='Collected: %{y:,.0f}<extra></extra>'))
    fig.update_layout(title=dict(text=f"{subdivision}", font=dict(color='#0f172a', size=22, family="Arial Black")), xaxis=dict(title=None, tickfont=dict(color='#0f172a', size=14, weight="bold"), categoryorder='array', categoryarray=df_final['X_Label']), yaxis=dict(title="Amount", showgrid=False, tickfont=dict(color='#0f172a', size=12), tickmode='array', tickvals=tick_vals, ticktext=tick_text), barmode='overlay', legend=dict(orientation="h", y=1.1, font=dict(color='#0f172a', size=14)), height=400, margin=dict(l=0, r=0, t=50, b=0), font=dict(color="#0f172a", size=14), plot_bgcolor="rgba(0,0,0,0)")
    return fig

def create_ai_trend_chart(df_daily_hist, current_data_df, subdivision, days_in_month, report_time_obj, selected_date):
    df_prev = df_daily_hist[df_daily_hist['Sub-Div'] == subdivision].copy()
    df_curr = current_data_df[current_data_df['Sub-Div'] == subdivision].copy()
    if df_prev.empty and df_curr.empty: return None
    if not df_curr.empty: df_curr = df_curr.sort_values('Date'); df_curr['Day'] = df_curr['Date'].dt.day
    stats_per_day = df_prev.groupby('Day')['Collection'].agg(['min', 'max', 'mean']).reset_index()
    stats_per_day = stats_per_day[stats_per_day['Day'] <= 31]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=stats_per_day['Day'], y=stats_per_day['max'], mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=stats_per_day['Day'], y=stats_per_day['min'], mode='lines', line=dict(width=0), fill='tonexty', fillcolor='rgba(148, 163, 184, 0.4)', name='Historical Range', showlegend=True, hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=stats_per_day['Day'], y=stats_per_day['mean'], mode='lines', line=dict(color='#475569', width=2, dash='dot'), name='Avg. Historic Trend'))

    if not df_curr.empty:
        fig.add_trace(go.Scatter(x=df_curr['Day'], y=df_curr['Collection'], mode='lines+markers', line=dict(color='#1e3a8a', width=4), name='Current Month'))
        last_day = df_curr.iloc[-1]['Day']; last_val = df_curr.iloc[-1]['Collection']
        fig.add_annotation(x=last_day, y=last_val, text=f"Today: {format_indian_currency(last_val)}", showarrow=True, arrowhead=2, ax=0, ay=-40, bgcolor="white", bordercolor="#1e3a8a", borderwidth=2, font=dict(color="#1e3a8a", weight="bold"))
        if len(df_curr) > 1:
            proj_val = calculate_smart_projection(last_val, last_day, df_daily_hist, subdivision, days_in_month, df_curr['Demand'].max(), report_time_obj)
            fig.add_trace(go.Scatter(x=[last_day, days_in_month], y=[last_val, proj_val], mode='lines', line=dict(color='#d97706', width=3, dash='dot'), name='AI Forecast'))

    max_y = max(stats_per_day['max'].max() if not stats_per_day.empty else 0, df_curr['Collection'].max() if not df_curr.empty else 0)
    tick_vals = []; tick_text = []
    if max_y > 0:
        step = 5000000 if max_y > 50000000 else 1000000; curr = 0
        while curr <= max_y * 1.2:
            tick_vals.append(curr)
            if curr == 0: tick_text.append("0")
            elif curr >= 10000000: tick_text.append(f"{curr/10000000:g} Cr")
            elif curr >= 100000: tick_text.append(f"{curr/100000:g} L")
            else: tick_text.append(f"{curr/1000:g} K")
            curr += step

    fig.update_layout(title=dict(text=f"{subdivision}", font=dict(color='#0f172a', size=18, family="Arial Black")), xaxis=dict(title="Day of Month", range=[1, 32], showgrid=False, tickfont=dict(color='#0f172a', size=12)), yaxis=dict(title="Collection", showgrid=True, gridcolor='#cbd5e1', tickmode='array', tickvals=tick_vals, ticktext=tick_text, tickfont=dict(color='#0f172a', size=12)), legend=dict(orientation="h", y=1.1, font=dict(color='#0f172a')), height=400, margin=dict(l=0, r=20, t=50, b=0), template="plotly_white", hovermode="x unified")
    return fig

def display_prediction_visuals(df_daily, df_hist_daily, key_suffix, selected_date, timestamp_str, report_time_obj):
    subdivs = df_daily['Sub-Div'].unique()
    subdivs = sorted(subdivs, key=lambda x: 0 if "CHILA" in x.upper() else 1)
    latest_data_date = df_daily['Date'].max()
    if pd.isna(latest_data_date): st.error("Error: Could not determine dates from files."); return
    days_in_month = calendar.monthrange(selected_date.year, selected_date.month)[1]
    current_day_number = latest_data_date.day
    days_rem = max(0, days_in_month - current_day_number)
    
    st.markdown('<div class="section-title">🎯 Monthly Target Projection</div>', unsafe_allow_html=True)
    if key_suffix != "report": st.info(f"📅 **Viewing Data for:** {latest_data_date.strftime('%d %B')}. **Days Remaining:** {days_rem}")

    for i, subdiv in enumerate(subdivs):
        sub_df = df_daily[df_daily['Sub-Div'] == subdiv].sort_values(by='Date')
        latest = sub_df.iloc[-1]
        curr_coll, curr_dem = latest['Collection'], latest['Demand']
        gap = max(0, curr_dem - curr_coll)
        percent = (curr_coll / curr_dem * 100) if curr_dem > 0 else 0
        proj_coll = calculate_smart_projection(curr_coll, current_day_number, df_hist_daily, subdiv, days_in_month, curr_dem, report_time_obj)
        
        plot_df = sub_df[sub_df['Demand'] > 0].copy()
        
        if len(sub_df) > 1:
            avg_rate = (curr_coll - sub_df.iloc[0]['Collection']) / (len(sub_df)-1)
            recent_df = sub_df.tail(5)
            if len(recent_df) > 1: recent_rate = (recent_df.iloc[-1]['Collection'] - recent_df.iloc[0]['Collection']) / (len(recent_df)-1)
            else: recent_rate = avg_rate
            momentum_pct = ((recent_rate - avg_rate) / avg_rate * 100) if avg_rate > 0 else 0
        else: momentum_pct = 0; recent_rate = 0

        ai_msg = ""; box_class = "ai-box"
        if momentum_pct > 10: ai_msg = f"🚀 **High Momentum:** Collection speed has accelerated by **{momentum_pct:.1f}%**."
        elif momentum_pct < -10: ai_msg = f"⚠️ **Slowing Down:** Recent collection speed dropped by **{abs(momentum_pct):.1f}%**."
        else: ai_msg = f"⚖️ **Steady Pace:** Collection is consistent."
        box_class = "ai-box warning" if momentum_pct < -10 else "ai-box"
        req_rate = gap / days_rem if days_rem > 0 else gap 
        req_label = "/day" if days_rem > 0 else " Due Today"
        
        date_span = f'<span style="font-size:0.9em; opacity:0.9">Data as of: {timestamp_str}</span>' if key_suffix != "report" else ""
        st.markdown(f"""<div class="subdiv-banner"><span>🏢 {subdiv}</span>{date_span}</div>""", unsafe_allow_html=True)
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("CURRENT DEMAND", format_indian_currency(curr_dem))
        m2.metric("TOTAL COLLECTED", format_indian_currency(curr_coll))
        m3.metric("ACHIEVEMENT %", f"{percent:.1f}%")
        m4.metric("GAP TO TARGET", format_indian_currency(gap), delta=-gap, delta_color="inverse")
        m5.metric("PROJECTED COLL.", format_indian_currency(proj_coll), delta=format_indian_currency(proj_coll - curr_coll), delta_color="normal")
        
        st.markdown("<hr style='margin: 15px 0; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)
        c_chart, c_verdict = st.columns([2, 1])
        with c_chart:
            st.markdown("**📉 Forecast Trajectory**")
            fig = px.line(plot_df, x="Date", y=["Collection", "Demand"], markers=True, color_discrete_sequence=["#1e3a8a", "#c2410c"]) 
            if gap > 0:
                if days_rem > 0:
                    fut_date = latest['Date'] + timedelta(days=days_rem)
                    fig.add_scatter(x=[latest['Date'], fut_date], y=[curr_coll, proj_coll], mode='lines+markers', line=dict(dash='dot', color='#15803d', width=3), name='Forecast')
                    fig.add_scatter(x=[fut_date], y=[curr_dem], mode='markers', marker=dict(symbol='star', size=12, color='#b91c1c'), name='Goal')
                else:
                    fig.add_scatter(x=[latest['Date'], latest['Date']], y=[curr_coll, proj_coll], mode='lines+markers', line=dict(dash='dot', color='#15803d', width=3), name='EOD Forecast')
            max_val = max(curr_coll, curr_dem, proj_coll); tick_vals = []; tick_text = []
            if max_val > 0:
                step = 1000000 if max_val < 10000000 else 5000000; curr = 0
                while curr <= max_val * 1.2:
                    tick_vals.append(curr)
                    if curr == 0: tick_text.append("0")
                    elif curr >= 10000000: tick_text.append(f"{curr/10000000:g} Cr")
                    elif curr >= 100000: tick_text.append(f"{curr/100000:g} L")
                    else: tick_text.append(f"{curr/1000:g} K")
                    curr += step
            fig.update_layout(template="plotly_white", height=300, margin=dict(l=0,r=0,t=10,b=0), legend=dict(orientation="h", y=1.1, font=dict(size=14, color='#0f172a')), yaxis=dict(tickmode='array', tickvals=tick_vals, ticktext=tick_text, tickfont=dict(size=12, color='#0f172a')))
            st.plotly_chart(fig, width='stretch', key=f"pred_chart_{subdiv}_{i}_{key_suffix}")
        with c_verdict:
            st.markdown('<div class="verdict-box">', unsafe_allow_html=True)
            st.markdown("#### 🤖 Forecast Verdict")
            if gap <= 0: st.success("🎉 **100% ACHIEVED!**")
            else:
                st.metric("Required Rate", format_indian_currency(gap / days_rem if days_rem > 0 else gap) + "/day")
                st.metric("Current Velocity", format_indian_currency(recent_rate) + "/day")
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="{box_class}">{ai_msg}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

# --- 7. TABS LOGIC ---
t1, t2, t3 = st.tabs(["📊 Daily Performance Review", "🎯 Monthly Projection", "📄 Full Report (Print View)"])

with t1:
    if st.session_state[ADMIN_KEY]:
        st.markdown('<div class="section-title">Step 1: Configure & Enter Manual Data</div>', unsafe_allow_html=True)
        with st.expander("📝 Month Names & TDC Data (Theft Detection)", expanded=True):
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                st.session_state['month_names'] = [st.session_state['n1'], st.session_state['n2'], st.session_state['n3']]
                st.session_state['month_names'][0] = st.text_input("Label 1", key="input_n1", on_change=persist_change)
                st.session_state['c_n1'] = st.number_input(f"CHESD {st.session_state['month_names'][0]} TDC", min_value=0, value=st.session_state.get('c_n1',0), key="num_c_n1", on_change=persist_change)
                st.session_state['j_n1'] = st.number_input(f"JESD {st.session_state['month_names'][0]} TDC", min_value=0, value=st.session_state.get('j_n1',0), key="num_j_n1", on_change=persist_change)
            with col_m2:
                st.session_state['month_names'][1] = st.text_input("Label 2", key="input_n2", on_change=persist_change)
                st.session_state['c_n2'] = st.number_input(f"CHESD {st.session_state['month_names'][1]} TDC", min_value=0, value=st.session_state.get('c_n2',0), key="num_c_n2", on_change=persist_change)
                st.session_state['j_n2'] = st.number_input(f"JESD {st.session_state['month_names'][1]} TDC", min_value=0, value=st.session_state.get('j_n2',0), key="num_j_n2", on_change=persist_change)
            with col_m3:
                st.session_state['month_names'][2] = st.text_input("Label 3", key="input_n3", on_change=persist_change)
                st.session_state['c_n3'] = st.number_input(f"CHESD {st.session_state['month_names'][2]} TDC", min_value=0, value=st.session_state.get('c_n3',0), key="num_c_n3", on_change=persist_change)
                st.session_state['j_n3'] = st.number_input(f"JESD {st.session_state['month_names'][2]} TDC", min_value=0, value=st.session_state.get('j_n3',0), key="num_j_n3", on_change=persist_change)
                st.markdown("---")
                c_d1, c_d2 = st.columns(2)
                st.session_state['d_c'] = c_d1.number_input("CHILAPATHAR DAILY TDC", min_value=0, value=st.session_state.get('d_c',0), key="num_d_c", on_change=persist_change)
                st.session_state['d_j'] = c_d2.number_input("JONAI DAILY TDC", min_value=0, value=st.session_state.get('d_j',0), key="num_d_j", on_change=persist_change)
    else:
        st.markdown('<div class="section-title">Step 1: Data (Read Only)</div>', unsafe_allow_html=True)
        st.info("🔒 Viewer mode — values below are saved data. Log in as admin in the sidebar to edit them.")
        st.markdown(
            f"**{st.session_state.get('n1', '')}** — CHESD TDC: {st.session_state.get('c_n1', 0)} · "
            f"JESD TDC: {st.session_state.get('j_n1', 0)}  \n"
            f"**{st.session_state.get('n2', '')}** — CHESD TDC: {st.session_state.get('c_n2', 0)} · "
            f"JESD TDC: {st.session_state.get('j_n2', 0)}  \n"
            f"**{st.session_state.get('n3', '')}** — CHESD TDC: {st.session_state.get('c_n3', 0)} · "
            f"JESD TDC: {st.session_state.get('j_n3', 0)}  \n\n"
            f"**Daily TDC** — CHILAPATHAR: {st.session_state.get('d_c', 0)} · "
            f"JONAI: {st.session_state.get('d_j', 0)}"
        )
    st.markdown(f'<div class="section-title">Step 2: Auto-Load Daily Data (Day {report_date.day})</div>', unsafe_allow_html=True)
    if 'quarterly_df' in st.session_state and not st.session_state['quarterly_df'].empty:
        display_quarterly_visuals(st.session_state['quarterly_df'], st.session_state['quarterly_labels'], st.session_state['daily_tdc_data'], key_suffix="tab1", download_in_sidebar=True)
    else: st.info("ℹ️ Data not available.")

with t2:
    st.markdown('<div class="section-title">📊 Historical Performance & Prediction</div>', unsafe_allow_html=True)
    st.subheader("HISTORICAL PERFORMANCE")
    hc1, hc2 = st.columns(2)
    with hc1: st.plotly_chart(create_history_chart(st.session_state.get('history_df',None), "CHILAPATHAR", report_date, st.session_state.get('prev_daily_df',None), st.session_state.get('daily_df',None)), width='stretch')
    with hc2: st.plotly_chart(create_history_chart(st.session_state.get('history_df',None), "JONAI", report_date, st.session_state.get('prev_daily_df',None), st.session_state.get('daily_df',None)), width='stretch')
    
    if 'daily_df' in st.session_state:
        st.subheader("📈 Trend Analysis (Current vs History)")
        df_daily_final = st.session_state['daily_df']
        days_in_month = calendar.monthrange(report_date.year, report_date.month)[1]
        ac1, ac2 = st.columns(2)
        with ac1: st.plotly_chart(create_ai_trend_chart(st.session_state['prev_daily_df'], df_daily_final, "CHILAPATHAR", days_in_month, report_time, report_date), width='stretch')
        with ac2: st.plotly_chart(create_ai_trend_chart(st.session_state['prev_daily_df'], df_daily_final, "JONAI", days_in_month, report_time, report_date), width='stretch')
        st.markdown("---")
        display_prediction_visuals(df_daily_final, st.session_state['prev_daily_df'], key_suffix="tab2", selected_date=report_date, timestamp_str=display_timestamp, report_time_obj=report_time)
    else: st.warning(f"⚠️ No daily data found for {report_date.strftime('%B %Y')}")

with t3:
    with st.container():
        st.markdown('<div class="block-container">', unsafe_allow_html=True)
        render_header_html()
        st.markdown("<br>", unsafe_allow_html=True)
        if 'quarterly_df' in st.session_state and not st.session_state['quarterly_df'].empty:
            st.markdown('<div class="section-title">📊 Daily Performance Review</div>', unsafe_allow_html=True)
            st.markdown(f"""<div style="font-size: 2rem; font-weight: 900; color: #0f172a; margin-top: -10px; margin-bottom: 25px; padding-left: 20px;">{report_date.strftime('%d %B, %Y')}</div>""", unsafe_allow_html=True)
            display_quarterly_visuals(st.session_state['quarterly_df'], st.session_state['quarterly_labels'], st.session_state.get('daily_tdc_data', []), key_suffix="report", hide_title=True, download_in_sidebar=False)
            st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="section-title">HISTORICAL PERFORMANCE</div>', unsafe_allow_html=True)
        rc1, rc2 = st.columns(2)
        with rc1: st.plotly_chart(create_history_chart(st.session_state.get('history_df',None), "CHILAPATHAR", report_date, st.session_state.get('prev_daily_df',None), st.session_state.get('daily_df',None)), width='stretch', key="hist_ch_rep")
        with rc2: st.plotly_chart(create_history_chart(st.session_state.get('history_df',None), "JONAI", report_date, st.session_state.get('prev_daily_df',None), st.session_state.get('daily_df',None)), width='stretch', key="hist_jo_rep")
        st.markdown("<br>", unsafe_allow_html=True)
        if 'daily_df' in st.session_state:
            st.markdown('<div class="section-title">📈 Trend Analysis</div>', unsafe_allow_html=True)
            df_daily_rep = st.session_state['daily_df']
            days_in_month_rep = calendar.monthrange(report_date.year, report_date.month)[1]
            tc1, tc2 = st.columns(2)
            with tc1: st.plotly_chart(create_ai_trend_chart(st.session_state['prev_daily_df'], df_daily_rep, "CHILAPATHAR", days_in_month_rep, report_time, report_date), width='stretch', key="ai_ch_rep")
            with tc2: st.plotly_chart(create_ai_trend_chart(st.session_state['prev_daily_df'], df_daily_rep, "JONAI", days_in_month_rep, report_time, report_date), width='stretch', key="ai_jo_rep")
            st.markdown("<br>", unsafe_allow_html=True)
            display_prediction_visuals(df_daily_rep, st.session_state['prev_daily_df'], key_suffix="report", selected_date=report_date, timestamp_str=display_timestamp, report_time_obj=report_time)
        st.markdown('</div>', unsafe_allow_html=True)