import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection

@st.cache_data(ttl="10m")  # 10分間データをキャッシュして高速化
def load_data():
    """
    Googleスプレッドシートから5つのデータを取得・クレンジングして返す関数
    """
    def _read_gsheet_safe(spreadsheet_url_or_id, worksheet_name=None):
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            
            # シート名が指定されている場合はworksheetパラメータを付与
            if worksheet_name:
                df = conn.read(spreadsheet=spreadsheet_url_or_id, worksheet=worksheet_name, ttl="10m")
            else:
                df = conn.read(spreadsheet=spreadsheet_url_or_id, ttl="10m")
        except Exception as e:
            st.error(f"スプレッドシートの読み込みに失敗しました ({spreadsheet_url_or_id}): {e}")
            return pd.DataFrame()
        
        if df.empty:
            return pd.DataFrame()

        # 年度カラムの文字列化
        if '年度' in df.columns:
            df['年度'] = df['年度'].astype(str)
            
        # 数値カラムのクレンジング（カンマ・ハイフンの置換と数値変換）
        exclude_cols = ['年度', '都道府県', '団体名', '都市区分', '自治体種別']
        num_cols = [c for c in df.columns if c not in exclude_cols]
        for col in num_cols:
            if df[col].dtype == 'object':
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(',', '').str.replace(' ', '').str.replace('-', '0'),
                    errors='coerce'
                )
        return df

    # --- 各スプレッドシートのURL（またはSecrets設定のキー）を指定 ---
    # ※ Secrets側で各URLを定義するか、以下に直接スプレッドシートのURLを記載してください
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
    
    # 目的別歳出の派生・合計項目の事前計算
    if not df_exp_purpose.empty:
        if '労働費_合計' not in df_exp_purpose.columns and '労働費_失業対策費' in df_exp_purpose.columns and '労働費_労働諸費' in df_exp_purpose.columns:
            df_exp_purpose['労働費_合計'] = df_exp_purpose['労働費_失業対策費'].fillna(0) + df_exp_purpose['労働費_労働諸費'].fillna(0)
            
        misc_cols = [c for c in ['諸支出金_普通財産取得費', '諸支出金_公営企業費', '諸支出金_市町村たばこ税都道府県交付金'] if c in df_exp_purpose.columns]
        if misc_cols and '諸支出金_合計' not in df_exp_purpose.columns:
            df_exp_purpose['諸支出金_合計'] = df_exp_purpose[misc_cols].sum(axis=1)

    return df_overview, df_revenue, df_exp_nature, df_exp_purpose, df_bonds