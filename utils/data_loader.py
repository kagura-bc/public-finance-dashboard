import re
import pandas as pd
import numpy as np
import streamlit as st
from streamlit_gsheets import GSheetsConnection

_PATTERN_NEG = re.compile(r'[▲△▼▽∆Δ\-\−\–\—\‐\─]|^\s*[\(（].*[\)）]\s*$')
_PATTERN_CLEAN = re.compile(r'[▲△▼▽∆Δ,,\(（\)）\s\-\−\–\—\‐\─]')

def _clean_single_value(val):
    if pd.isna(val) or val is None:
        return np.nan
    if isinstance(val, (int, float)):
        return float(val)
    st_val = str(val).strip()
    if not st_val or st_val.lower() in ('nan', 'none', '-', '▲', '△'):
        return np.nan
    
    is_neg = bool(_PATTERN_NEG.search(st_val))
    cleaned = _PATTERN_CLEAN.sub('', st_val)
    try:
        num = float(cleaned)
        return -num if is_neg else num
    except ValueError:
        return np.nan

def _clean_dataframe_numeric(df, exclude_cols=None):
    if exclude_cols is None:
        exclude_cols = ['年度', '都道府県', '都市区分', '自治体種別', '団体名', 'コード', '備考']
    
    df = df.copy()
    for col in df.columns:
        if col in exclude_cols:
            continue
        df[col] = [_clean_single_value(v) for v in df[col]]
        
    return df

def _read_gsheet_safe(spreadsheet_url_or_id, worksheet_name=None):
    try:
        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            pk = st.secrets["connections"]["gsheets"].get("private_key", "")
            if "\\n" in pk:
                st.secrets["connections"]["gsheets"]["private_key"] = pk.replace("\\n", "\n")

        conn = st.connection("gsheets", type=GSheetsConnection)
        
        if worksheet_name:
            df = conn.read(spreadsheet=spreadsheet_url_or_id, worksheet=worksheet_name, ttl="1h")
        else:
            df = conn.read(spreadsheet=spreadsheet_url_or_id, ttl="1h")
    except Exception as e:
        st.error(f"スプレッドシートの読み込みに失敗しました ({spreadsheet_url_or_id}): {e}")
        return pd.DataFrame()
    
    if df.empty:
        return pd.DataFrame()

    if '年度' in df.columns:
        df['年度'] = df['年度'].astype(str)
        
    exclude_cols = ['年度', '都道府県', '団体名', '都市区分', '自治体種別', 'コード', '備考']
    df = _clean_dataframe_numeric(df, exclude_cols)
    return df

# --- 市区町村用データ読み込み ---
@st.cache_data(ttl="1h")
def load_data():
    url_overview = st.secrets["connections"]["gsheets"].get("url_overview")
    url_revenue = st.secrets["connections"]["gsheets"].get("url_revenue", url_overview)
    url_exp_nature = st.secrets["connections"]["gsheets"].get("url_exp_nature", url_overview)
    url_exp_purpose = st.secrets["connections"]["gsheets"].get("url_exp_purpose", url_overview)
    url_bonds = st.secrets["connections"]["gsheets"].get("url_bonds", url_overview)

    df_overview = _read_gsheet_safe(url_overview)
    df_revenue = _read_gsheet_safe(url_revenue)
    df_exp_nature = _read_gsheet_safe(url_exp_nature)
    df_exp_purpose = _read_gsheet_safe(url_exp_purpose)
    df_bonds = _read_gsheet_safe(url_bonds)

    return df_overview, df_revenue, df_exp_nature, df_exp_purpose, df_bonds

# --- 都道府県用データ読み込み ---
@st.cache_data(ttl="1h")
def load_pref_data():
    url_pref_overview = st.secrets["connections"]["gsheets"].get("url_pref_overview")
    url_pref_revenue = st.secrets["connections"]["gsheets"].get("url_pref_revenue", url_pref_overview)
    url_pref_exp_nature = st.secrets["connections"]["gsheets"].get("url_pref_exp_nature", url_pref_overview)
    url_pref_exp_purpose = st.secrets["connections"]["gsheets"].get("url_pref_exp_purpose", url_pref_overview)
    url_pref_bonds = st.secrets["connections"]["gsheets"].get("url_pref_bonds", url_pref_overview)

    df_overview = _read_gsheet_safe(url_pref_overview)
    df_revenue = _read_gsheet_safe(url_pref_revenue)
    df_exp_nature = _read_gsheet_safe(url_pref_exp_nature)
    df_exp_purpose = _read_gsheet_safe(url_pref_exp_purpose)
    df_bonds = _read_gsheet_safe(url_pref_bonds)

    return df_overview, df_revenue, df_exp_nature, df_exp_purpose, df_bonds