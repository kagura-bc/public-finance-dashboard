import re
import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection

# --- マイナス記号・特殊表記対応の数値変換ヘルパー ---
def _parse_numeric_value(val):
    if pd.isna(val) or val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
        
    s = str(val).strip()
    if not s or s in ['-', '―', 'ー', 'null', 'None', 'NaN', 'nan', '0']:
        return 0.0

    # マイナスを示す要素（▲, △, ▼, ▽, ∆, Δ, 括弧, 各種ハイフン・マイナス）が含まれるか判定
    is_negative = False
    if re.search(r'[▲△▼▽∆Δ\-\−\–\—\‐\─]|^\s*[\(（].*[\)）]\s*$', s):
        is_negative = True

    # 数字と小数点以外の文字（カンマ、スペース、記号等）を削除
    clean_s = re.sub(r'[^0-9.]', '', s)
    if not clean_s:
        return 0.0
        
    try:
        num = float(clean_s)
        return -num if (is_negative and num != 0) else num
    except:
        return 0.0

@st.cache_data(ttl="10m")
def load_data():
    def _read_gsheet_safe(spreadsheet_url_or_id, worksheet_name=None):
        try:
            # secrets内の private_key の \n (文字列) を実際の改行コードに自動補正
            if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
                pk = st.secrets["connections"]["gsheets"].get("private_key", "")
                if "\\n" in pk:
                    st.secrets["connections"]["gsheets"]["private_key"] = pk.replace("\\n", "\n")

            conn = st.connection("gsheets", type=GSheetsConnection)
            
            if worksheet_name:
                df = conn.read(spreadsheet=spreadsheet_url_or_id, worksheet=worksheet_name, ttl="10m")
            else:
                df = conn.read(spreadsheet=spreadsheet_url_or_id, ttl="10m")
        except Exception as e:
            st.error(f"スプレッドシートの読み込みに失敗しました ({spreadsheet_url_or_id}): {e}")
            return pd.DataFrame()
        
        if df.empty:
            return pd.DataFrame()

        if '年度' in df.columns:
            df['年度'] = df['年度'].astype(str)
            
        exclude_cols = ['年度', '都道府県', '団体名', '都市区分', '自治体種別']
        num_cols = [c for c in df.columns if c not in exclude_cols]
        for col in num_cols:
            if df[col].dtype == 'object':
                df[col] = df[col].apply(_parse_numeric_value)
        return df

    url_overview = st.secrets["connections"]["gsheets"].get("url_overview", st.secrets["connections"]["gsheets"].get("spreadsheet"))
    url_revenue = st.secrets["connections"]["gsheets"].get("url_revenue", url_overview)
    url_exp_nature = st.secrets["connections"]["gsheets"].get("url_exp_nature", url_overview)
    url_exp_purpose = st.secrets["connections"]["gsheets"].get("url_exp_purpose", url_overview)
    url_bonds = st.secrets["connections"]["gsheets"].get("url_bonds", url_overview)

    df_overview = _read_gsheet_safe(url_overview)
    df_revenue = _read_gsheet_safe(url_revenue)
    df_exp_nature = _read_gsheet_safe(url_exp_nature)
    df_exp_purpose = _read_gsheet_safe(url_exp_purpose)
    df_bonds = _read_gsheet_safe(url_bonds)
    
    if not df_exp_purpose.empty:
        if '労働費_合計' not in df_exp_purpose.columns and '労働費_失業対策費' in df_exp_purpose.columns and '労働費_労働諸費' in df_exp_purpose.columns:
            df_exp_purpose['労働費_合計'] = df_exp_purpose['労働費_失業対策費'].fillna(0) + df_exp_purpose['労働費_労働諸費'].fillna(0)
            
        misc_cols = [c for c in ['諸支出金_普通財産取得費', '諸支出金_公営企業費', '諸支出金_市町村たばこ税都道府県交付金'] if c in df_exp_purpose.columns]
        if misc_cols and '諸支出金_合計' not in df_exp_purpose.columns:
            df_exp_purpose['諸支出金_合計'] = df_exp_purpose[misc_cols].sum(axis=1)

    return df_overview, df_revenue, df_exp_nature, df_exp_purpose, df_bonds