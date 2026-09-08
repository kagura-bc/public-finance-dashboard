import re
from pathlib import Path
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

def _read_local_csv_fallback(file_names):
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    
    if isinstance(file_names, str):
        file_names = [file_names]
        
    for fname in file_names:
        fpath = data_dir / fname
        if fpath.exists():
            try:
                df = pd.read_csv(fpath)
                if '年度' in df.columns:
                    df['年度'] = df['年度'].astype(str)
                return _clean_dataframe_numeric(df)
            except Exception:
                continue
    return pd.DataFrame()

@st.cache_data(ttl="1h")
def load_data():
    gsheets_secrets = st.secrets.get("connections", {}).get("gsheets", {}) if "connections" in st.secrets else {}
    
    url_overview = gsheets_secrets.get("url_overview", "")
    url_revenue = gsheets_secrets.get("url_revenue", url_overview)
    url_exp_nature = gsheets_secrets.get("url_exp_nature", url_overview)
    url_exp_purpose = gsheets_secrets.get("url_exp_purpose", gsheets_secrets.get("url_purpose", url_overview))
    url_bonds = gsheets_secrets.get("url_bonds", url_overview)
    url_pop = gsheets_secrets.get("url_pop", gsheets_secrets.get("url_population", url_overview))

    ws_overview = [gsheets_secrets.get("ws_overview"), "概要", "財政概要", "Sheet1"]
    ws_revenue = [gsheets_secrets.get("ws_revenue"), "歳入", "歳入内訳"]
    ws_exp_nature = [gsheets_secrets.get("ws_exp_nature"), "性質別歳出", "性質別", "歳出(性質別)"]
    ws_exp_purpose = [gsheets_secrets.get("ws_exp_purpose"), "目的別歳出", "目的別", "歳出(目的別)"]
    ws_bonds = [gsheets_secrets.get("ws_bonds"), "地方債", "地方債・基金", "基金"]
    ws_pop = [gsheets_secrets.get("ws_pop"), "人口", "人口構造", "人口・世帯"]

    df_overview = _read_gsheet_safe(url_overview, [w for w in ws_overview if w])
    df_revenue = _read_gsheet_safe(url_revenue, [w for w in ws_revenue if w])
    df_exp_nature = _read_gsheet_safe(url_exp_nature, [w for w in ws_exp_nature if w])
    df_exp_purpose = _read_gsheet_safe(url_exp_purpose, [w for w in ws_exp_purpose if w])
    df_bonds = _read_gsheet_safe(url_bonds, [w for w in ws_bonds if w])
    df_pop = _read_gsheet_safe(url_pop, [w for w in ws_pop if w])

    # ローカルファイルフォールバック
    if df_overview.empty:
        df_overview = _read_local_csv_fallback(["overview.csv", "city_overview.csv"])
    if df_revenue.empty:
        df_revenue = _read_local_csv_fallback(["revenue.csv", "city_revenue.csv"])
    if df_exp_nature.empty:
        df_exp_nature = _read_local_csv_fallback(["exp_nature.csv", "city_exp_nature.csv"])
    if df_exp_purpose.empty:
        df_exp_purpose = _read_local_csv_fallback(["exp_purpose.csv", "city_exp_purpose.csv"])
    if df_bonds.empty:
        df_bonds = _read_local_csv_fallback(["bonds.csv", "city_bonds.csv"])
    if df_pop.empty:
        df_pop = _read_local_csv_fallback(["population.csv", "city_population.csv", "pop.csv"])

    return df_overview, df_revenue, df_exp_nature, df_exp_purpose, df_bonds, df_pop

@st.cache_data(ttl="1h")
def load_pref_data():
    gsheets_secrets = st.secrets.get("connections", {}).get("gsheets", {}) if "connections" in st.secrets else {}
    
    url_pref = gsheets_secrets.get("url_pref", gsheets_secrets.get("url_pref_overview", ""))
    url_overview = gsheets_secrets.get("url_pref_overview", url_pref if url_pref else gsheets_secrets.get("url_overview", ""))
    url_revenue = gsheets_secrets.get("url_pref_revenue", url_pref if url_pref else gsheets_secrets.get("url_revenue", url_overview))
    url_exp_nature = gsheets_secrets.get("url_pref_exp_nature", url_pref if url_pref else gsheets_secrets.get("url_exp_nature", url_overview))
    url_exp_purpose = gsheets_secrets.get("url_pref_exp_purpose", url_pref if url_pref else gsheets_secrets.get("url_exp_purpose", url_overview))
    url_bonds = gsheets_secrets.get("url_pref_bonds", url_pref if url_pref else gsheets_secrets.get("url_bonds", url_overview))
    url_pop = gsheets_secrets.get("url_pref_pop", url_pref if url_pref else gsheets_secrets.get("url_pop", url_overview))

    ws_overview = [gsheets_secrets.get("ws_pref_overview"), "都道府県_概要", "都道府県概要", "概要", "財政概要", "Sheet1"]
    ws_revenue = [gsheets_secrets.get("ws_pref_revenue"), "都道府県_歳入", "都道府県歳入", "歳入", "歳入内訳"]
    ws_exp_nature = [gsheets_secrets.get("ws_pref_exp_nature"), "都道府県_性質別歳出", "都道府県性質別", "性質別歳出", "性質別"]
    ws_exp_purpose = [gsheets_secrets.get("ws_pref_exp_purpose"), "都道府県_目的別歳出", "都道府県目的別", "目的別歳出", "目的別"]
    ws_bonds = [gsheets_secrets.get("ws_pref_bonds"), "都道府県_地方債", "都道府県地方債", "地方債", "地方債・基金", "基金"]
    ws_pop = [gsheets_secrets.get("ws_pref_pop"), "都道府県_人口", "都道府県人口", "人口", "人口構造", "人口・世帯"]

    df_overview = _read_gsheet_safe(url_overview, [w for w in ws_overview if w])
    df_revenue = _read_gsheet_safe(url_revenue, [w for w in ws_revenue if w])
    df_exp_nature = _read_gsheet_safe(url_exp_nature, [w for w in ws_exp_nature if w])
    df_exp_purpose = _read_gsheet_safe(url_exp_purpose, [w for w in ws_exp_purpose if w])
    df_bonds = _read_gsheet_safe(url_bonds, [w for w in ws_bonds if w])
    df_pop = _read_gsheet_safe(url_pop, [w for w in ws_pop if w])

    # 都道府県データ用ローカルファイルフォールバック
    if df_overview.empty:
        df_overview = _read_local_csv_fallback(["pref_overview.csv", "overview.csv"])
    if df_revenue.empty:
        df_revenue = _read_local_csv_fallback(["pref_revenue.csv", "revenue.csv"])
    if df_exp_nature.empty:
        df_exp_nature = _read_local_csv_fallback(["pref_exp_nature.csv", "exp_nature.csv"])
    if df_exp_purpose.empty:
        df_exp_purpose = _read_local_csv_fallback(["pref_exp_purpose.csv", "exp_purpose.csv"])
    if df_bonds.empty:
        df_bonds = _read_local_csv_fallback(["pref_bonds.csv", "bonds.csv"])
    if df_pop.empty:
        df_pop = _read_local_csv_fallback(["pref_population.csv", "pref_pop.csv", "population.csv", "pop.csv"])

    return df_overview, df_revenue, df_exp_nature, df_exp_purpose, df_bonds, df_pop

@st.cache_data(ttl="1h")
def load_city_data():
    return load_data()