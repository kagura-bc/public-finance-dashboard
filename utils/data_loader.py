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
        exclude_cols = ['年度', '都道府県', '都市区分', '自治体種別', '団体名', '市町村名', '自治体名', 'コード', '備考', '国勢調査_調査年']
    
    df = df.copy()
    for col in df.columns:
        if col in exclude_cols:
            continue
        df[col] = [_clean_single_value(v) for v in df[col]]
        
    return df

def _read_gsheet_safe(spreadsheet_url_or_id, candidate_worksheets=None):
    if not spreadsheet_url_or_id:
        return pd.DataFrame()

    try:
        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            pk = st.secrets["connections"]["gsheets"].get("private_key", "")
            if "\\n" in pk:
                st.secrets["connections"]["gsheets"]["private_key"] = pk.replace("\\n", "\n")

        conn = st.connection("gsheets", type=GSheetsConnection)
        
        if candidate_worksheets:
            if isinstance(candidate_worksheets, str):
                candidate_worksheets = [candidate_worksheets]
            
            df = pd.DataFrame()
            for ws in candidate_worksheets:
                try:
                    df = conn.read(spreadsheet=spreadsheet_url_or_id, worksheet=ws, ttl="1h")
                    if not df.empty:
                        break
                except Exception:
                    continue
            if df.empty:
                df = conn.read(spreadsheet=spreadsheet_url_or_id, ttl="1h")
        else:
            df = conn.read(spreadsheet=spreadsheet_url_or_id, ttl="1h")
            
    except Exception:
        return pd.DataFrame()
    
    if df.empty:
        return pd.DataFrame()

    if '年度' in df.columns:
        df['年度'] = df['年度'].astype(str)
        
    exclude_cols = ['年度', '都道府県', '団体名', '市町村名', '自治体名', '都市区分', '自治体種別', 'コード', '備考', '国勢調査_調査年']
    df = _clean_dataframe_numeric(df, exclude_cols)
    return df

@st.cache_data(ttl="1h")
def load_data():
    gsheets_secrets = st.secrets["connections"].get("gsheets", {}) if "connections" in st.secrets else {}
    
    url_overview = gsheets_secrets.get("url_overview", "")
    url_revenue = gsheets_secrets.get("url_revenue", url_overview)
    url_exp_nature = gsheets_secrets.get("url_exp_nature", url_overview)
    url_exp_purpose = gsheets_secrets.get("url_exp_purpose", gsheets_secrets.get("url_purpose", url_overview))
    url_bonds = gsheets_secrets.get("url_bonds", url_overview)

    ws_overview = [gsheets_secrets.get("ws_overview"), "概要", "財政概要", "Sheet1"]
    ws_revenue = [gsheets_secrets.get("ws_revenue"), "歳入", "歳入内訳"]
    ws_exp_nature = [gsheets_secrets.get("ws_exp_nature"), "性質別歳出", "性質別", "歳出(性質別)"]
    ws_exp_purpose = [gsheets_secrets.get("ws_exp_purpose"), "目的別歳出", "目的別", "歳出(目的別)"]
    ws_bonds = [gsheets_secrets.get("ws_bonds"), "地方債", "地方債・基金", "基金"]

    df_overview = _read_gsheet_safe(url_overview, [w for w in ws_overview if w])
    df_revenue = _read_gsheet_safe(url_revenue, [w for w in ws_revenue if w])
    df_exp_nature = _read_gsheet_safe(url_exp_nature, [w for w in ws_exp_nature if w])
    df_exp_purpose = _read_gsheet_safe(url_exp_purpose, [w for w in ws_exp_purpose if w])
    df_bonds = _read_gsheet_safe(url_bonds, [w for w in ws_bonds if w])

    return df_overview, df_revenue, df_exp_nature, df_exp_purpose, df_bonds