import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from utils.data_loader import load_data

# --- 年度整形用ヘルパー関数 ---
def format_year(val):
    """'2024.0' や 2024.0 を '2024' に整形する"""
    if pd.isna(val):
        return ""
    s = str(val).strip()
    if s.endswith('.0'):
        return s[:-2]
    return s

# データの呼び出し（キャッシュから取得）
loaded_data = load_data()
if isinstance(loaded_data, (tuple, list)) and len(loaded_data) >= 5:
    df_overview, df_revenue, df_exp_nature, df_exp_purpose, df_bonds = loaded_data[:5]
else:
    df_overview, df_revenue, df_exp_nature, df_exp_purpose = loaded_data[:4]
    df_bonds = pd.DataFrame()

# 全データフレームの「年度」表記を「2024」形式に一括統一
for df in [df_overview, df_revenue, df_exp_nature, df_exp_purpose, df_bonds]:
    if not df.empty and '年度' in df.columns:
        df['年度'] = df['年度'].apply(format_year)

st.title("🏘️ 市町村 財政分析")

# --- ラベル整形用ヘルパー関数 ---
def clean_col_label(text):
    """'地方税_合計' や '地方税_合計_1人当たり' などの接尾辞を除去して綺麗な表示名にする"""
    if not isinstance(text, str):
        return text
    return (text.replace('_合計', '')
                .replace('_1人当たり', '')
                .replace('_パーセント', '')
                .replace('_割合', '')
                .replace('積立金現在高_', '')
                .replace('公営企業等に対する繰出金_', '')
                .replace('健全化判断比率_', ''))

# --- 市町村専用のサイドバーフィルター ---
st.sidebar.markdown("---")
st.sidebar.subheader("データ絞り込み")

# 1. 都市区分の選択
all_types = set()
if not df_overview.empty and '都市区分' in df_overview.columns:
    all_types.update(df_overview['都市区分'].dropna().unique())
type_options = ["すべて"] + sorted(list(all_types))
selected_type = st.sidebar.selectbox("都市区分を選択", type_options)

# 2. 都道府県の選択
PREF_ORDER = [
    '北海道', '青森県', '岩手県', '宮城県', '秋田県', '山形県', '福島県',
    '茨城県', '栃木県', '群馬県', '埼玉県', '千葉県', '東京都', '神奈川県',
    '新潟県', '富山県', '石川県', '福井県', '山梨県', '長野県', '岐阜県',
    '静岡県', '愛知県', '三重県', '滋賀県', '京都府', '大阪府', '兵庫県',
    '奈良県', '和歌山県', '鳥取県', '島根県', '岡山県', '広島県', '山口県',
    '徳島県', '香川県', '愛媛県', '高知県', '福岡県', '佐賀県', '長崎県',
    '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県'
]
pref_order_dict = {pref: i for i, pref in enumerate(PREF_ORDER)}

all_prefs = set()
df_ref = df_overview if not df_overview.empty else df_revenue
if not df_ref.empty and '都道府県' in df_ref.columns:
    df_filtered_temp = df_ref
    if selected_type != "すべて" and '都市区分' in df_filtered_temp.columns:
        df_filtered_temp = df_filtered_temp[df_filtered_temp['都市区分'] == selected_type]
    all_prefs.update(df_filtered_temp['都道府県'].dropna().unique())

sorted_prefs = sorted(list(all_prefs), key=lambda x: pref_order_dict.get(x, 999))
pref_options = ["全国"] + sorted_prefs
pref_default_idx = pref_options.index('山梨県') if '山梨県' in pref_options else 0
selected_pref = st.sidebar.selectbox("都道府県を選択", pref_options, index=pref_default_idx)

# 都道府県による表示用ラベルの設定
if selected_pref == "全国":
    scope_label = f"全国（{selected_type}）" if selected_type != "すべて" else "全国"
else:
    scope_label = f"{selected_pref}（{selected_type}）" if selected_type != "すべて" else selected_pref

# 3. 市町村・町村の選択
df_city_ref = df_overview if not df_overview.empty else df_revenue
filtered_city_df = df_city_ref.copy()
if selected_type != "すべて" and '都市区分' in filtered_city_df.columns:
    filtered_city_df = filtered_city_df[filtered_city_df['都市区分'] == selected_type]
if selected_pref != "全国" and '都道府県' in filtered_city_df.columns:
    filtered_city_df = filtered_city_df[filtered_city_df['都道府県'] == selected_pref]

city_list = sorted(filtered_city_df['団体名'].dropna().unique().tolist()) if '団体名' in filtered_city_df.columns else []
city_default_idx = city_list.index('甲府市') if '甲府市' in city_list else 0
selected_city = st.sidebar.selectbox("市町村・町村を選択", city_list, index=city_default_idx) if len(city_list) > 0 else st.sidebar.text("自治体データなし")

menu = st.sidebar.radio("表示メニュー", ["概要", "歳入", "性質別歳出", "目的別歳出", "地方債・基金"])

# --- フィルター処理関数（表記ゆれ・市町村区除去対応強化） ---
def filter_by_city(df, pref, city):
    if df.empty:
        return df
    
    city_col = None
    for candidate in ['団体名', '市町村名', '自治体名']:
        if candidate in df.columns:
            city_col = candidate
            break
            
    if not city_col:
        return df
    
    res = df.copy()
    clean_city = str(city).strip()
    clean_pref = str(pref).strip()
    
    # 末尾の「市」「町」「村」「区」を除去した基本名（例：「市川三郷町」→「市川三郷」）
    base_city = clean_city
    for suffix in ['市', '町', '村', '区']:
        if base_city.endswith(suffix) and len(base_city) > 1:
            base_city = base_city[:-1]
            break

    city_series = res[city_col].astype(str).str.strip()
    pref_col = '都道府県' if '都道府県' in res.columns else ('都道府県名' if '都道府県名' in res.columns else None)
    
    # 1. 完全名で検索
    if pref != "全国" and pref_col:
        pref_series = res[pref_col].astype(str).str.strip()
        filtered = res[(pref_series == clean_pref) & (city_series.str.contains(clean_city, regex=False))]
    else:
        filtered = res[city_series.str.contains(clean_city, regex=False)]
        
    # 2. ヒットしない場合、基本名（市町村区除去名）で再検索（表記ゆれ対応）
    if filtered.empty:
        if pref != "全国" and pref_col:
            pref_series = res[pref_col].astype(str).str.strip()
            filtered = res[(pref_series == clean_pref) & (city_series.str.contains(base_city, regex=False))]
        else:
            filtered = res[city_series.str.contains(base_city, regex=False)]

    if '年度' in filtered.columns:
        filtered = filtered.sort_values('年度', key=lambda x: x.astype(str))
        
    return filtered

def get_comparison_df(df):
    if df.empty:
        return df
    res = df.copy()
    
    if selected_type != "すべて" and '都市区分' in res.columns:
        res = res[res['都市区分'].astype(str).str.strip() == str(selected_type).strip()]
        
    if selected_pref != "全国" and '都道府県' in res.columns:
        res = res[res['都道府県'].astype(str).str.strip() == str(selected_pref).strip()]
        
    return res

# --- 人口カラム検出関数 ---
def get_population_col(df):
    pop_cols = [c for c in df.columns if '人口' in c and '千円' not in c and '%' not in c and 'パーセント' not in c]
    if not pop_cols:
        return None
    for priority_kw in ['住民基本台帳人口', '総人口', '人口']:
        matched = [c for c in pop_cols if priority_kw in c]
        if matched:
            return matched[0]
    return pop_cols[0]

# --- 人口取得用ヘルパー関数 ---
def get_population_series(df_target, df_ov, target_year="latest"):
    pop_col = get_population_col(df_ov)
    if not pop_col or df_ov.empty or df_target.empty:
        return pd.Series(np.nan, index=df_target.index)
    
    has_city_col = '団体名' in df_target.columns
    has_pref_col = '都道府県' in df_target.columns
    
    default_p = selected_pref if 'selected_pref' in globals() and selected_pref != "全国" else np.nan
    default_c = selected_city if 'selected_city' in globals() else np.nan
    
    pref_s = df_target['都道府県'] if has_pref_col else pd.Series(default_p, index=df_target.index)
    city_s = df_target['団体名'] if has_city_col else pd.Series(default_c, index=df_target.index)
    
    if city_s.isna().all():
        return pd.Series(np.nan, index=df_target.index)

    has_pref = pref_s.notna().any() and '都道府県' in df_ov.columns
    
    s_row = pd.Series(np.nan, index=df_target.index)
    if (target_year in ["latest", "by_row"]) and ('年度' in df_target.columns):
        df_ov_copy = df_ov.copy()
        df_ov_copy['年度_str'] = df_ov_copy['年度'].astype(str)
        if has_pref:
            pop_map_row = df_ov_copy.drop_duplicates(subset=['都道府県', '団体名', '年度_str']).set_index(['都道府県', '団体名', '年度_str'])[pop_col].to_dict()
            target_idx = pd.MultiIndex.from_arrays([pref_s, city_s, df_target['年度'].astype(str)])
            s_row = pd.Series(target_idx.map(pop_map_row), index=df_target.index)
        else:
            pop_map_row = df_ov_copy.drop_duplicates(subset=['団体名', '年度_str']).set_index(['団体名', '年度_str'])[pop_col].to_dict()
            target_idx = pd.MultiIndex.from_arrays([city_s, df_target['年度'].astype(str)])
            s_row = pd.Series(target_idx.map(pop_map_row), index=df_target.index)

    s_year = pd.Series(np.nan, index=df_target.index)
    if target_year not in ["latest", "by_row"]:
        df_ov_y = df_ov[df_ov['年度'].astype(str) == str(target_year)]
        if has_pref:
            pop_map_year = df_ov_y.drop_duplicates(subset=['都道府県', '団体名']).set_index(['都道府県', '団体名'])[pop_col].to_dict() if not df_ov_y.empty and pop_col in df_ov_y.columns else {}
            target_idx = pd.MultiIndex.from_arrays([pref_s, city_s])
            s_year = pd.Series(target_idx.map(pop_map_year), index=df_target.index)
        else:
            pop_dict_year = df_ov_y.drop_duplicates(subset=['団体名']).set_index('団体名')[pop_col].to_dict() if not df_ov_y.empty and pop_col in df_ov_y.columns else {}
            s_year = city_s.map(pop_dict_year)

    df_ov_latest = df_ov.sort_values('年度', key=lambda x: x.astype(str)).groupby(['都道府県', '団体名'] if has_pref else '団体名').last().reset_index() if not df_ov.empty else pd.DataFrame()
    if has_pref:
        pop_map_latest = df_ov_latest.set_index(['都道府県', '団体名'])[pop_col].to_dict() if not df_ov_latest.empty and pop_col in df_ov_latest.columns else {}
        target_idx = pd.MultiIndex.from_arrays([pref_s, city_s])
        s_latest = pd.Series(target_idx.map(pop_map_latest), index=df_target.index)
    else:
        pop_dict_latest = df_ov_latest.set_index('団体名')[pop_col].to_dict() if not df_ov_latest.empty and pop_col in df_ov_latest.columns else {}
        s_latest = city_s.map(pop_dict_latest)

    pop_series = s_row.fillna(s_year).fillna(s_latest)
    return pd.to_numeric(pop_series, errors='coerce')

# 選択された自治体のデータを抽出
df_ov_city = filter_by_city(df_overview, selected_pref, selected_city)
df_rev_city = filter_by_city(df_revenue, selected_pref, selected_city)
df_exp_city = filter_by_city(df_exp_nature, selected_pref, selected_city)
df_purp_city = filter_by_city(df_exp_purpose, selected_pref, selected_city)
df_bonds_city = filter_by_city(df_bonds, selected_pref, selected_city)

st.write(f"**{scope_label} {selected_city}** のデータをご案内します。")

# ==========================================
# メニュー1: 概要 （略：変更なし）
# ==========================================
if menu == "概要":
    st.markdown("### 財政状況の概要（パッケージ表示）")
    if not df_ov_city.empty:
        tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
            "🏆 総合評価・ランキング",
            "💪 財政力（自力で稼ぐ力）",
            "⚙️ 効率性（やりくりの上手さ）",
            "🚨 健全性（将来のリスク・安心感）",
            "🏙️ 都市構造・インフラ効率性",
            "👥 人口・産業",
            "📋 データ一覧"
        ])
        
        num_cols = df_ov_city.select_dtypes(include=['number']).columns.tolist()
        def get_cols_by_keywords(keywords):
            return [col for col in num_cols if any(kw in col for kw in keywords)]

        with tab1:
            st.markdown(f"#### 🏆 {scope_label} 財政健全化総合ポイントランキング & 比較分析")
            with st.expander("💡 「真の稼ぐ力・財政の余裕」を判断するための補完指標ガイド", expanded=True):
                st.markdown("""
                自治体の「稼ぐ力」と「財政構造の強さ」を正しく把握するには、財政力指数に加えて以下の指標をセットで分析する必要があります。
                * **人口1人当たりの地方税収入**: 最も直接的な「地域の経済力・稼ぐ力」の指標です。
                * **自主財源比率**: 歳入全体のうち、自力で稼ぎ出したお金が占める割合です。
                * **経常収支比率**: 毎年の収入のうち「固定費」にどれだけ取られているかを示します。低いほど財政の弾力性があります。
                * **将来負担比率・実質将来負担**: 将来支払うべき負債の重さを示します。低いほど健全です。
                """)

            available_ov_years = sorted(df_overview['年度'].astype(str).unique()) if not df_overview.empty else []
            if available_ov_years:
                selected_rank_year = st.selectbox("分析対象年度を選択", available_ov_years, index=len(available_ov_years)-1, key="rank_year_select")
                
                df_ov_all = df_overview[df_overview['年度'].astype(str) == str(selected_rank_year)].copy() if not df_overview.empty else pd.DataFrame()
                df_rev_all = df_revenue[df_revenue['年度'].astype(str) == str(selected_rank_year)].copy() if not df_revenue.empty else pd.DataFrame()
                df_bonds_all = df_bonds[df_bonds['年度'].astype(str) == str(selected_rank_year)].copy() if not df_bonds.empty else pd.DataFrame()
                
                if not df_ov_all.empty:
                    df_rank_base = df_ov_all.copy()
                    
                    if not df_bonds_all.empty:
                        b_cols = ['都道府県', '団体名', '地方債現在高_合計', '積立金現在高_合計', '債務負担行為額(翌年度以降支出予定額)_合計']
                        b_cols_exist = [c for c in b_cols if c in df_bonds_all.columns]
                        df_rank_base = pd.merge(df_rank_base, df_bonds_all[b_cols_exist].drop_duplicates(subset=['都道府県', '団体名']), on=['都道府県', '団体名'], how='left')
                    
                    if not df_rev_all.empty:
                        jishu_cand = ['地方税_合計', '分担金及び負担金_合計', '使用料_合計', '手数料_合計', '財産収入_合計', '寄附金_合計', '繰入金_合計', '繰越金_合計', '諸収入_合計']
                        jishu_exist = [c for c in jishu_cand if c in df_rev_all.columns]

                        izon_cand = ['地方譲与税_合計', '都道府県税交付金_合計', '地方特例交付金_合計', '地方交付税_合計', '交通安全対策特別交付金', '国庫支出金_合計', '都道府県支出金_合計', '地方債_合計', '国有提供施設等所在市町村助成交付金', '特別区財政調整交付金']
                        izon_exist = [c for c in izon_cand if c in df_rev_all.columns]

                        df_rev_calc = df_rev_all.copy()
                        df_rev_calc['自主財源_合計'] = df_rev_calc[jishu_exist].sum(axis=1) if jishu_exist else 0
                        df_rev_calc['依存財源_合計'] = df_rev_calc[izon_exist].sum(axis=1) if izon_exist else 0
                        df_rev_calc['歳入総額_calc'] = df_rev_calc['自主財源_合計'] + df_rev_calc['依存財源_合計']
                        
                        rev_merge_cols = ['都道府県', '団体名', '地方税_合計', '自主財源_合計', '歳入総額_calc']
                        rev_merge_cols = [c for c in rev_merge_cols if c in df_rev_calc.columns]
                        df_rank_base = pd.merge(df_rank_base, df_rev_calc[rev_merge_cols].drop_duplicates(subset=['都道府県', '団体名']), on=['都道府県', '団体名'], how='left')

                    df_rank_base['人口_num'] = get_population_series(df_rank_base, df_overview, selected_rank_year)

                    valid_pop = df_rank_base['人口_num'].replace(0, np.nan)
                    if '地方税_合計' in df_rank_base.columns:
                        df_rank_base['1人当たり地方税収入(千円)'] = (df_rank_base['地方税_合計'] / valid_pop).round(1)
                    if '地方債現在高_合計' in df_rank_base.columns:
                        df_rank_base['1人当たり地方債(千円)'] = (df_rank_base['地方債現在高_合計'] / valid_pop).round(1)
                    if '積立金現在高_合計' in df_rank_base.columns:
                        df_rank_base['1人当たり基金(千円)'] = (df_rank_base['積立金現在高_合計'] / valid_pop).round(1)
                    if '地方債現在高_合計' in df_rank_base.columns and '積立金現在高_合計' in df_rank_base.columns:
                        debt_val = df_rank_base['地方債現在高_合計'].fillna(0)
                        fund_val = df_rank_base['積立金現在高_合計'].fillna(0)
                        commit_val = df_rank_base['債務負担行為額(翌年度以降支出予定額)_合計'].fillna(0) if '債務負担行為額(翌年度以降支出予定額)_合計' in df_rank_base.columns else 0
                        df_rank_base['実質将来負担残高_推計'] = debt_val + commit_val - fund_val
                        df_rank_base['1人当たり実質将来負担(千円)'] = (df_rank_base['実質将来負担残高_推計'] / valid_pop).round(1)
                    
                    if '自主財源_合計' in df_rank_base.columns and '歳入総額_calc' in df_rank_base.columns:
                        df_rank_base['自主財源比率(%)'] = ((df_rank_base['自主財源_合計'] / df_rank_base['歳入総額_calc'].replace(0, np.nan)) * 100).round(1)

                    # 将来負担比率のカラム作成
                    future_burden_cols = [c for c in df_rank_base.columns if '将来負担比率' in c]
                    if future_burden_cols:
                        df_rank_base['将来負担比率(%)'] = pd.to_numeric(df_rank_base[future_burden_cols[0]], errors='coerce').round(1)

                    # 👈 【追加】経常収支比率のカラム統一作成
                    keijo_cols = [c for c in df_rank_base.columns if '経常収支比率' in c and not any(ex in c for ex in ['人件費', '公債費', '物件費', '扶助費', '繰出金', '特例除外'])]
                    if keijo_cols:
                        df_rank_base['経常収支比率'] = pd.to_numeric(df_rank_base[keijo_cols[0]], errors='coerce').round(1)

                    # 👈 【追加】実質単年度収支のカラム統一作成
                    tannendo_cols = [c for c in df_rank_base.columns if '実質単年度収支' in c]
                    if tannendo_cols:
                        df_rank_base['実質単年度収支'] = pd.to_numeric(df_rank_base[tannendo_cols[0]], errors='coerce').round(1)

                    def calc_score(series, is_higher_better=True):
                        s = pd.to_numeric(series, errors='coerce')
                        valid_mask = s.notna()
                        if valid_mask.sum() == 0:
                            return pd.Series(50.0, index=s.index)
                        ascending = is_higher_better
                        ranks = s.rank(pct=True, ascending=ascending, method='average') * 100
                        return ranks.round(1)

                    score_item_map = {}
                    if '財政力指数' in df_rank_base.columns:
                        df_rank_base['財政力スコア'] = calc_score(df_rank_base['財政力指数'], is_higher_better=True)
                        score_item_map['財政力スコア'] = ('財政力', '財政力指数')
                    if '1人当たり地方税収入(千円)' in df_rank_base.columns:
                        df_rank_base['地域稼ぐ力スコア'] = calc_score(df_rank_base['1人当たり地方税収入(千円)'], is_higher_better=True)
                        score_item_map['地域稼ぐ力スコア'] = ('稼ぐ力(1人当たり地方税)', '1人当たり地方税収入(千円)')
                    if '自主財源比率(%)' in df_rank_base.columns:
                        df_rank_base['自主財源スコア'] = calc_score(df_rank_base['自主財源比率(%)'], is_higher_better=True)
                        score_item_map['自主財源スコア'] = ('自立性(自主財源比率)', '自主財源比率(%)')
                    if '経常収支比率' in df_rank_base.columns:
                        df_rank_base['経常収支スコア'] = calc_score(df_rank_base['経常収支比率'], is_higher_better=False)
                        score_item_map['経常収支スコア'] = ('財政の弾力性', '経常収支比率')
                    if '1人当たり基金(千円)' in df_rank_base.columns:
                        df_rank_base['基金スコア'] = calc_score(df_rank_base['1人当たり基金(千円)'], is_higher_better=True)
                        score_item_map['基金スコア'] = ('貯蓄力(1人当たり基金)', '1人当たり基金(千円)')
                    if '1人当たり実質将来負担(千円)' in df_rank_base.columns:
                        df_rank_base['将来負担スコア'] = calc_score(df_rank_base['1人当たり実質将来負担(千円)'], is_higher_better=False)
                        score_item_map['将来負担スコア'] = ('健全性(将来負担)', '1人当たり実質将来負担(千円)')

                    score_cols = list(score_item_map.keys())
                    if score_cols:
                        df_rank_base['総合ポイント'] = df_rank_base[score_cols].mean(axis=1).round(1)

                    df_rank_filtered = get_comparison_df(df_rank_base)
                    if '総合ポイント' in df_rank_filtered.columns:
                        df_rank_filtered['総合順位'] = df_rank_filtered['総合ポイント'].rank(ascending=False, method='min').astype(int)

                    total_cities_count = len(df_rank_filtered)
                    city_rank_row = df_rank_filtered[df_rank_filtered['団体名'] == selected_city]
                    
                    if not city_rank_row.empty:
                        c_data = city_rank_row.iloc[0]
                        st.markdown(f"##### 📍 {scope_label}における **{selected_city}** の多角的総合評価・スコア要約（{selected_rank_year}年度 / 全{total_cities_count}自治体）")
                        
                        m_col1, m_col2, m_col3, m_col4, m_col5, m_col6 = st.columns(6)
                        with m_col1:
                            if '総合ポイント' in c_data and not pd.isna(c_data['総合ポイント']):
                                st.metric(label="総合ポイント", value=f"{c_data['総合ポイント']:.1f} pt", delta=f"{scope_label} {int(c_data['総合順位'])}位 / {total_cities_count}", delta_color="normal")
                        with m_col2:
                            if '地域稼ぐ力スコア' in c_data and not pd.isna(c_data['地域稼ぐ力スコア']):
                                st.metric(label="1人当たり地方税", value=f"{c_data['地域稼ぐ力スコア']:.1f} pt", delta=f"{c_data['1人当たり地方税収入(千円)']:,.1f}千円" if '1人当たり地方税収入(千円)' in c_data else None)
                        with m_col3:
                            if '自主財源スコア' in c_data and not pd.isna(c_data['自主財源スコア']):
                                st.metric(label="自主財源比率", value=f"{c_data['自主財源スコア']:.1f} pt", delta=f"{c_data['自主財源比率(%)']:.1f}%" if '自主財源比率(%)' in c_data else None)
                        with m_col4:
                            if '経常収支比率' in c_data and not pd.isna(c_data['経常収支比率']):
                                st.metric(label="経常収支(弾力性)", value=f"{c_data['経常収支スコア']:.1f} pt", delta=f"{c_data['経常収支比率']:.1f}%")
                        with m_col5:
                            if '基金スコア' in c_data and not pd.isna(c_data['基金スコア']):
                                st.metric(label="貯蓄力スコア", value=f"{c_data['基金スコア']:.1f} pt", delta=f"{c_data['1人当たり基金(千円)']:,.1f}千円" if '1人当たり基金(千円)' in c_data else None)
                        with m_col6:
                            if '将来負担スコア' in c_data and not pd.isna(c_data['将来負担スコア']):
                                st.metric(label="将来負担スコア", value=f"{c_data['将来負担スコア']:.1f} pt", delta=f"{c_data['1人当たり実質将来負担(千円)']:,.1f}千円" if '1人当たり実質将来負担(千円)' in c_data else None)

                        st.markdown("---")
                        st.markdown(f"#### 🩺 {selected_city} の財政状況診断（強み・課題・総合評価）")

                        avg_tax_pc = df_rank_base['1人当たり地方税収入(千円)'].mean() if '1人当たり地方税収入(千円)' in df_rank_base.columns else np.nan
                        avg_pow_idx = df_rank_base['財政力指数'].mean() if '財政力指数' in df_rank_base.columns else np.nan
                        avg_jishu = df_rank_base['自主財源比率(%)'].mean() if '自主財源比率(%)' in df_rank_base.columns else np.nan
                        avg_keijo = df_rank_base['経常収支比率'].mean() if '経常収支比率' in df_rank_base.columns else np.nan
                        avg_fund_pc = df_rank_base['1人当たり基金(千円)'].mean() if '1人当たり基金(千円)' in df_rank_base.columns else np.nan
                        avg_debt_pc = df_rank_base['1人当たり実質将来負担(千円)'].mean() if '1人当たり実質将来負担(千円)' in df_rank_base.columns else np.nan

                        diag_metric_defs = {
                            '地域稼ぐ力スコア': ('地域の稼ぐ力', c_data.get('1人当たり地方税収入(千円)'), '千円/人', avg_tax_pc, '全国平均以上', '住民1人当たりの地方税収入が高く、自立的な課税基盤を有しています。', '住民1人当たりの地方税収入が伸び悩んでおり、地域産業や税源の強化が求められます。'),
                            '財政力スコア': ('財政力指数', c_data.get('財政力指数'), '', avg_pow_idx, '1.0 以上 (自立ライン)', '基準財政需要に対する収入額の割合が高く、財政基盤が安定しています。', '基準財政需要に対して自前収入が不足しており、地方交付税等への依存度が高い状態です。'),
                            '自主財源スコア': ('自主財源比率', c_data.get('自主財源比率(%)'), '%', avg_jishu, '50.0% 以上', '歳入に占める自主財源の割合が高く、国や県の交付金への依存度が低いです。', '歳入の多くを交付金や国県支出金等の依存財源に頼っており、自律的財政運営に制約があります。'),
                            '経常収支スコア': ('経常収支比率（財政の弾力性）', c_data.get('経常収支比率'), '%', avg_keijo, '80.0% 以下 (適正水準)', '人件費・扶助費等の固定費率が低く抑えられており、柔軟な予算配分が可能です。', '人件費や扶助費・公債費などの固定的な経費（経常経費）が高止まりしており、財政の弾力性が低下しています。'),
                            '基金スコア': ('1人当たり基金（貯蓄力）', c_data.get('1人当たり基金(千円)'), '千円/人', avg_fund_pc, '全国平均以上', '住民1人当たりの貯蓄（基金残高）が豊富で、突発的支出や不況への備えが手厚いです。', '住民1人当たりの基金残高が少なく、財政調整や災害等に対する蓄え（クッション）の強化が必要です。'),
                            '将来負担スコア': ('1人当たり実質将来負担（負債リスク）', c_data.get('1人当たり実質将来負担(千円)'), '千円/人', avg_debt_pc, '全国平均以下', '実質的な将来負債残高が低く抑えられており、将来世代への負担リスクが少ないです。', '地方債や将来負担額が累積しており、将来世代に対する返済負担の軽減策が必要です。')
                        }

                        strengths_list = []
                        weaknesses_list = []

                        for score_col, (m_label, m_val, m_unit, m_avg, m_target, str_desc, weak_desc) in diag_metric_defs.items():
                            sc_val = c_data.get(score_col)
                            if sc_val is not None and not pd.isna(sc_val):
                                fmt_spec = ".2f" if score_col == '財政力スコア' else ",.1f"
                                val_str = f"{m_val:{fmt_spec}} {m_unit}".strip() if isinstance(m_val, (int, float)) and not pd.isna(m_val) else "-"
                                avg_str = f"{m_avg:{fmt_spec}} {m_unit}".strip() if isinstance(m_avg, (int, float)) and not pd.isna(m_avg) else "-"
                                
                                info_meta = f"実数値: **{val_str}** ｜ 全国平均: **{avg_str}** ｜ 目安・適正値: **{m_target}**"

                                if sc_val >= 60:
                                    strengths_list.append(f"**{m_label}**（スコア: {sc_val:.1f} pt）<br>└ {info_meta}<br>└ {str_desc}")
                                elif sc_val < 45:
                                    is_weakness = True
                                    if score_col in ['地域稼ぐ力スコア', '基金スコア', '財政力スコア', '自主財源スコア'] and (m_val is not None and m_avg is not None and m_val >= m_avg):
                                        is_weakness = False
                                    elif score_col in ['経常収支スコア', '将来負担スコア'] and (m_val is not None and m_avg is not None and m_val <= m_avg):
                                        is_weakness = False
                                        
                                    if is_weakness:
                                        weaknesses_list.append(f"**{m_label}**（スコア: {sc_val:.1f} pt）<br>└ {info_meta}<br>└ {weak_desc}")

                        tot_score_val = c_data.get('総合ポイント', 50.0)
                        tot_rank_val = int(c_data['総合順位']) if '総合順位' in c_data else 0

                        if tot_score_val >= 70:
                            st.success(f"**【総合診断】 ⭐ 超健全・先進型（総合スコア: {tot_score_val:.1f} pt / {scope_label} {tot_rank_val}位）**\n\n"
                                       f"**{selected_city}** は上位に位置する極めて優秀な財政状態です。高い稼ぐ力と十分な貯蓄、低い将来負担リスクを備えた強固な財政基盤を誇ります。")
                        elif tot_score_val >= 55:
                            st.info(f"**【総合診断】 🟢 健全・安定型（総合スコア: {tot_score_val:.1f} pt / {scope_label} {tot_rank_val}位）**\n\n"
                                    f"**{selected_city}** は主要な指標のバランスが良く、安定した財政運営が行われている良好な水準です。")
                        elif tot_score_val >= 45:
                            st.warning(f"**【総合診断】 🟡 標準・課題点在型（総合スコア: {tot_score_val:.1f} pt / {scope_label} {tot_rank_val}位）**\n\n"
                                       f"**{selected_city}** はほぼ標準的な財政水準です。全体としては一定の財政規模を維持していますが、強みと改善が必要な課題が混在しています。")
                        else:
                            st.error(f"**【総合診断】 🔴 警戒・構造改善要求型（総合スコア: {tot_score_val:.1f} pt / {scope_label} {tot_rank_val}位）**\n\n"
                                     f"**{selected_city}** は総合スコアが相対的に低い状態にあります。自前の課税基盤の強化や固定費の削減など、構造的な財政改革が必要です。")

                        diag_col1, diag_col2 = st.columns(2)
                        with diag_col1:
                            st.markdown("##### 💪 **自治体の強み・優れている点（スコア60pt以上）**")
                            if strengths_list:
                                for s in strengths_list:
                                    st.markdown(f"・ {s}", unsafe_allow_html=True)
                            else:
                                st.caption("※ スコア60pt以上の特筆すべき項目はありません（ほぼ全指標が標準水準です）。")

                        with diag_col2:
                            st.markdown("##### ⚠️ **課題・改善が望まれる点（スコア45pt未満）**")
                            if weaknesses_list:
                                for w in weaknesses_list:
                                    st.markdown(f"・ {w}", unsafe_allow_html=True)
                            else:
                                st.caption("※ スコア45pt未満の懸念項目はありません（健全なレベルに制御されています）。")

                        st.markdown("---")
                        subtab_rank1, subtab_rank2 = st.tabs(["🌐 総合ポイントランキング & レーダー", "🥇 指標別 TOP/WORST100 ランキング"])

                        with subtab_rank1:
                            col_chart_left, col_chart_right = st.columns([3, 2])
                            with col_chart_left:
                                df_rank_sorted = df_rank_filtered.dropna(subset=['総合ポイント']).sort_values('総合ポイント', ascending=True).copy()
                                df_rank_sorted['表示色'] = df_rank_sorted['団体名'].apply(lambda x: '選択中の自治体' if x == selected_city else 'その他自治体')
                                df_rank_sorted['順位表示名'] = df_rank_sorted['総合順位'].astype(str) + "位 " + df_rank_sorted['団体名'] + "（" + df_rank_sorted['都道府県'] + "）"

                                fig_rank = px.bar(
                                    df_rank_sorted, x='総合ポイント', y='順位表示名', orientation='h', color='表示色', text='総合ポイント',
                                    title=f"{scope_label}（{selected_rank_year}年度）真の稼ぐ力・財政健全化 総合ポイントランキング",
                                    color_discrete_map={'選択中の自治体': '#FF4B4B', 'その他自治体': '#1F77B4'},
                                    custom_data=['都道府県', '団体名', '総合順位']
                                )
                                fig_rank.update_traces(texttemplate='%{text:.1f} pt', textposition='outside', hovertemplate="順位: %{customdata[2]}位<br>都道府県: %{customdata[0]}<br><b>自治体: %{customdata[1]}</b><br>総合ポイント: %{x:.1f} pt<extra></extra>")
                                fig_rank.update_layout(xaxis_title="総合ポイント (pt)", yaxis_title="順位・自治体名", showlegend=True, height=max(400, len(df_rank_sorted)*25))
                                st.plotly_chart(fig_rank, use_container_width=True, key="overview_rank_bar")
                            
                            with col_chart_right:
                                radar_labels = [score_item_map[sc][0] for sc in score_cols if sc in c_data]
                                radar_vals = [c_data[sc] for sc in score_cols if sc in c_data]
                                if radar_vals:
                                    fig_radar = go.Figure()
                                    fig_radar.add_trace(go.Scatterpolar(r=radar_vals + [radar_vals[0]], theta=radar_labels + [radar_labels[0]], fill='toself', name=selected_city, line_color='#FF4B4B'))
                                    fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), showlegend=False, title=f"{selected_city} 各分野スコアバランス")
                                    st.plotly_chart(fig_radar, use_container_width=True, key="overview_radar")

                            disp_cols = ['総合順位', '都道府県', '団体名', '総合ポイント', '1人当たり地方税収入(千円)', '自主財源比率(%)', '経常収支比率', '財政力指数', '1人当たり基金(千円)', '1人当たり実質将来負担(千円)']
                            disp_cols = [c for c in disp_cols if c in df_rank_filtered.columns]
                            st.dataframe(df_rank_filtered.sort_values('総合順位')[disp_cols], use_container_width=True)

                        with subtab_rank2:
                            st.markdown("##### 🥇 指標別 自治体ランキング（全国・同一県内・同一都市区分）")
                            
                            ranking_metrics_map = {
                                '財政力指数': ('財政力指数', True, ''),
                                '経常収支比率': ('経常収支比率（財政の弾力性）', False, '%'),  # 👈 表示ラベルを統一・分かりやすく修正
                                '将来負担比率(%)': ('将来負担比率', False, '%'),
                                '1人当たり地方税収入(千円)': ('1人当たり地方税収入（地域の稼ぐ力）', True, '千円'),
                                '1人当たり基金(千円)': ('1人当たり基金残高（自治体の貯蓄力）', True, '千円'),
                                '1人当たり実質将来負担(千円)': ('1人当たり実質将来負担残高（実質借金）', False, '千円'),
                                '自主財源比率(%)': ('自主財源比率（自力調達の割合）', True, '%'),
                                '実質単年度収支': ('実質単年度収支（純損益）', True, '千円'),
                            }
                            
                            available_metrics = {k: v for k, v in ranking_metrics_map.items() if k in df_rank_base.columns}
                            
                            r_col1, r_col2, r_col3, r_col4 = st.columns([3, 2, 2, 2])
                            with r_col1:
                                selected_m_key = st.selectbox(
                                    "ランキング指標を選択", 
                                    list(available_metrics.keys()), 
                                    format_func=lambda x: available_metrics[x][0],
                                    key="m_rank_key_select"
                                )
                            with r_col2:
                                scope_opt = st.radio("比較範囲", ["全国", f"同一県内（{selected_pref}）", f"同一都市区分（{selected_type}）"], horizontal=False, key="m_rank_scope")
                            with r_col3:
                                rank_order_mode = st.radio("順位順", ["ベスト (優秀順)", "ワースト (課題順)"], horizontal=False, key="m_rank_order_mode")
                            with r_col4:
                                top_n = st.selectbox("表示件数", [10, 30, 50, 100, "全件"], index=3, key="m_rank_top_n")

                            if "同一県内" in scope_opt and selected_pref != "全国":
                                df_target_rank = df_rank_base[df_rank_base['都道府県'] == selected_pref].copy()
                            elif "同一都市区分" in scope_opt and selected_type != "すべて":
                                df_target_rank = df_rank_base[df_rank_base['都市区分'] == selected_type].copy()
                            else:
                                df_target_rank = df_rank_base.copy()

                            metric_info = available_metrics[selected_m_key]
                            is_higher_better = metric_info[1]
                            unit_str = metric_info[2]

                            if "ベスト" in rank_order_mode:
                                ascending = not is_higher_better
                            else:
                                ascending = is_higher_better

                            df_m_sorted = df_target_rank.dropna(subset=[selected_m_key]).sort_values(selected_m_key, ascending=ascending).copy()
                            
                            rank_asc = not is_higher_better
                            df_m_sorted['順位'] = df_m_sorted[selected_m_key].rank(ascending=rank_asc, method='min').astype(int)

                            if top_n != "全件":
                                df_plot_rank = df_m_sorted.head(int(top_n)).copy()
                            else:
                                df_plot_rank = df_m_sorted.copy()

                            df_plot_rank['表示色'] = df_plot_rank['団体名'].apply(lambda x: '選択中の自治体' if x == selected_city else 'その他自治体')
                            df_plot_rank['順位表示名'] = df_plot_rank['順位'].astype(str) + "位 " + df_plot_rank['団体名'] + "（" + df_plot_rank['都道府県'] + "）"

                            plot_order_df = df_plot_rank.sort_values(selected_m_key, ascending=not ascending).copy()

                            fig_m_rank = px.bar(
                                plot_order_df, 
                                x=selected_m_key, y='順位表示名', orientation='h', color='表示色',
                                text=selected_m_key,
                                title=f"{scope_opt}（{selected_rank_year}年度）{metric_info[0]} ランキング（{rank_order_mode}）",
                                color_discrete_map={'選択中の自治体': '#FF4B4B', 'その他自治体': '#1F77B4'},
                                custom_data=['都道府県', '団体名', '順位']
                            )
                            
                            fmt_text = '%{text:.2f}' if selected_m_key == '財政力指数' else f'%{{text:,.1f}} {unit_str}'
                            fig_m_rank.update_traces(
                                texttemplate=fmt_text, 
                                textposition='outside', 
                                hovertemplate=f"順位: %{{customdata[2]}}位<br>都道府県: %{{customdata[0]}}<br><b>自治体: %{{customdata[1]}}</b><br>数値: %{{x:,.2f}} {unit_str}<extra></extra>"
                            )
                            fig_m_rank.update_layout(
                                xaxis_title=f"{metric_info[0]}（{unit_str}）" if unit_str else metric_info[0], 
                                yaxis_title="順位・自治体名", 
                                height=max(400, len(df_plot_rank)*25)
                            )
                            st.plotly_chart(fig_m_rank, use_container_width=True, key="metric_rank_bar")

                            st.markdown(f"##### 📋 {scope_opt} {metric_info[0]} データテーブル（{len(df_m_sorted)}自治体中）")
                            disp_m_cols = ['順位', '都道府県', '団体名', selected_m_key]
                            if '人口_num' in df_m_sorted.columns:
                                disp_m_cols.append('人口_num')
                            
                            st.dataframe(df_m_sorted[disp_m_cols], use_container_width=True)

        # --- Tab 2: 財政力 ---
        with tab2:
            st.markdown("#### 💪 財政力・財源基盤の推移と要因分析")
            subtab_pow1, subtab_pow2 = st.tabs(["📈 単体推移（需要額 vs 収入額 ギャップ分析）", "📊 財政力指数の自治体間比較"])
            
            with subtab_pow1:
                cols_dem_inc = get_cols_by_keywords(['基準財政需要額', '基準財政収入額', '標準財政規模'])
                cols_pow = get_cols_by_keywords(['財政力指数'])
                if cols_dem_inc or cols_pow:
                    fig_d = make_subplots(specs=[[{"secondary_y": True}]])
                    for col in cols_dem_inc:
                        fig_d.add_trace(go.Scatter(x=df_ov_city['年度'], y=df_ov_city[col], mode='lines+markers', name=clean_col_label(col)), secondary_y=False)
                    for col in cols_pow:
                        fig_d.add_trace(go.Scatter(x=df_ov_city['年度'], y=df_ov_city[col], mode='lines+markers', name=clean_col_label(col), line=dict(dash='dash', color='orange')), secondary_y=True)
                    fig_d.add_hline(y=1.0, line_dash="dash", line_color="red", secondary_y=True, annotation_text="自立判定ライン (1.0)", annotation_position="bottom right")
                    fig_d.update_layout(title=f"{selected_city} 標準財政規模・需要額・収入額 vs 財政力指数", xaxis_title="年度")
                    fig_d.update_yaxes(title_text="金額（千円）", secondary_y=False, tickformat=",")
                    fig_d.update_yaxes(title_text="財政力指数", secondary_y=True, tickformat=".2f")
                    st.plotly_chart(fig_d, use_container_width=True, key="pow_trend_chart")

                st.markdown("---")
                st.markdown("##### 🔍 財政力指数の構造要因分析（自前収入の自立充足率）")

                dem_col = next((c for c in df_ov_city.columns if '基準財政需要額' in c), None)
                inc_col = next((c for c in df_ov_city.columns if '基準財政収入額' in c), None)

                if dem_col and inc_col and not df_ov_city.empty:
                    latest_ov_row = df_ov_city.sort_values('年度').iloc[-1]
                    dem_val = latest_ov_row[dem_col]
                    inc_val = latest_ov_row[inc_col]
                    gap_val = dem_val - inc_val
                    self_ratio = (inc_val / dem_val * 100) if dem_val > 0 else 0

                    c_pow1, c_pow2, c_pow3 = st.columns(3)
                    with c_pow1:
                        st.metric("基準財政需要額 (標準コスト)", f"{dem_val:,.0f} 千円")
                    with c_pow2:
                        st.metric("基準財政収入額 (標準税収)", f"{inc_val:,.0f} 千円", delta=f"自立充足率: {self_ratio:.1f}%")
                    with c_pow3:
                        st.metric("財源不足額 (地方交付税補填分)", f"{gap_val:,.0f} 千円", delta="自前財源不足" if gap_val > 0 else "財源超過", delta_color="inverse")

                    st.caption(f"""
                    💡 **財政力指数の構造分析**:
                    * 標準的行政コスト（需要額: {dem_val:,.0f}千円）に対して、自前の標準税収入等（収入額: {inc_val:,.0f}千円）は **{self_ratio:.1f}%** の充足にとどまっています。
                    * 不足する **{gap_val:,.0f}千円** は地方交付税で補填されているため、財政力指数が低水準となる構造的な原因となっています。
                    """)

            with subtab_pow2:
                st.markdown("##### 🏛️ 自治体別 財政力指数ランキング・比較")
                df_ov_comp_pow = get_comparison_df(df_overview)
                avail_pow_years = sorted(df_ov_comp_pow['年度'].astype(str).unique()) if not df_ov_comp_pow.empty else []
                if avail_pow_years:
                    selected_pow_comp_year = st.selectbox("比較年度を選択", avail_pow_years, index=len(avail_pow_years)-1, key="pow_comp_year_select")
                    df_pow_y = df_ov_comp_pow[df_ov_comp_pow['年度'].astype(str) == str(selected_pow_comp_year)].copy()
                    
                    idx_cols = [c for c in df_pow_y.columns if '財政力指数' in c]
                    if idx_cols:
                        pow_col = idx_cols[0]
                        df_pow_sorted = df_pow_y.dropna(subset=[pow_col]).sort_values(pow_col, ascending=False).copy()
                        df_pow_sorted['表示色'] = df_pow_sorted['団体名'].apply(lambda x: '選択中の自治体' if x == selected_city else 'その他自治体')

                        fig_pow_bar = px.bar(
                            df_pow_sorted, x='団体名', y=pow_col, color='表示色', text=pow_col,
                            title=f"{scope_label}（{selected_pow_comp_year}年度）財政力指数 自治体間比較（高い順）",
                            color_discrete_map={'選択中の自治体': '#FF4B4B', 'その他自治体': '#1F77B4'},
                            custom_data=['都道府県']
                        )
                        fig_pow_bar.add_hline(y=1.0, line_dash="dash", line_color="red", annotation_text="財政自立ライン (1.0)", annotation_position="top right")
                        fig_pow_bar.update_traces(texttemplate='%{text:.2f}', textposition='outside', hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>財政力指数: %{y:.2f}<extra></extra>")
                        fig_pow_bar.update_layout(xaxis_title="自治体名", yaxis_title="財政力指数")
                        st.plotly_chart(fig_pow_bar, use_container_width=True, key="tab2_pow_comp_chart")

                        disp_pow_cols = ['都道府県', '団体名', pow_col]
                        pop_c = get_population_col(df_pow_sorted)
                        if pop_c:
                            disp_pow_cols.append(pop_c)
                        st.dataframe(df_pow_sorted[disp_pow_cols], use_container_width=True)

        # --- Tab 3: 効率性 ---
        with tab3:
            st.markdown("#### ⚙️ 財政効率性・収支構造の推移と要因分析")
            subtab_eff1, subtab_eff2 = st.tabs(["📊 経常収支比率の要因分析（歳入一般財源 vs 固定費構造）", "💰 単年度損益・収支バランス"])
            
            with subtab_eff1:
                cols_keijo = get_cols_by_keywords(['経常収支比率'])
                if cols_keijo:
                    fig_k = px.line(df_ov_city, x='年度', y=cols_keijo, markers=True, title=f"{selected_city} 経常収支比率の推移")
                    fig_k.add_hline(y=80.0, line_dash="dash", line_color="green", annotation_text="適正水準 (80%)", annotation_position="bottom right")
                    fig_k.add_hline(y=90.0, line_dash="dash", line_color="red", annotation_text="財政硬直化警戒ライン (90%)", annotation_position="top right")
                    st.plotly_chart(fig_k, use_container_width=True, key="eff_keijo_chart")

                st.markdown("---")
                st.markdown("##### 🔍 経常収支比率の要因分析（歳入一般財源 vs 歳出固定費構造）")

                exp_source_df = df_exp_city if (not df_exp_city.empty) else df_ov_city
                rev_source_df = df_rev_city if (not df_rev_city.empty) else df_ov_city

                exp_tab, rev_tab, comb_tab = st.tabs(["🔴 歳出側（固定費・経常支出の内訳）", "🔵 歳入側（経常一般財源の構成）", "⚖️ 歳入・歳出 構造バランス"])

                with exp_tab:
                    found_exp_items = {}
                    is_percent_data = False
                    latest_exp_year = "直近"

                    if not exp_source_df.empty:
                        latest_exp_row = exp_source_df.sort_values('年度').iloc[-1]
                        latest_exp_year = latest_exp_row['年度']

                        exp_keywords = {
                            '人件費': ['人件費'], '扶助費': ['扶助費'], '公債費': ['公債費'],
                            '物件費': ['物件費'], '繰出金': ['繰出金'], '補助費等': ['補助費'], '維持補修費': ['維持補修']
                        }

                        for label, kws in exp_keywords.items():
                            matched_cols = [
                                c for c in exp_source_df.columns 
                                if any(kw in c for kw in kws) 
                                and not any(ex in c for ex in ['1人当たり', '%', 'パーセント', '比率', '割合'])
                            ]
                            if matched_cols:
                                val = pd.to_numeric(latest_exp_row[matched_cols[0]], errors='coerce')
                                if pd.notna(val) and val > 0:
                                    found_exp_items[label] = val

                        if not found_exp_items and not df_ov_city.empty:
                            latest_ov_row = df_ov_city.sort_values('年度').iloc[-1]
                            pct_cols = [
                                c for c in df_ov_city.columns 
                                if '経常収支比率' in c 
                                and any(kw in c for kw in ['人件費', '公債費', '物件費', '扶助費', '繰出金']) 
                                and '特例除外' not in c
                            ]
                            if pct_cols:
                                is_percent_data = True
                                for c in pct_cols:
                                    val = pd.to_numeric(latest_ov_row[c], errors='coerce')
                                    if pd.notna(val) and val > 0:
                                        label_name = clean_col_label(c).replace('経常収支比率_', '').replace('_パーセント', '')
                                        found_exp_items[label_name] = val

                    if found_exp_items:
                        tot_exp_val = sum(found_exp_items.values())
                        unit_str = "%" if is_percent_data else "千円"
                        val_col_name = f"数値({unit_str})"

                        df_exp_f = pd.DataFrame([
                            {'項目名': k, val_col_name: v, '構成比(%)': round(v / tot_exp_val * 100, 1) if not is_percent_data else round(v, 1)}
                            for k, v in found_exp_items.items()
                        ]).sort_values(val_col_name, ascending=False)

                        top_f = df_exp_f.iloc[0]
                        gimu_items = ['人件費', '扶助費', '公債費']
                        gimu_val = sum(found_exp_items.get(k, 0) for k in gimu_items if k in found_exp_items)
                        gimu_ratio = round(gimu_val / tot_exp_val * 100, 1) if (tot_exp_val > 0 and not is_percent_data) else round(gimu_val, 1)
                        val_fmt_top = f"{top_f[val_col_name]:,.1f}%" if is_percent_data else f"{top_f[val_col_name]:,.0f}千円"

                        st.info(f"""
                        💡 **{latest_exp_year}年度 歳出（固定費）の要因診断**
                        * 経常的な固定費の中で最も大きな割合を占めているのは **「{top_f['項目名']}」**（{val_fmt_top}）です。
                        * 削減が困難な**義務的経費（人件費・扶助費・公債費）**の合計割合は **{gimu_ratio}%** を占めています。
                        """)

                        c_f1, c_f2 = st.columns([3, 2])
                        with c_f1:
                            fig_exp_bar = px.bar(
                                df_exp_f, x=val_col_name, y='項目名', orientation='h',
                                text=val_col_name if is_percent_data else '構成比(%)',
                                color=val_col_name if is_percent_data else '構成比(%)',
                                color_continuous_scale='Reds',
                                title=f"{selected_city}（{latest_exp_year}年度）経常的支出（固定費）の内訳"
                            )
                            fig_exp_bar.update_traces(texttemplate='%{text:.1f}%' if is_percent_data else '%{text:.1f}%', textposition='outside')
                            fig_exp_bar.update_layout(xaxis_title=val_col_name, yaxis_title="支出項目", height=320)
                            st.plotly_chart(fig_exp_bar, use_container_width=True, key="keijo_exp_factor_bar")

                        with c_f2:
                            st.markdown("##### 📋 経常支出 構成内訳テーブル")
                            st.dataframe(df_exp_f, use_container_width=True, hide_index=True)

                with rev_tab:
                    found_rev_items = {}
                    latest_rev_year = "直近"

                    if not rev_source_df.empty:
                        latest_rev_row = rev_source_df.sort_values('年度').iloc[-1]
                        latest_rev_year = latest_rev_row['年度']

                        rev_keywords = {
                            '地方税': ['地方税'], '地方交付税': ['地方交付税'],
                            '地方譲与税': ['地方譲与税'], '都道府県税交付金': ['都道府県税交付金'],
                            'その他交付金': ['地方特例交付金', '交通安全']
                        }

                        for label, kws in rev_keywords.items():
                            matched_cols = [
                                c for c in rev_source_df.columns 
                                if any(kw in c for kw in kws) 
                                and not any(ex in c for ex in ['1人当たり', '%', 'パーセント', '比率', '割合', '国庫', '都道府県支出金'])
                            ]
                            if matched_cols:
                                val = pd.to_numeric(latest_rev_row[matched_cols[0]], errors='coerce')
                                if pd.notna(val) and val > 0:
                                    found_rev_items[label] = val

                    if found_rev_items:
                        tot_rev_val = sum(found_rev_items.values())
                        df_rev_f = pd.DataFrame([
                            {'項目名': k, '金額(千円)': v, '構成比(%)': round(v / tot_rev_val * 100, 1)}
                            for k, v in found_rev_items.items()
                        ]).sort_values('金額(千円)', ascending=False)

                        tax_val = found_rev_items.get('地方税', 0)
                        tax_ratio = round(tax_val / tot_rev_val * 100, 1) if tot_rev_val > 0 else 0
                        alloc_val = found_rev_items.get('地方交付税', 0)
                        alloc_ratio = round(alloc_val / tot_rev_val * 100, 1) if tot_rev_val > 0 else 0

                        st.info(f"""
                        💡 **{latest_rev_year}年度 歳入（経常一般財源）の要因診断**
                        * 固定費を賄う一般財源のうち、自前税収入である**「地方税」**の比率は **{tax_ratio}%**（{tax_val:,.0f}千円）です。
                        * 国からの補填である**「地方交付税」**への依存比率は **{alloc_ratio}%**（{alloc_val:,.0f}千円）です。
                        """)

                        c_r1, c_r2 = st.columns([3, 2])
                        with c_r1:
                            fig_rev_bar = px.bar(
                                df_rev_f, x='金額(千円)', y='項目名', orientation='h',
                                text='構成比(%)', color='構成比(%)', color_continuous_scale='Blues',
                                title=f"{selected_city}（{latest_rev_year}年度）経常一般財源（分母）の内訳"
                            )
                            fig_rev_bar.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                            fig_rev_bar.update_layout(xaxis_title="金額（千円）", yaxis_title="歳入項目", height=320)
                            st.plotly_chart(fig_rev_bar, use_container_width=True, key="keijo_rev_factor_bar")

                        with c_r2:
                            st.markdown("##### 📋 経常一般財源 構成比テーブル")
                            st.dataframe(df_rev_f, use_container_width=True, hide_index=True)

                with comb_tab:
                    st.markdown("##### ⚖️ 経常収支比率の計算構造バランス（分母 vs 分子）")

                    # 1. 経常収支比率（最新値）を取得
                    keijo_ratio = None
                    if not df_ov_city.empty:
                        keijo_cols = [c for c in df_ov_city.columns if '経常収支比率' in c and not any(ex in c for ex in ['人件費', '公債費', '物件費', '扶助費', '繰出金', '特例除外'])]
                        if keijo_cols:
                            latest_ov = df_ov_city.sort_values('年度').iloc[-1]
                            val = pd.to_numeric(latest_ov[keijo_cols[0]], errors='coerce')
                            if pd.notna(val):
                                keijo_ratio = val

                    tot_rev_gen = sum(found_rev_items.values()) if found_rev_items else 0
                    calc_exp_gen = (tot_rev_gen * (keijo_ratio / 100.0)) if (tot_rev_gen > 0 and keijo_ratio is not None) else None
                    tot_exp_gross = sum(found_exp_items.values()) if (found_exp_items and not is_percent_data) else 0
                    specific_source = (tot_exp_gross - calc_exp_gen) if (tot_exp_gross > 0 and calc_exp_gen is not None) else 0

                    # メトリクス表示
                    m_col1, m_col2, m_col3 = st.columns(3)
                    with m_col1:
                        if tot_rev_gen > 0:
                            st.metric("経常一般財源（分母）", f"{tot_rev_gen:,.0f} 千円")
                    with m_col2:
                        if calc_exp_gen is not None:
                            st.metric("充当一般財源（実質分子）", f"{calc_exp_gen:,.0f} 千円", delta=f"経常収支比率: {keijo_ratio:.1f}%", delta_color="normal")
                    with m_col3:
                        if tot_exp_gross > 0 and calc_exp_gen is not None:
                            st.metric("うち特定財源（国県支出金等）", f"{max(0, specific_source):,.0f} 千円", delta=f"事業費総額: {tot_exp_gross:,.0f}千円", delta_color="off")
                    
                    st.markdown("---")
                    st.markdown("##### 📈 充当一般財源（実質分子）の内訳 & 経常収支比率押し上げ要因分析（分離表示）")

                    # 1. 人件費・公債費の公表値を取得
                    pct_items = {}
                    if not df_ov_city.empty:
                        latest_ov = df_ov_city.sort_values('年度').iloc[-1]
                        if '経常収支比率_人件費_パーセント' in latest_ov and pd.notna(latest_ov['経常収支比率_人件費_パーセント']):
                            pct_items['人件費'] = float(latest_ov['経常収支比率_人件費_パーセント'])
                        if '経常収支比率_公債費_パーセント' in latest_ov and pd.notna(latest_ov['経常収支比率_公債費_パーセント']):
                            pct_items['公債費'] = float(latest_ov['経常収支比率_公債費_パーセント'])

                    # 2. 性質別歳出の事業費比率に基づき残りを「扶助費」「物件費」「補助費等」等に推計分解
                    known_sum = sum(pct_items.values())
                    remaining_pct = (keijo_ratio - known_sum) if (keijo_ratio and keijo_ratio > known_sum) else 0

                    if remaining_pct > 0 and not df_exp_city.empty:
                        latest_exp = df_exp_city.sort_values('年度').iloc[-1]
                        
                        sub_exp_map = {
                            '扶助費': '扶助費_合計',
                            '補助費等': '補助費等_合計',
                            '物件費': '物件費_合計',
                            '繰出金': '繰出金_合計',
                            '維持補修費': '維持補修費_合計'
                        }
                        
                        sub_vals = {}
                        for label, col_name in sub_exp_map.items():
                            if col_name in latest_exp and pd.notna(latest_exp[col_name]):
                                sub_vals[label] = float(latest_exp[col_name])

                        sub_tot = sum(sub_vals.values())
                        if sub_tot > 0:
                            for label, val in sub_vals.items():
                                # 残りの%ptを事業費の構成比で按分推計
                                pct_items[f"{label}(推計)"] = round(remaining_pct * (val / sub_tot), 1)

                    if pct_items and tot_rev_gen > 0:
                        df_factor = pd.DataFrame([
                            {
                                '経費項目': k,
                                '押し上げ比率(%pt)': v,
                                '充当一般財源(千円)': round(tot_rev_gen * (v / 100.0)),
                                '充当一般財源(億円)': round(tot_rev_gen * (v / 100.0) / 100000, 1)
                            }
                            for k, v in pct_items.items()
                        ]).sort_values('押し上げ比率(%pt)', ascending=False)

                        f_col1, f_col2 = st.columns([3, 2])
                        with f_col1:
                            fig_factor = px.bar(
                                df_factor, x='押し上げ比率(%pt)', y='経費項目', orientation='h',
                                text='押し上げ比率(%pt)', color='押し上げ比率(%pt)', color_continuous_scale='Reds',
                                title=f"{selected_city} 経常収支比率（{keijo_ratio:.1f}%）の経費別押し上げ寄与度"
                            )
                            fig_factor.update_traces(texttemplate='%{text:.1f} %pt', textposition='outside')
                            fig_factor.update_layout(xaxis_title="経常収支比率への押し上げ寄与度 (%pt)", yaxis_title="経費項目", height=380)
                            st.plotly_chart(fig_factor, use_container_width=True, key="keijo_factor_push_bar")

                        with f_col2:
                            st.markdown("##### 📋 充当一般財源（自前負担）の推定内訳")
                            st.dataframe(df_factor[['経費項目', '押し上げ比率(%pt)', '充当一般財源(億円)']], use_container_width=True, hide_index=True)

                        st.caption("※ 扶助費・物件費・補助費等・繰出金等の値は、人件費・公債費以外の一般財源充当分を性質別歳出の事業費比率に基づき推計・分解した値です。")

                    # =========================================================
                    # 🌐 全国平均・県内平均との比較分析（%pt寄与度 & 1人当たり歳出額・歳入額）
                    # =========================================================
                    st.markdown("---")
                    st.markdown("##### 🌐 全国平均・県内平均との比較分析")

                    # 分析対象年度の特定
                    if not df_ov_city.empty and '年度' in df_ov_city.columns:
                        latest_year_str = str(df_ov_city.sort_values('年度').iloc[-1]['年度'])
                        
                        # 対象年度の全体データフィルタリング
                        df_ov_y_all = df_overview[df_overview['年度'].astype(str) == latest_year_str].copy() if not df_overview.empty else pd.DataFrame()
                        df_exp_y_all = df_exp_nature[df_exp_nature['年度'].astype(str) == latest_year_str].copy() if not df_exp_nature.empty else pd.DataFrame()
                        df_rev_y_all = df_revenue[df_revenue['年度'].astype(str) == latest_year_str].copy() if not df_revenue.empty else pd.DataFrame()

                        if not df_ov_y_all.empty and not df_exp_y_all.empty:
                            # データの結合
                            merge_keys = ['都道府県', '団体名', '年度'] if ('都道府県' in df_ov_y_all.columns and '都道府県' in df_exp_y_all.columns) else ['団体名', '年度']
                            df_comp_all = pd.merge(df_ov_y_all, df_exp_y_all, on=merge_keys, how='inner', suffixes=('', '_exp'))
                            if not df_rev_y_all.empty:
                                df_comp_all = pd.merge(df_comp_all, df_rev_y_all, on=merge_keys, how='left', suffixes=('', '_rev'))

                            # 1. 押し上げ寄与度（%pt）の算出ヘルパー関数
                            def calc_factor_push_series(df_target):
                                sub_map = {
                                    '扶助費': '扶助費_合計',
                                    '補助費等': '補助費等_合計',
                                    '物件費': '物件費_合計',
                                    '繰出金': '繰出金_合計',
                                    '維持補修費': '維持補修費_合計'
                                }
                                records = []
                                for _, row in df_target.iterrows():
                                    keijo = pd.to_numeric(row.get('経常収支比率_パーセント'), errors='coerce')
                                    jin = pd.to_numeric(row.get('経常収支比率_人件費_パーセント'), errors='coerce') if pd.notna(row.get('経常収支比率_人件費_パーセント')) else 0
                                    ko = pd.to_numeric(row.get('経常収支比率_公債費_パーセント'), errors='coerce') if pd.notna(row.get('経常収支比率_公債費_パーセント')) else 0
                                    
                                    if pd.isna(keijo):
                                        continue
                                    
                                    rem = max(0, keijo - jin - ko)
                                    sub_vals = {lbl: float(row[col]) for lbl, col in sub_map.items() if col in row and pd.notna(row[col])}
                                    sub_tot = sum(sub_vals.values())
                                    
                                    rec = {'人件費': jin, '公債費': ko, '経常収支比率': keijo}
                                    if sub_tot > 0:
                                        for lbl, val in sub_vals.items():
                                            rec[f"{lbl}(推計)"] = rem * (val / sub_tot)
                                    records.append(rec)
                                return pd.DataFrame(records).mean() if records else pd.Series()

                            # 2. 人口カラムの検出と1人当たり歳出額（千円/人）の算出ヘルパー関数
                            pop_col_name = get_population_col(df_ov_y_all)
                            def calc_per_capita_series(df_target):
                                if not pop_col_name or pop_col_name not in df_target.columns:
                                    return pd.Series()
                                tot_pop = pd.to_numeric(df_target[pop_col_name], errors='coerce').sum()
                                if tot_pop <= 0:
                                    return pd.Series()
                                
                                exp_cols_map = {
                                    '扶助費': '扶助費_合計', '人件費': '人件費_合計', '補助費等': '補助費等_合計',
                                    '物件費': '物件費_合計', '公債費': '公債費_合計', '繰出金': '繰出金_合計', '維持補修費': '維持補修費_合計'
                                }
                                res = {}
                                for lbl, col in exp_cols_map.items():
                                    if col in df_target.columns:
                                        tot_val = pd.to_numeric(df_target[col], errors='coerce').sum()
                                        res[lbl] = round(tot_val / tot_pop, 1)
                                return pd.Series(res)

                            # 3. 1人当たり歳入額（千円/人）の算出ヘルパー関数（👈 追加）
                            def calc_rev_per_capita_series(df_target):
                                if not pop_col_name or pop_col_name not in df_target.columns:
                                    return pd.Series()
                                tot_pop = pd.to_numeric(df_target[pop_col_name], errors='coerce').sum()
                                if tot_pop <= 0:
                                    return pd.Series()
                                
                                rev_cols_map = {
                                    '地方税': '地方税_合計', '地方交付税': '地方交付税_合計', '国庫支出金': '国庫支出金_合計',
                                    '都道府県支出金': '都道府県支出金_合計', '地方債': '地方債_合計', '繰入金': '繰入金_合計', '諸収入': '諸収入_合計'
                                }
                                res = {}
                                for lbl, col in rev_cols_map.items():
                                    if col in df_target.columns:
                                        tot_val = pd.to_numeric(df_target[col], errors='coerce').sum()
                                        res[lbl] = round(tot_val / tot_pop, 1)
                                return pd.Series(res)

                            # グループごとの抽出
                            df_target_city = df_comp_all[df_comp_all['団体名'].astype(str).str.contains(str(selected_city).strip(), regex=False)]
                            df_target_pref = df_comp_all[df_comp_all['都道府県'].astype(str) == str(selected_pref).strip()] if selected_pref != "全国" else df_comp_all
                            df_target_japan = df_comp_all

                            # 各指標の算出
                            s_push_city = calc_factor_push_series(df_target_city)
                            s_push_pref = calc_factor_push_series(df_target_pref)
                            s_push_japan = calc_factor_push_series(df_target_japan)

                            s_pc_city = calc_per_capita_series(df_target_city)
                            s_pc_pref = calc_per_capita_series(df_target_pref)
                            s_pc_japan = calc_per_capita_series(df_target_japan)

                            s_rev_pc_city = calc_rev_per_capita_series(df_target_city)
                            s_rev_pc_pref = calc_rev_per_capita_series(df_target_pref)
                            s_rev_pc_japan = calc_rev_per_capita_series(df_target_japan)

                            # サブタブの作成（👈 歳入額比較タブを追加）
                            tab_comp_push, tab_comp_pc, tab_comp_rev_pc = st.tabs([
                                "📊 押し上げ寄与度(%pt)の比較", 
                                "👥 1人当たり歳出額(千円/人)の比較", 
                                "💰 1人当たり歳入額(千円/人)の比較"
                            ])

                            # --- Tab 1: 押し上げ寄与度(%pt)の比較 ---
                            with tab_comp_push:
                                if not s_push_city.empty:
                                    items_order = ['経常収支比率', '人件費', '扶助費(推計)', '公債費', '補助費等(推計)', '物件費(推計)', '繰出金(推計)', '維持補修費(推計)']
                                    df_push_comp = pd.DataFrame({
                                        '項目名': items_order,
                                        f'{selected_city}': [round(s_push_city.get(it, 0), 1) for it in items_order],
                                        f'{selected_pref}平均' if selected_pref != "全国" else '県内平均': [round(s_push_pref.get(it, 0), 1) for it in items_order],
                                        '全国平均': [round(s_push_japan.get(it, 0), 1) for it in items_order]
                                    })

                                    df_push_melt = df_push_comp[df_push_comp['項目名'] != '経常収支比率'].melt(
                                        id_vars=['項目名'], var_name='比較対象', value_name='寄与度(%pt)'
                                    )

                                    fig_push_comp = px.bar(
                                        df_push_melt, x='項目名', y='寄与度(%pt)', color='比較対象', barmode='group',
                                        text='寄与度(%pt)',
                                        title=f"{selected_city} vs 全国・県内平均 経費別押し上げ寄与度(%pt)比較（{latest_year_str}年度）",
                                        color_discrete_map={f'{selected_city}': '#FF4B4B', f'{selected_pref}平均': '#2CA02C', '県内平均': '#2CA02C', '全国平均': '#1F77B4'}
                                    )
                                    fig_push_comp.update_traces(texttemplate='%{text:.1f}%pt', textposition='outside')
                                    fig_push_comp.update_layout(xaxis_title="経費項目", yaxis_title="押し上げ寄与度 (%pt)", height=400, legend_title_text="")
                                    st.plotly_chart(fig_push_comp, use_container_width=True, key="comp_push_factor_bar")

                                    st.markdown("##### 📋 経常収支比率 押し上げ寄与度（%pt）データ一覧")
                                    st.dataframe(df_push_comp, use_container_width=True, hide_index=True)

                            # --- Tab 2: 1人当たり歳出額(千円/人)の比較 ---
                            with tab_comp_pc:
                                if not s_pc_city.empty:
                                    pc_items_order = ['扶助費', '人件費', '補助費等', '物件費', '公債費', '繰出金', '維持補修費']
                                    df_pc_comp = pd.DataFrame({
                                        '項目名': pc_items_order,
                                        f'{selected_city}': [s_pc_city.get(it, 0) for it in pc_items_order],
                                        f'{selected_pref}平均' if selected_pref != "全国" else '県内平均': [s_pc_pref.get(it, 0) for it in pc_items_order],
                                        '全国平均': [s_pc_japan.get(it, 0) for it in pc_items_order]
                                    })

                                    df_pc_melt = df_pc_comp.melt(id_vars=['項目名'], var_name='比較対象', value_name='1人当たり金額(千円)')

                                    fig_pc_comp = px.bar(
                                        df_pc_melt, x='項目名', y='1人当たり金額(千円)', color='比較対象', barmode='group',
                                        text='1人当たり金額(千円)',
                                        title=f"{selected_city} vs 全国・県内平均 住民1人当たり性質別歳出(千円/人)比較（{latest_year_str}年度）",
                                        color_discrete_map={f'{selected_city}': '#FF4B4B', f'{selected_pref}平均': '#2CA02C', '県内平均': '#2CA02C', '全国平均': '#1F77B4'}
                                    )
                                    fig_pc_comp.update_traces(texttemplate='%{text:,.1f}千円', textposition='outside')
                                    fig_pc_comp.update_layout(xaxis_title="経費項目", yaxis_title="1人当たり金額（千円/人）", height=400, legend_title_text="")
                                    st.plotly_chart(fig_pc_comp, use_container_width=True, key="comp_per_capita_bar")

                                    st.markdown("##### 📋 住民1人当たり歳出額（千円/人）データ一覧")
                                    st.dataframe(df_pc_comp, use_container_width=True, hide_index=True)

                            # --- Tab 3: 1人当たり歳入額(千円/人)の比較（👈 新規追加） ---
                            with tab_comp_rev_pc:
                                if not s_rev_pc_city.empty:
                                    rev_pc_items_order = ['地方税', '地方交付税', '国庫支出金', '都道府県支出金', '地方債', '繰入金', '諸収入']
                                    rev_pc_items_order = [it for it in rev_pc_items_order if it in s_rev_pc_city.index]
                                    df_rev_pc_comp = pd.DataFrame({
                                        '項目名': rev_pc_items_order,
                                        f'{selected_city}': [s_rev_pc_city.get(it, 0) for it in rev_pc_items_order],
                                        f'{selected_pref}平均' if selected_pref != "全国" else '県内平均': [s_rev_pc_pref.get(it, 0) for it in rev_pc_items_order],
                                        '全国平均': [s_rev_pc_japan.get(it, 0) for it in rev_pc_items_order]
                                    })

                                    df_rev_pc_melt = df_rev_pc_comp.melt(id_vars=['項目名'], var_name='比較対象', value_name='1人当たり金額(千円)')

                                    fig_rev_pc_comp = px.bar(
                                        df_rev_pc_melt, x='項目名', y='1人当たり金額(千円)', color='比較対象', barmode='group',
                                        text='1人当たり金額(千円)',
                                        title=f"{selected_city} vs 全国・県内平均 住民1人当たり主要歳入(千円/人)比較（{latest_year_str}年度）",
                                        color_discrete_map={f'{selected_city}': '#FF4B4B', f'{selected_pref}平均': '#2CA02C', '県内平均': '#2CA02C', '全国平均': '#1F77B4'}
                                    )
                                    fig_rev_pc_comp.update_traces(texttemplate='%{text:,.1f}千円', textposition='outside')
                                    fig_rev_pc_comp.update_layout(xaxis_title="歳入項目", yaxis_title="1人当たり金額（千円/人）", height=400, legend_title_text="")
                                    st.plotly_chart(fig_rev_pc_comp, use_container_width=True, key="comp_rev_per_capita_bar")

                                    st.markdown("##### 📋 住民1人当たり歳入額（千円/人）データ一覧")
                                    st.dataframe(df_rev_pc_comp, use_container_width=True, hide_index=True)

            with subtab_eff2:
                cols_scale = [
                    c for c in df_ov_city.columns 
                    if any(kw in c for kw in ['実質単年度収支', '単年度収支', '実質収支']) 
                    and not any(ex in c for ex in ['比率', '%', 'パーセント', '指数'])
                ]
                if cols_scale:
                    df_scale_plot = df_ov_city.copy()
                    fig1 = px.line(df_scale_plot, x='年度', y=cols_scale, markers=True, title="収支関連指標の推移（金額：千円）")
                    fig1.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="収支均衡ライン (0円)", annotation_position="bottom right")
                    
                    data_min = df_scale_plot[cols_scale].min().min()
                    data_max = df_scale_plot[cols_scale].max().max()

                    y_lower = min(-1000000, data_min * 1.2 if pd.notna(data_min) and data_min < 0 else -1000000)
                    y_upper = max(1000000, data_max * 1.1 if pd.notna(data_max) else 1000000)

                    fig1.update_yaxes(range=[y_lower, y_upper], tickformat=",", title="金額（千円）", zeroline=True, zerolinewidth=2, zerolinecolor='black')
                    fig1.update_layout(xaxis_title="年度")
                    st.plotly_chart(fig1, use_container_width=True, key="eff_scale_chart")

        # --- Tab 4, 5, 6, 7 （略：変更なし） ---
        with tab4:
            st.markdown("### 🚨 地方財政健全化法に基づく健全化判断比率 & 負債・基金構造分析")
            cols_kenzen = get_cols_by_keywords(['実質赤字比率', '連結実質赤字比率', '実質公債費比率', '将来負担比率'])
            if cols_kenzen:
                cols_small = [c for c in cols_kenzen if '将来負担比率' not in c]
                cols_large = [c for c in cols_kenzen if '将来負担比率' in c]
                col_left, col_right = st.columns(2)
                with col_left:
                    if cols_small:
                        df_s = df_ov_city[['年度'] + cols_small].copy()
                        df_s = df_s.rename(columns={c: clean_col_label(c) for c in cols_small})
                        fig_s = px.line(df_s, x='年度', y=[clean_col_label(c) for c in cols_small], markers=True, title="実質赤字・連結赤字・実質公債費比率")
                        st.plotly_chart(fig_s, use_container_width=True, key="kenzen_small_chart")
                with col_right:
                    if cols_large:
                        df_l = df_ov_city[['年度'] + cols_large].copy()
                        df_l = df_l.rename(columns={c: clean_col_label(c) for c in cols_large})
                        fig_l = px.line(df_l, x='年度', y=[clean_col_label(c) for c in cols_large], markers=True, title="将来負担比率")
                        st.plotly_chart(fig_l, use_container_width=True, key="kenzen_large_chart")

            st.markdown("---")
            st.markdown("##### 🔍 将来負担比率の裏側（借金残高 vs 貯蓄残高のクッション分析）")
            if not df_bonds_city.empty:
                latest_bond_row = df_bonds_city.sort_values('年度').iloc[-1]
                b_year = latest_bond_row['年度']

                debt_tot = latest_bond_row.get('地方債現在高_合計', 0)
                fund_tot = latest_bond_row.get('積立金現在高_合計', 0)
                net_debt = debt_tot - fund_tot

                b_col1, b_col2, b_col3 = st.columns(3)
                with b_col1:
                    st.metric("地方債残高 (総負債)", f"{debt_tot:,.0f} 千円")
                with b_col2:
                    st.metric("積立金残高 (貯蓄)", f"{fund_tot:,.0f} 千円")
                with b_col3:
                    st.metric("実質負債残高 (相殺後)", f"{net_debt:,.0f} 千円", delta="貯蓄超過" if net_debt < 0 else "負債超過", delta_color="inverse")

        with tab5:
            st.markdown("#### 🏙️ 人口密度・都市構造とインフラ効率性の分析")
            available_ov_years = sorted(df_overview['年度'].astype(str).unique()) if not df_overview.empty else []
            if available_ov_years:
                selected_struct_year = st.selectbox("分析対象年度を選択", available_ov_years, index=len(available_ov_years)-1, key="struct_year_select")
                df_ov_comp = get_comparison_df(df_overview)
                df_ov_y = df_ov_comp[df_ov_comp['年度'].astype(str) == str(selected_struct_year)].copy()
                if not df_ov_y.empty:
                    pop_col = get_population_col(df_ov_y)
                    area_cols = [c for c in df_ov_y.columns if '面積' in c and '千円' not in c and '%' not in c]
                    area_col = area_cols[0] if area_cols else None
                    dem_cols = [c for c in df_ov_y.columns if '基準財政需要額' in c]
                    index_cols = [c for c in df_ov_y.columns if '財政力指数' in c]
                    
                    if pop_col:
                        df_ov_y['人口_num'] = df_ov_y[pop_col]
                    if area_col:
                        df_ov_y['面積_num'] = df_ov_y[area_col]
                        if '人口_num' in df_ov_y.columns:
                            valid_area = df_ov_y['面積_num'].replace(0, np.nan)
                            df_ov_y['人口密度(人/km2)'] = (df_ov_y['人口_num'] / valid_area).round(1)

                    if dem_cols and '人口_num' in df_ov_y.columns:
                        df_ov_y['基準財政需要額_num'] = df_ov_y[dem_cols[0]]
                        valid_pop = df_ov_y['人口_num'].replace(0, np.nan)
                        df_ov_y['1人当たり基準財政需要額(千円)'] = (df_ov_y['基準財政需要額_num'] / valid_pop).round(1)

                    if index_cols:
                        df_ov_y['財政力指数_num'] = df_ov_y[index_cols[0]]

                    city_row = df_ov_y[df_ov_y['団体名'] == selected_city]
                    if not city_row.empty:
                        c_struct = city_row.iloc[0]
                        m1, m2, m3, m4 = st.columns(4)
                        with m1:
                            if '人口密度(人/km2)' in c_struct and not pd.isna(c_struct['人口密度(人/km2)']):
                                st.metric("人口密度", f"{c_struct['人口密度(人/km2)']:,.1f} 人/km²")
                        with m2:
                            if '1人当たり基準財政需要額(千円)' in c_struct and not pd.isna(c_struct['1人当たり基準財政需要額(千円)']):
                                st.metric("1人当たり行政コスト(需要額)", f"{c_struct['1人当たり基準財政需要額(千円)']:,.1f} 千円")
                        with m3:
                            if '財政力指数_num' in c_struct and not pd.isna(c_struct['財政力指数_num']):
                                st.metric("財政力指数", f"{c_struct['財政力指数_num']:.2f}")
                        with m4:
                            if '人口_num' in c_struct:
                                st.metric("総人口", f"{int(c_struct['人口_num']):,} 人")

        with tab6:
            subtab_prof1, subtab_prof2 = st.tabs(["👥 人口・職員数", "🏗️ 産業割合"])
            with subtab_prof1:
                pop_cols = [c for c in df_ov_city.columns if '人口' in c and not any(kw in c for kw in ['千円', '%', '割合', '比率'])]
                if pop_cols:
                    fig_pop = px.line(df_ov_city, x='年度', y=pop_cols, markers=True, title="人口推移")
                    st.plotly_chart(fig_pop, use_container_width=True, key="prof_pop_chart")
            with subtab_prof2:
                ind_cols = [c for c in df_ov_city.columns if any(kw in c for kw in ['第1次', '第2次', '第3次', '産業'])]
                if ind_cols:
                    fig_ind = px.bar(df_ov_city, x='年度', y=ind_cols, title="産業構造の推移", barmode='stack')
                    st.plotly_chart(fig_ind, use_container_width=True, key="prof_ind_chart")

        with tab7:
            st.dataframe(df_ov_city, use_container_width=True)

# ==========================================
# メニュー2: 歳入
# ==========================================
elif menu == "歳入":
    st.markdown("### 歳入の推移と分析")
    if not df_rev_city.empty:
        general_revenue_cols = ['地方税_合計', '地方譲与税_合計', '都道府県税交付金_合計', '地方特例交付金_合計', '地方交付税_合計', '交通安全対策特別交付金', '特別区財政調整交付金']
        specific_revenue_cols = ['国庫支出金_合計', '都道府県支出金_合計', '地方債_合計', '分担金及び負担金_合計', '使用料_合計', '手数料_合計', '財産収入_合計', '寄附金_合計', '繰入金_合計', '繰越金_合計', '諸収入_合計', '国有提供施設等所在市町村助成交付金']

        main_revenue_categories = [c for c in general_revenue_cols + specific_revenue_cols if c in df_revenue.columns]
        jishu_candidate_cols = ['地方税_合計', '分担金及び負担金_合計', '使用料_合計', '手数料_合計', '財産収入_合計', '寄附金_合計', '繰入金_合計', '繰越金_合計', '諸収入_合計']
        jishu_cols_exist = [c for c in jishu_candidate_cols if c in df_revenue.columns]
        izon_candidate_cols = ['地方譲与税_合計', '都道府県税交付金_合計', '地方特例交付金_合計', '地方交付税_合計', '交通安全対策特別交付金', '国庫支出金_合計', '都道府県支出金_合計', '地方債_合計', '国有提供施設等所在市町村助成交付金', '特別区財政調整交付金']
        izon_cols_exist = [c for c in izon_candidate_cols if c in df_revenue.columns]

        rev_category_order = [clean_col_label(c) for c in main_revenue_categories]

        tab_rev1, tab_rev_jishu, tab_rev_comp = st.tabs(["📈 自治体単体分析", "🏛️ 自主財源分析", "🏛️ 自治体間比較"])

        with tab_rev1:
            st.subheader("1. 歳入構造の時系列推移（総額 vs 人口1人当たり）")
            df_plot_base = df_rev_city.groupby('年度', as_index=False)[main_revenue_categories].sum()
            df_plot_base['歳入合計'] = df_plot_base[main_revenue_categories].sum(axis=1)
            df_plot_base['人口_num'] = get_population_series(df_plot_base, df_overview, "latest")

            sub_tot, sub_pc = st.tabs(["💰 総額", "👥 1人当たり"])
            with sub_tot:
                df_melt = df_plot_base.melt(id_vars=['年度'], value_vars=main_revenue_categories, var_name='項目_raw', value_name='金額')
                df_melt['項目名'] = df_melt['項目_raw'].apply(clean_col_label)
                df_melt = df_melt.groupby(['年度', '項目名'], as_index=False)['金額'].sum()
                year_totals = df_melt.groupby('年度')['金額'].transform('sum')
                df_melt['歳入合計'] = year_totals
                df_melt['割合(%)'] = (df_melt['金額'] / df_melt['歳入合計'].replace(0, np.nan) * 100).fillna(0).round(1)

                fig = px.bar(
                    df_melt, x='年度', y='金額', color='項目名', 
                    title=f"{selected_city} 歳入構成の推移（総額）", barmode='stack',
                    custom_data=['項目名', '割合(%)'], category_orders={"項目名": rev_category_order}
                )
                fig.update_layout(yaxis_tickformat=",", yaxis_title="金額（千円）")
                fig.update_traces(hovertemplate="<b>%{customdata[0]}</b><br>金額: %{y:,.0f} 千円<br>構成比: %{customdata[1]}%<extra></extra>")
                st.plotly_chart(fig, use_container_width=True, key="rev_tot_trend")

            with sub_pc:
                if '人口_num' in df_plot_base.columns and (df_plot_base['人口_num'] > 0).any():
                    df_pc_base = df_plot_base.copy()
                    pc_cols = []
                    for c in main_revenue_categories:
                        pc_col_name = c + '_1人当たり'
                        df_pc_base[pc_col_name] = (df_pc_base[c] / df_pc_base['人口_num'].replace(0, np.nan)).round(2)
                        pc_cols.append(pc_col_name)

                    df_melt_pc = df_pc_base.melt(id_vars=['年度'], value_vars=pc_cols, var_name='項目_raw', value_name='1人当たり金額')
                    df_melt_pc['項目名'] = df_melt_pc['項目_raw'].apply(lambda x: clean_col_label(x.replace('_1人当たり', '')))
                    df_melt_pc = df_melt_pc.groupby(['年度', '項目名'], as_index=False)['1人当たり金額'].sum()
                    pc_year_totals = df_melt_pc.groupby('年度')['1人当たり金額'].transform('sum')
                    df_melt_pc['1人当たり歳入合計'] = pc_year_totals
                    df_melt_pc['割合(%)'] = (df_melt_pc['1人当たり金額'] / df_melt_pc['1人当たり歳入合計'].replace(0, np.nan) * 100).fillna(0).round(1)

                    fig_pc = px.bar(
                        df_melt_pc, x='年度', y='1人当たり金額', color='項目名', 
                        title=f"{selected_city} 歳入構成の推移（1人当たり）", barmode='stack',
                        custom_data=['項目名', '割合(%)'], category_orders={"項目名": rev_category_order}
                    )
                    fig_pc.update_layout(yaxis_tickformat=",.1f", yaxis_title="1人当たり金額（千円/人）")
                    fig_pc.update_traces(hovertemplate="<b>%{customdata[0]}</b><br>1人当たり金額: %{y:,.2f} 千円/人<br>構成比: %{customdata[1]}%<extra></extra>")
                    st.plotly_chart(fig_pc, use_container_width=True, key="rev_pc_trend")

        with tab_rev_jishu:
            st.subheader("🏛️ 自主財源の総額・比率および自治体間比較")
            if jishu_cols_exist and izon_cols_exist:
                df_jishu_calc = df_rev_city.groupby('年度', as_index=False)[jishu_cols_exist + izon_cols_exist].sum()
                df_jishu_calc['自主財源_合計'] = df_jishu_calc[jishu_cols_exist].sum(axis=1)
                df_jishu_calc['依存財源_合計'] = df_jishu_calc[izon_cols_exist].sum(axis=1)
                df_jishu_calc['歳入総額_calc'] = df_jishu_calc['自主財源_合計'] + df_jishu_calc['依存財源_合計']
                df_jishu_calc['自主財源比率(%)'] = (df_jishu_calc['自主財源_合計'] / df_jishu_calc['歳入総額_calc'].replace(0, np.nan) * 100).fillna(0).round(1)

                subtab_jishu1, subtab_jishu2, subtab_jishu3 = st.tabs(["📈 単体推移（総額 & 比率）", "📊 自治体間比較（総額内訳）", "👥 自治体間比較（1人当たり内訳）"])
                with subtab_jishu1:
                    fig_jishu = make_subplots(specs=[[{"secondary_y": True}]])
                    fig_jishu.add_trace(go.Bar(x=df_jishu_calc['年度'], y=df_jishu_calc['自主財源_合計'], name='自主財源', marker_color='#1F77B4'), secondary_y=False)
                    fig_jishu.add_trace(go.Bar(x=df_jishu_calc['年度'], y=df_jishu_calc['依存財源_合計'], name='依存財源', marker_color='#A6CEE3'), secondary_y=False)
                    fig_jishu.add_trace(go.Scatter(x=df_jishu_calc['年度'], y=df_jishu_calc['自主財源比率(%)'], mode='lines+markers+text', name='自主財源比率(%)', line=dict(color='#FF4B4B', width=3), text=[f"{v:.1f}%" for v in df_jishu_calc['自主財源比率(%)']], textposition='top center'), secondary_y=True)
                    fig_jishu.update_layout(title=f"{selected_city} 歳入構造と自主財源比率の推移", barmode='stack', xaxis_title="年度")
                    fig_jishu.update_yaxes(title_text="金額（千円）", secondary_y=False, tickformat=",")
                    fig_jishu.update_yaxes(title_text="自主財源比率（%）", secondary_y=True, range=[0, 110])
                    st.plotly_chart(fig_jishu, use_container_width=True, key="jishu_trend_chart")

                with subtab_jishu2:
                    df_pref_rev = get_comparison_df(df_revenue)
                    if not df_pref_rev.empty:
                        comp_year_j = st.selectbox("比較する年度を選択", df_pref_rev['年度'].astype(str).unique(), index=len(df_pref_rev['年度'].astype(str).unique())-1, key="comp_jishu_year")
                        df_comp_j = df_pref_rev[df_pref_rev['年度'].astype(str) == str(comp_year_j)].groupby(['都道府県', '団体名'], as_index=False)[jishu_cols_exist].sum()
                        df_comp_j['自主財源_合計'] = df_comp_j[jishu_cols_exist].sum(axis=1)
                        df_comp_j = df_comp_j.sort_values('自主財源_合計', ascending=False)
                        sorted_cities_j = df_comp_j['団体名'].tolist()

                        df_comp_j_melt = df_comp_j.melt(id_vars=['都道府県', '団体名', '自主財源_合計'], value_vars=jishu_cols_exist, var_name='項目_raw', value_name='金額')
                        df_comp_j_melt['項目名'] = df_comp_j_melt['項目_raw'].apply(clean_col_label)
                        df_comp_j_melt = df_comp_j_melt.groupby(['都道府県', '団体名', '自主財源_合計', '項目名'], as_index=False)['金額'].sum()
                        df_comp_j_melt['割合(%)'] = (df_comp_j_melt['金額'] / df_comp_j_melt['自主財源_合計'].replace(0, np.nan) * 100).fillna(0).round(1)

                        fig_comp_j_stack = px.bar(
                            df_comp_j_melt, x='団体名', y='金額', color='項目名',
                            title=f"{scope_label}（{comp_year_j}年度）自治体別 自主財源内訳比較（総額・大きい順）", barmode='stack',
                            custom_data=['都道府県', '項目名', '割合(%)'], category_orders={'団体名': sorted_cities_j}
                        )
                        fig_comp_j_stack.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
                        st.plotly_chart(fig_comp_j_stack, use_container_width=True, key="jishu_tot_comp_chart")

                with subtab_jishu3:
                    df_pref_rev = get_comparison_df(df_revenue)
                    if not df_pref_rev.empty:
                        comp_year_j_pop = st.selectbox("比較する年度を選択", df_pref_rev['年度'].astype(str).unique(), index=len(df_pref_rev['年度'].astype(str).unique())-1, key="comp_jishu_pop_year")
                        df_comp_j_pop = df_pref_rev[df_pref_rev['年度'].astype(str) == str(comp_year_j_pop)].groupby(['都道府県', '団体名'], as_index=False)[jishu_cols_exist].sum()
                        df_comp_j_pop['人口_num'] = get_population_series(df_comp_j_pop, df_overview, comp_year_j_pop)
                        df_comp_j_pop = df_comp_j_pop[df_comp_j_pop['人口_num'] > 0].copy()

                        jishu_pc_cols = []
                        for c in jishu_cols_exist:
                            pc_col_name = c + '_1人当たり'
                            df_comp_j_pop[pc_col_name] = (df_comp_j_pop[c] / df_comp_j_pop['人口_num']).round(2)
                            jishu_pc_cols.append(pc_col_name)

                        df_comp_j_pop['1人当たり自主財源合計'] = df_comp_j_pop[jishu_pc_cols].sum(axis=1)
                        df_comp_j_pop = df_comp_j_pop.sort_values('1人当たり自主財源合計', ascending=False)
                        sorted_cities_j_pop = df_comp_j_pop['団体名'].tolist()

                        df_melt_j_pc = df_comp_j_pop.melt(id_vars=['都道府県', '団体名', '1人当たり自主財源合計'], value_vars=jishu_pc_cols, var_name='項目_raw', value_name='1人当たり金額')
                        df_melt_j_pc['項目名'] = df_melt_j_pc['項目_raw'].apply(lambda x: clean_col_label(x.replace('_1人当たり', '')))
                        df_melt_j_pc = df_melt_j_pc.groupby(['都道府県', '団体名', '1人当たり自主財源合計', '項目名'], as_index=False)['1人当たり金額'].sum()
                        df_melt_j_pc['割合(%)'] = (df_melt_j_pc['1人当たり金額'] / df_melt_j_pc['1人当たり自主財源合計'].replace(0, np.nan) * 100).fillna(0).round(1)

                        fig_j_pc = px.bar(
                            df_melt_j_pc, x='団体名', y='1人当たり金額', color='項目名',
                            title=f"{scope_label}（{comp_year_j_pop}年度）自治体別 1人当たり自主財源内訳比較（大きい順）", barmode='stack',
                            custom_data=['都道府県', '項目名', '割合(%)'], category_orders={'団体名': sorted_cities_j_pop}
                        )
                        fig_j_pc.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
                        st.plotly_chart(fig_j_pc, use_container_width=True, key="jishu_pc_comp_chart")

        with tab_rev_comp:
            subtab_rev_tot, subtab_rev_pc, subtab_rev_sub = st.tabs(["📊 自治体間比較（総額）", "👥 自治体間比較（1人当たり）", "🔍 細分化項目比較（全税目・内訳一覧）"])
            with subtab_rev_tot:
                st.subheader(f"{scope_label} 自治体歳入比較（総額）")
                df_pref_rev = get_comparison_df(df_revenue)
                if not df_pref_rev.empty:
                    comp_year_rev = st.selectbox("比較する年度を選択", df_pref_rev['年度'].astype(str).unique(), index=len(df_pref_rev['年度'].astype(str).unique())-1, key="comp_rev_year")
                    df_comp = df_pref_rev[df_pref_rev['年度'].astype(str) == str(comp_year_rev)].groupby(['都道府県', '団体名'], as_index=False)[main_revenue_categories].sum()
                    df_comp['歳入合計'] = df_comp[main_revenue_categories].sum(axis=1)
                    df_comp = df_comp.sort_values('歳入合計', ascending=False)
                    sorted_cities_rev = df_comp['団体名'].tolist()

                    df_melt_comp = df_comp.melt(id_vars=['都道府県', '団体名', '歳入合計'], value_vars=main_revenue_categories, var_name='項目_raw', value_name='金額')
                    df_melt_comp['項目名'] = df_melt_comp['項目_raw'].apply(clean_col_label)
                    df_melt_comp = df_melt_comp.groupby(['都道府県', '団体名', '歳入合計', '項目名'], as_index=False)['金額'].sum()
                    df_melt_comp['割合(%)'] = (df_melt_comp['金額'] / df_melt_comp['歳入合計'].replace(0, np.nan) * 100).fillna(0).round(1)

                    fig_c = px.bar(
                        df_melt_comp, x='団体名', y='金額', color='項目名', 
                        title=f"{scope_label}（{comp_year_rev}年度）自治体別 歳入構成比較（総額・大きい順）", barmode='stack',
                        custom_data=['都道府県', '項目名', '割合(%)'], category_orders={"項目名": rev_category_order, "団体名": sorted_cities_rev}
                    )
                    fig_c.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
                    st.plotly_chart(fig_c, use_container_width=True, key="rev_tot_comp_chart")

            with subtab_rev_pc:
                st.subheader(f"{scope_label} 自治体歳入比較（人口1人当たり）")
                df_pref_rev = get_comparison_df(df_revenue)
                if not df_pref_rev.empty:
                    comp_year_rev_pop = st.selectbox("比較する年度を選択", df_pref_rev['年度'].astype(str).unique(), index=len(df_pref_rev['年度'].astype(str).unique())-1, key="comp_rev_pop_year")
                    df_comp_pop = df_pref_rev[df_pref_rev['年度'].astype(str) == str(comp_year_rev_pop)].groupby(['都道府県', '団体名'], as_index=False)[main_revenue_categories].sum()
                    df_comp_pop['人口_num'] = get_population_series(df_comp_pop, df_overview, comp_year_rev_pop)
                    df_comp_pop = df_comp_pop[df_comp_pop['人口_num'] > 0].copy()
                    
                    pc_cols = []
                    for c in main_revenue_categories:
                        pc_col_name = c + '_1人当たり'
                        df_comp_pop[pc_col_name] = (df_comp_pop[c] / df_comp_pop['人口_num']).round(2)
                        pc_cols.append(pc_col_name)

                    df_comp_pop['1人当たり歳入合計'] = df_comp_pop[pc_cols].sum(axis=1)
                    df_comp_pop = df_comp_pop.sort_values('1人当たり歳入合計', ascending=False)
                    sorted_cities_rev_pop = df_comp_pop['団体名'].tolist()

                    df_melt_pc_all = df_comp_pop.melt(id_vars=['都道府県', '団体名', '1人当たり歳入合計'], value_vars=pc_cols, var_name='項目_raw', value_name='1人当たり金額')
                    df_melt_pc_all['項目名'] = df_melt_pc_all['項目_raw'].apply(lambda x: clean_col_label(x.replace('_1人当たり', '')))
                    df_melt_pc_all = df_melt_pc_all.groupby(['都道府県', '団体名', '1人当たり歳入合計', '項目名'], as_index=False)['1人当たり金額'].sum()
                    df_melt_pc_all['割合(%)'] = (df_melt_pc_all['1人当たり金額'] / df_melt_pc_all['1人当たり歳入合計'].replace(0, np.nan) * 100).fillna(0).round(1)

                    fig_pc = px.bar(
                        df_melt_pc_all, x='団体名', y='1人当たり金額', color='項目名',
                        title=f"{scope_label}（{comp_year_rev_pop}年度）自治体別 1人当たり歳入構成比較（大きい順）", barmode='stack',
                        custom_data=['都道府県', '項目名', '割合(%)'], category_orders={"項目名": rev_category_order, "団体名": sorted_cities_rev_pop}
                    )
                    fig_pc.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
                    st.plotly_chart(fig_pc, use_container_width=True, key="rev_pc_comp_chart")

            with subtab_rev_sub:
                st.subheader("🔍 細分化項目・全税目等の自治体間比較・内訳深掘り")
                df_pref_rev = get_comparison_df(df_revenue)
                rev_parent_options = {c: clean_col_label(c) for c in main_revenue_categories}
                selected_parent = st.selectbox("分析する歳入の大項目を選択", list(rev_parent_options.keys()), format_func=lambda x: rev_parent_options[x], key="sub_rev_parent")
                
                prefix = selected_parent.replace('_合計', '') + '_' if '_合計' in selected_parent else selected_parent + '_'
                sub_rev_cols = [c for c in df_revenue.columns if c.startswith(prefix) and c != selected_parent and '小計' not in c and '不納欠損' not in c and '参考_' not in c]
                
                c_city_col = '団体名' if '団体名' in df_pref_rev.columns else ('市町村名' if '市町村名' in df_pref_rev.columns else df_pref_rev.columns[0])
                c_pref_col = '都道府県' if '都道府県' in df_pref_rev.columns else '都道府県名'
                group_c_cols_r = [c for c in [c_pref_col, c_city_col] if c in df_pref_rev.columns]

                if sub_rev_cols:
                    sub_rev_labels = {c: c.replace(prefix, '').replace('寄附金_', '').replace('寄付金_', '') for c in sub_rev_cols}
                    sub_mode1, sub_mode2 = st.tabs(["📊 傘下全項目（全税目等）の一括自治体比較", "🔍 特定の細分化項目の個別比較"])

                    with sub_mode1:
                        avail_sub_years = df_pref_rev['年度'].astype(str).unique()
                        selected_sub_year = st.selectbox("比較年度を選択", avail_sub_years, index=len(avail_sub_years)-1, key="all_sub_rev_year")
                        unit_mode = st.radio("表示単位", ["1人当たり金額（千円/人）", "総額（千円）"], horizontal=True, key="unit_all_sub_rev")

                        df_pref_sub_y = df_pref_rev[df_pref_rev['年度'].astype(str) == str(selected_sub_year)].groupby(['都道府県', '団体名'], as_index=False)[sub_rev_cols].sum()
                        df_pref_sub_y['人口_num'] = get_population_series(df_pref_sub_y, df_overview, selected_sub_year)

                        if unit_mode == "1人当たり金額（千円/人）":
                            plot_sub_cols = []
                            for c in sub_rev_cols:
                                pc_c = c + '_1人当たり'
                                df_pref_sub_y[pc_c] = (df_pref_sub_y[c] / df_pref_sub_y['人口_num'].replace(0, np.nan)).round(2)
                                plot_sub_cols.append(pc_c)
                            
                            df_pref_sub_y['内訳合計_calc'] = df_pref_sub_y[plot_sub_cols].sum(axis=1)
                            df_pref_sub_y = df_pref_sub_y.sort_values('内訳合計_calc', ascending=False)
                            sorted_cities_sub_rev1 = df_pref_sub_y['団体名'].tolist()

                            df_melt_all_sub = df_pref_sub_y.melt(id_vars=['都道府県', '団体名', '内訳合計_calc'], value_vars=plot_sub_cols, var_name='項目_raw', value_name='数値')
                            df_melt_all_sub['内訳名'] = df_melt_all_sub['項目_raw'].apply(lambda x: sub_rev_labels.get(x.replace('_1人当たり', ''), clean_col_label(x)))
                            df_melt_all_sub = df_melt_all_sub.groupby(['都道府県', '団体名', '内訳合計_calc', '内訳名'], as_index=False)['数値'].sum()
                            df_melt_all_sub['割合(%)'] = (df_melt_all_sub['数値'] / df_melt_all_sub['内訳合計_calc'].replace(0, np.nan) * 100).fillna(0).round(1)

                            fig_all_sub = px.bar(
                                df_melt_all_sub, x='団体名', y='数値', color='内訳名',
                                title=f"{scope_label}（{selected_sub_year}年度）{rev_parent_options[selected_parent]} 内訳全項目 1人当たり比較",
                                barmode='stack', custom_data=['都道府県', '内訳名', '割合(%)'], category_orders={'団体名': sorted_cities_sub_rev1}
                            )
                            fig_all_sub.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
                            st.plotly_chart(fig_all_sub, use_container_width=True, key="rev_sub1_pc_chart")
                        else:
                            df_pref_sub_y['内訳合計_calc'] = df_pref_sub_y[sub_rev_cols].sum(axis=1)
                            df_pref_sub_y = df_pref_sub_y.sort_values('内訳合計_calc', ascending=False)
                            sorted_cities_sub_rev2 = df_pref_sub_y['団体名'].tolist()

                            df_melt_all_sub = df_pref_sub_y.melt(id_vars=['都道府県', '団体名', '内訳合計_calc'], value_vars=sub_rev_cols, var_name='項目_raw', value_name='数値')
                            df_melt_all_sub['内訳名'] = df_melt_all_sub['項目_raw'].apply(lambda x: sub_rev_labels.get(x, clean_col_label(x)))
                            df_melt_all_sub = df_melt_all_sub.groupby(['都道府県', '団体名', '内訳合計_calc', '内訳名'], as_index=False)['数値'].sum()
                            df_melt_all_sub['割合(%)'] = (df_melt_all_sub['数値'] / df_melt_all_sub['内訳合計_calc'].replace(0, np.nan) * 100).fillna(0).round(1)

                            fig_all_sub = px.bar(
                                df_melt_all_sub, x='団体名', y='数値', color='内訳名',
                                title=f"{scope_label}（{selected_sub_year}年度）{rev_parent_options[selected_parent]} 内訳全項目 総額比較",
                                barmode='stack', custom_data=['都道府県', '内訳名', '割合(%)'], category_orders={'団体名': sorted_cities_sub_rev2}
                            )
                            fig_all_sub.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
                            st.plotly_chart(fig_all_sub, use_container_width=True, key="rev_sub1_tot_chart")

                    with sub_mode2:
                        selected_sub_item = st.selectbox("比較する細分化項目を選択", list(sub_rev_labels.keys()), format_func=lambda x: sub_rev_labels[x], key="single_sub_rev_item")
                        sub_item_name = sub_rev_labels[selected_sub_item]
                        avail_sub_years = df_pref_rev['年度'].astype(str).unique()
                        selected_sub_year_single = st.selectbox("比較年度を選択", avail_sub_years, index=len(avail_sub_years)-1, key="single_sub_rev_year")

                        df_pref_sub_y = df_pref_rev[df_pref_rev['年度'].astype(str) == str(selected_sub_year_single)].groupby(['都道府県', '団体名'], as_index=False)[selected_sub_item].sum()
                        df_pref_sub_y['人口_num'] = get_population_series(df_pref_sub_y, df_overview, selected_sub_year_single)

                        val_s = pd.to_numeric(df_pref_sub_y[selected_sub_item], errors='coerce').fillna(0)
                        pop_s = pd.to_numeric(df_pref_sub_y['人口_num'], errors='coerce').replace(0, np.nan)
                        df_pref_sub_y['1人当たり金額(千円)'] = (val_s / pop_s).round(2)

                        sub_rank_mode = st.radio("比較表示モード", ["1人当たり金額（千円/人）", "総額（千円）"], horizontal=True, key="sub_rev_single_mode")
                        target_rank_col = '1人当たり金額(千円)' if sub_rank_mode == "1人当たり金額（千円/人）" else selected_sub_item

                        df_rank_sub = df_pref_sub_y.sort_values(target_rank_col, ascending=False).copy()
                        sorted_cities_sub_single = df_rank_sub['団体名'].tolist()
                        df_rank_sub['表示色'] = df_rank_sub['団体名'].apply(lambda x: '選択中の自治体' if x == selected_city else 'その他自治体')

                        fig_sub_rank = px.bar(
                            df_rank_sub, x='団体名', y=target_rank_col, color='表示色', text=target_rank_col,
                            title=f"{scope_label}（{selected_sub_year_single}年度）{sub_item_name} {sub_rank_mode} 比較",
                            color_discrete_map={'選択中の自治体': '#FF4B4B', 'その他自治体': '#1F77B4'},
                            custom_data=['都道府県', selected_sub_item], category_orders={'団体名': sorted_cities_sub_single}
                        )
                        fig_sub_rank.update_traces(texttemplate='%{text:,.1f}', textposition='outside')
                        st.plotly_chart(fig_sub_rank, use_container_width=True, key="rev_sub2_single_chart")
                else:
                    st.info(f"💡 「{rev_parent_options[selected_parent]}」には詳細な細分化データが含まれていないため、総額（合計）を比較表示します。")
                    avail_sub_rev_years = df_pref_rev['年度'].astype(str).unique()
                    selected_sub_rev_year_single = st.selectbox("比較年度を選択", avail_sub_rev_years, index=len(avail_sub_rev_years)-1, key="single_tot_rev_year")

                    df_pref_sub_r_y = df_pref_rev[df_pref_rev['年度'].astype(str) == str(selected_sub_rev_year_single)].groupby(group_c_cols_r, as_index=False)[selected_parent].sum()
                    df_pref_sub_r_y['人口_num'] = get_population_series(df_pref_sub_r_y, df_overview, selected_sub_rev_year_single)

                    val_s = pd.to_numeric(df_pref_sub_r_y[selected_parent], errors='coerce').fillna(0)
                    pop_s = pd.to_numeric(df_pref_sub_r_y['人口_num'], errors='coerce').replace(0, np.nan)
                    df_pref_sub_r_y['1人当たり金額(千円)'] = (val_s / pop_s).round(2)

                    sub_rev_rank_mode = st.radio("比較表示モード", ["1人当たり金額（千円/人）", "総額（千円）"], horizontal=True, key="sub_rev_tot_mode")
                    target_rank_col_r = '1人当たり金額(千円)' if sub_rev_rank_mode == "1人当たり金額（千円/人）" else selected_parent

                    df_rank_sub_r = df_pref_sub_r_y.sort_values(target_rank_col_r, ascending=False).copy()
                    clean_selected_city = str(selected_city).strip()
                    df_rank_sub_r['表示色'] = df_rank_sub_r[c_city_col].apply(lambda x: '選択中の自治体' if clean_selected_city in str(x) else 'その他自治体')

                    fig_sub_rev_rank = px.bar(
                        df_rank_sub_r, x=c_city_col, y=target_rank_col_r, color='表示色', text=target_rank_col_r,
                        title=f"{scope_label}（{selected_sub_rev_year_single}年度）{rev_parent_options[selected_parent]} {sub_rev_rank_mode} 比較",
                        color_discrete_map={'選択中の自治体': '#FF4B4B', 'その他自治体': '#1F77B4'},
                        custom_data=[c_pref_col if c_pref_col in df_rank_sub_r.columns else c_city_col, selected_parent]
                    )
                    fig_sub_rev_rank.update_traces(texttemplate='%{text:,.1f}', textposition='outside')
                    st.plotly_chart(fig_sub_rev_rank, use_container_width=True, key="rev_sub_tot_single_chart")

# ==========================================
# メニュー3: 性質別歳出
# ==========================================
elif menu == "性質別歳出":
    st.markdown("### 性質別歳出の推移と分析")
    
    exp_nature_kw_map = {
        '人件費': ['人件費'], '物件費': ['物件費'], '維持補修費': ['維持補修'],
        '扶助費': ['扶助費'], '補助費等': ['補助費'], '普通建設事業費': ['普通建設'],
        '災害復旧事業費': ['災害復旧'], '公債費': ['公債費'], '積立金': ['積立金'], '繰出金': ['繰出金']
    }
    
    main_categories = []
    if not df_exp_nature.empty:
        for label, kws in exp_nature_kw_map.items():
            matched = [
                c for c in df_exp_nature.columns 
                if any(kw in c for kw in kws) 
                and not any(ex in c for ex in ['1人当たり', 'パーセント', '%', '割合', '比率'])
            ]
            if matched:
                main_categories.append(matched[0])

    exp_category_order = [clean_col_label(c) for c in main_categories]

    tab_exp1, tab_exp_comp = st.tabs(["📈 自治体単体分析", "🏛️ 自治体間比較"])

    # --- 1. 単体分析 ---
    with tab_exp1:
        st.subheader("1. 性質別歳出の時系列推移（総額 vs 人口1人当たり）")
        
        # A. df_exp_city に詳細データが存在する場合
        if not df_exp_city.empty and main_categories:
            group_cols_e = [c for c in ['都道府県', '団体名', '年度'] if c in df_exp_city.columns]
            df_plot_base = df_exp_city.groupby(group_cols_e, as_index=False)[main_categories].sum()
            df_plot_base['歳出合計'] = df_plot_base[main_categories].sum(axis=1)
            df_plot_base['人口_num'] = get_population_series(df_plot_base, df_overview, "latest")

            # 「自治体間比較」と同じ表記（「💰 総額」「👥 1人当たり」）に統一
            sub_exp_tot, sub_exp_pc = st.tabs(["💰 総額", "👥 1人当たり"])
            
            # --- 総額タブ ---
            with sub_exp_tot:
                df_melt_e = df_plot_base.melt(id_vars=['年度'], value_vars=main_categories, var_name='項目_raw', value_name='金額')
                df_melt_e['項目名'] = df_melt_e['項目_raw'].apply(clean_col_label)
                df_melt_e = df_melt_e.groupby(['年度', '項目名'], as_index=False)['金額'].sum()
                
                year_totals = df_melt_e.groupby('年度')['金額'].transform('sum')
                df_melt_e['歳出合計'] = year_totals
                df_melt_e['割合(%)'] = (df_melt_e['金額'] / df_melt_e['歳出合計'].replace(0, np.nan) * 100).fillna(0).round(1)

                fig_exp = px.bar(
                    df_melt_e, x='年度', y='金額', color='項目名', 
                    title=f"{selected_city} 性質別歳出（総額）", barmode='stack',
                    custom_data=['項目名', '割合(%)'],
                    category_orders={"項目名": exp_category_order}
                )
                fig_exp.update_layout(yaxis_tickformat=",", yaxis_title="金額（千円）", legend_title_text="項目名")
                fig_exp.update_traces(hovertemplate="<b>%{customdata[0]}</b><br>金額: %{y:,.0f} 千円<br>構成比: %{customdata[1]}%<extra></extra>")
                st.plotly_chart(fig_exp, use_container_width=True, key="exp_nature_tot_trend")

            # --- 1人当たりタブ ---
            with sub_exp_pc:
                if '人口_num' in df_plot_base.columns and (df_plot_base['人口_num'] > 0).any():
                    df_pc_base = df_plot_base.copy()
                    pc_cols_e = []
                    for c in main_categories:
                        pc_col_name = c + '_1人当たり'
                        df_pc_base[pc_col_name] = (df_pc_base[c] / df_pc_base['人口_num'].replace(0, np.nan)).round(2)
                        pc_cols_e.append(pc_col_name)

                    df_melt_e_pc = df_pc_base.melt(id_vars=['年度'], value_vars=pc_cols_e, var_name='項目_raw', value_name='1人当たり金額')
                    df_melt_e_pc['項目名'] = df_melt_e_pc['項目_raw'].apply(lambda x: clean_col_label(x.replace('_1人当たり', '')))
                    df_melt_e_pc = df_melt_e_pc.groupby(['年度', '項目名'], as_index=False)['1人当たり金額'].sum()
                    
                    pc_year_totals = df_melt_e_pc.groupby('年度')['1人当たり金額'].transform('sum')
                    df_melt_e_pc['1人当たり歳出合計'] = pc_year_totals
                    df_melt_e_pc['割合(%)'] = (df_melt_e_pc['1人当たり金額'] / df_melt_e_pc['1人当たり歳出合計'].replace(0, np.nan) * 100).fillna(0).round(1)

                    fig_exp_pc = px.bar(
                        df_melt_e_pc, x='年度', y='1人当たり金額', color='項目名', 
                        title=f"{selected_city} 性質別歳出（1人当たり）", barmode='stack',
                        custom_data=['項目名', '割合(%)'],
                        category_orders={"項目名": exp_category_order}
                    )
                    fig_exp_pc.update_layout(yaxis_tickformat=",.1f", yaxis_title="1人当たり金額（千円/人）", legend_title_text="項目名")
                    fig_exp_pc.update_traces(hovertemplate="<b>%{customdata[0]}</b><br>1人当たり金額: %{y:,.2f} 千円/人<br>構成比: %{customdata[1]}%<extra></extra>")
                    st.plotly_chart(fig_exp_pc, use_container_width=True, key="exp_nature_pc_trend")

        # B. 詳細データが存在しない場合はメッセージのみ表示
        else:
            st.info(f"💡 **{selected_city}** の性質別歳出データはありません。")

        # --- 2. 自治体間比較 ---
        with tab_exp_comp:
            subtab_exp_tot, subtab_exp_pc, subtab_exp_sub, subtab_exp_rank = st.tabs(["💰 総額", "👥 1人当たり", "🔍 細分化項目比較（内訳一括・個別）", "🏆 項目別ランキング・自治体力点分析"])

            with subtab_exp_tot:
                st.subheader(f"{scope_label} 性質別歳出比較（総額）")
                df_pref_exp = get_comparison_df(df_exp_nature)
                if not df_pref_exp.empty:
                    comp_year_exp = st.selectbox("比較する年度を選択", df_pref_exp['年度'].astype(str).unique(), index=len(df_pref_exp['年度'].astype(str).unique())-1, key="comp_exp_year")
                    c_city_col = '団体名' if '団体名' in df_pref_exp.columns else ('市町村名' if '市町村名' in df_pref_exp.columns else df_pref_exp.columns[0])
                    c_pref_col = '都道府県' if '都道府県' in df_pref_exp.columns else '都道府県名'
                    group_c_cols_e = [c for c in [c_pref_col, c_city_col] if c in df_pref_exp.columns]

                    df_comp_e = df_pref_exp[df_pref_exp['年度'].astype(str) == str(comp_year_exp)].groupby(group_c_cols_e, as_index=False)[main_categories].sum()
                    df_comp_e['歳出合計'] = df_comp_e[main_categories].sum(axis=1)
                    df_comp_e = df_comp_e.sort_values('歳出合計', ascending=False)
                    sorted_cities_exp = df_comp_e[c_city_col].tolist()

                    df_melt_ce = df_comp_e.melt(id_vars=group_c_cols_e + ['歳出合計'], value_vars=main_categories, var_name='項目_raw', value_name='金額')
                    df_melt_ce['項目名'] = df_melt_ce['項目_raw'].apply(clean_col_label)
                    df_melt_ce = df_melt_ce.groupby(group_c_cols_e + ['歳出合計', '項目名'], as_index=False)['金額'].sum()
                    df_melt_ce['割合(%)'] = (df_melt_ce['金額'] / df_melt_ce['歳出合計'].replace(0, np.nan) * 100).fillna(0).round(1)

                    fig_ce = px.bar(
                        df_melt_ce, x=c_city_col, y='金額', color='項目名', 
                        title=f"{scope_label}（{comp_year_exp}年度）性質別歳出比較（総額・大きい順）", barmode='stack',
                        custom_data=[c_pref_col if c_pref_col in df_melt_ce.columns else c_city_col, '項目名', '割合(%)'],
                        category_orders={"項目名": exp_category_order, c_city_col: sorted_cities_exp}
                    )
                    fig_ce.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
                    st.plotly_chart(fig_ce, use_container_width=True, key="exp_nature_tot_comp_chart")

            with subtab_exp_pc:
                st.subheader(f"{scope_label} 性質別歳出比較（人口1人当たり）")
                df_pref_exp = get_comparison_df(df_exp_nature)
                if not df_pref_exp.empty:
                    comp_year_exp_pop = st.selectbox("比較する年度を選択", df_pref_exp['年度'].astype(str).unique(), index=len(df_pref_exp['年度'].astype(str).unique())-1, key="comp_exp_pop_year")
                    c_city_col = '団体名' if '団体名' in df_pref_exp.columns else ('市町村名' if '市町村名' in df_pref_exp.columns else df_pref_exp.columns[0])
                    c_pref_col = '都道府県' if '都道府県' in df_pref_exp.columns else '都道府県名'
                    group_c_cols_e = [c for c in [c_pref_col, c_city_col] if c in df_pref_exp.columns]

                    df_comp_e_pop = df_pref_exp[df_pref_exp['年度'].astype(str) == str(comp_year_exp_pop)].groupby(group_c_cols_e, as_index=False)[main_categories].sum()
                    df_comp_e_pop['人口_num'] = get_population_series(df_comp_e_pop, df_overview, comp_year_exp_pop)
                    df_comp_e_pop = df_comp_e_pop[df_comp_e_pop['人口_num'] > 0].copy()
                    
                    pc_cols_e = []
                    for c in main_categories:
                        pc_c = c + '_1人当たり'
                        df_comp_e_pop[pc_c] = (df_comp_e_pop[c] / df_comp_e_pop['人口_num']).round(2)
                        pc_cols_e.append(pc_c)

                    df_comp_e_pop['1人当たり歳出合計'] = df_comp_e_pop[pc_cols_e].sum(axis=1)
                    df_comp_e_pop = df_comp_e_pop.sort_values('1人当たり歳出合計', ascending=False)
                    sorted_cities_exp_pop = df_comp_e_pop[c_city_col].tolist()

                    df_melt_ce_pc = df_comp_e_pop.melt(id_vars=group_c_cols_e + ['1人当たり歳出合計'], value_vars=pc_cols_e, var_name='項目_raw', value_name='1人当たり金額')
                    df_melt_ce_pc['項目名'] = df_melt_ce_pc['項目_raw'].apply(lambda x: clean_col_label(x.replace('_1人当たり', '')))
                    df_melt_ce_pc = df_melt_ce_pc.groupby(group_c_cols_e + ['1人当たり歳出合計', '項目名'], as_index=False)['1人当たり金額'].sum()
                    df_melt_ce_pc['割合(%)'] = (df_melt_ce_pc['1人当たり金額'] / df_melt_ce_pc['1人当たり歳出合計'].replace(0, np.nan) * 100).fillna(0).round(1)

                    fig_pc_e = px.bar(
                        df_melt_ce_pc, x=c_city_col, y='1人当たり金額', color='項目名', 
                        title=f"{scope_label}（{comp_year_exp_pop}年度）自治体別 1人当たり性質別歳出比較（大きい順）", barmode='stack',
                        custom_data=[c_pref_col if c_pref_col in df_melt_ce_pc.columns else c_city_col, '項目名', '割合(%)'],
                        category_orders={"項目名": exp_category_order, c_city_col: sorted_cities_exp_pop}
                    )
                    fig_pc_e.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
                    st.plotly_chart(fig_pc_e, use_container_width=True, key="exp_nature_pc_comp_chart")

            with subtab_exp_sub:
                st.subheader("🔍 性質別歳出 細分化項目の比較分析")
                df_pref_exp = get_comparison_df(df_exp_nature)
                exp_parent_options = {c: clean_col_label(c) for c in main_categories}
                selected_exp_parent = st.selectbox("分析する歳出の大項目（性質別）を選択", list(exp_parent_options.keys()), format_func=lambda x: exp_parent_options[x], key="sub_exp_parent")
                
                prefix_exp = selected_exp_parent.replace('_合計', '') + '_'
                sub_exp_cols = [c for c in df_exp_nature.columns if c.startswith(prefix_exp) and c != selected_exp_parent and '小計' not in c]
                
                c_city_col = '団体名' if '団体名' in df_pref_exp.columns else ('市町村名' if '市町村名' in df_pref_exp.columns else df_pref_exp.columns[0])
                c_pref_col = '都道府県' if '都道府県' in df_pref_exp.columns else '都道府県名'
                group_c_cols_e = [c for c in [c_pref_col, c_city_col] if c in df_pref_exp.columns]

                if sub_exp_cols:
                    sub_exp_labels = {c: c.replace(prefix_exp, '') for c in sub_exp_cols}
                    sub_exp_mode1, sub_exp_mode2 = st.tabs(["📊 傘下全項目の一括自治体比較", "🔍 特定の細分化項目の個別比較"])

                    with sub_exp_mode1:
                        avail_sub_exp_years = df_pref_exp['年度'].astype(str).unique()
                        selected_sub_exp_year = st.selectbox("比較年度を選択", avail_sub_exp_years, index=len(avail_sub_exp_years)-1, key="sub_exp_year_select")
                        unit_mode_e = st.radio("表示単位", ["1人当たり金額（千円/人）", "総額（千円）"], horizontal=True, key="unit_exp_sub")

                        df_pref_sub_e_y = df_pref_exp[df_pref_exp['年度'].astype(str) == str(selected_sub_exp_year)].groupby(group_c_cols_e, as_index=False)[sub_exp_cols].sum()
                        df_pref_sub_e_y['人口_num'] = get_population_series(df_pref_sub_e_y, df_overview, selected_sub_exp_year)

                        if unit_mode_e == "1人当たり金額（千円/人）":
                            plot_sub_cols_e = []
                            for c in sub_exp_cols:
                                pc_c = c + '_1人当たり'
                                val_s = pd.to_numeric(df_pref_sub_e_y[c], errors='coerce').fillna(0)
                                pop_s = pd.to_numeric(df_pref_sub_e_y['人口_num'], errors='coerce').replace(0, np.nan)
                                df_pref_sub_e_y[pc_c] = (val_s / pop_s).round(2)
                                plot_sub_cols_e.append(pc_c)
                            
                            df_pref_sub_e_y['内訳合計_calc'] = df_pref_sub_e_y[plot_sub_cols_e].sum(axis=1)
                            df_pref_sub_e_y = df_pref_sub_e_y.sort_values('内訳合計_calc', ascending=False)
                            sorted_cities_exp_sub1 = df_pref_sub_e_y[c_city_col].tolist()

                            df_melt_all_sub_e = df_pref_sub_e_y.melt(id_vars=group_c_cols_e + ['内訳合計_calc'], value_vars=plot_sub_cols_e, var_name='項目_raw', value_name='数値')
                            df_melt_all_sub_e['内訳名'] = df_melt_all_sub_e['項目_raw'].apply(lambda x: sub_exp_labels.get(x.replace('_1人当たり', ''), clean_col_label(x)))
                            df_melt_all_sub_e = df_melt_all_sub_e.groupby(group_c_cols_e + ['内訳合計_calc', '内訳名'], as_index=False)['数値'].sum()
                            df_melt_all_sub_e['割合(%)'] = (df_melt_all_sub_e['数値'] / df_melt_all_sub_e['内訳合計_calc'].replace(0, np.nan) * 100).fillna(0).round(1)

                            fig_all_sub_e = px.bar(
                                df_melt_all_sub_e, x=c_city_col, y='数値', color='内訳名',
                                title=f"{scope_label}（{selected_sub_exp_year}年度）{exp_parent_options[selected_exp_parent]} 内訳一括比較（1人当たり）",
                                barmode='stack', custom_data=[c_pref_col if c_pref_col in df_melt_all_sub_e.columns else c_city_col, '内訳名', '割合(%)'],
                                category_orders={c_city_col: sorted_cities_exp_sub1}
                            )
                            fig_all_sub_e.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
                            st.plotly_chart(fig_all_sub_e, use_container_width=True, key="exp_sub_pc_chart")
                        else:
                            df_pref_sub_e_y['内訳合計_calc'] = df_pref_sub_e_y[sub_exp_cols].sum(axis=1)
                            df_pref_sub_e_y = df_pref_sub_e_y.sort_values('内訳合計_calc', ascending=False)
                            sorted_cities_exp_sub2 = df_pref_sub_e_y[c_city_col].tolist()

                            df_melt_all_sub_e = df_pref_sub_e_y.melt(id_vars=group_c_cols_e + ['内訳合計_calc'], value_vars=sub_exp_cols, var_name='項目_raw', value_name='数値')
                            df_melt_all_sub_e['内訳名'] = df_melt_all_sub_e['項目_raw'].apply(lambda x: sub_exp_labels.get(x, clean_col_label(x)))
                            df_melt_all_sub_e = df_melt_all_sub_e.groupby(group_c_cols_e + ['内訳合計_calc', '内訳名'], as_index=False)['数値'].sum()
                            df_melt_all_sub_e['割合(%)'] = (df_melt_all_sub_e['数値'] / df_melt_all_sub_e['内訳合計_calc'].replace(0, np.nan) * 100).fillna(0).round(1)

                            fig_all_sub_e = px.bar(
                                df_melt_all_sub_e, x=c_city_col, y='数値', color='内訳名',
                                title=f"{scope_label}（{selected_sub_exp_year}年度）{exp_parent_options[selected_exp_parent]} 内訳一括比較（総額）",
                                barmode='stack', custom_data=[c_pref_col if c_pref_col in df_melt_all_sub_e.columns else c_city_col, '内訳名', '割合(%)'],
                                category_orders={c_city_col: sorted_cities_exp_sub2}
                            )
                            fig_all_sub_e.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
                            st.plotly_chart(fig_all_sub_e, use_container_width=True, key="exp_sub_tot_chart")

                    with sub_exp_mode2:
                        selected_sub_exp_item = st.selectbox("比較する細分化項目を選択", list(sub_exp_labels.keys()), format_func=lambda x: sub_exp_labels[x], key="single_sub_exp_item")
                        sub_exp_item_name = sub_exp_labels[selected_sub_exp_item]
                        avail_sub_exp_years = df_pref_exp['年度'].astype(str).unique()
                        selected_sub_exp_year_single = st.selectbox("比較年度を選択", avail_sub_exp_years, index=len(avail_sub_exp_years)-1, key="single_sub_exp_year")

                        df_pref_sub_e_y = df_pref_exp[df_pref_exp['年度'].astype(str) == str(selected_sub_exp_year_single)].groupby(group_c_cols_e, as_index=False)[selected_sub_exp_item].sum()
                        df_pref_sub_e_y['人口_num'] = get_population_series(df_pref_sub_e_y, df_overview, selected_sub_exp_year_single)

                        val_s = pd.to_numeric(df_pref_sub_e_y[selected_sub_exp_item], errors='coerce').fillna(0)
                        pop_s = pd.to_numeric(df_pref_sub_e_y['人口_num'], errors='coerce').replace(0, np.nan)
                        df_pref_sub_e_y['1人当たり金額(千円)'] = (val_s / pop_s).round(2)

                        sub_exp_rank_mode = st.radio("比較表示モード", ["1人当たり金額（千円/人）", "総額（千円）"], horizontal=True, key="sub_exp_single_mode")
                        target_rank_col_e = '1人当たり金額(千円)' if sub_exp_rank_mode == "1人当たり金額（千円/人）" else selected_sub_exp_item

                        df_rank_sub_e = df_pref_sub_e_y.sort_values(target_rank_col_e, ascending=False).copy()
                        clean_selected_city = str(selected_city).strip()
                        df_rank_sub_e['表示色'] = df_rank_sub_e[c_city_col].apply(lambda x: '選択中の自治体' if clean_selected_city in str(x) else 'その他自治体')

                        fig_sub_exp_rank = px.bar(
                            df_rank_sub_e, x=c_city_col, y=target_rank_col_e, color='表示色', text=target_rank_col_e,
                            title=f"{scope_label}（{selected_sub_exp_year_single}年度）{sub_exp_item_name} {sub_exp_rank_mode} 比較",
                            color_discrete_map={'選択中の自治体': '#FF4B4B', 'その他自治体': '#1F77B4'},
                            custom_data=[c_pref_col if c_pref_col in df_rank_sub_e.columns else c_city_col, selected_sub_exp_item]
                        )
                        fig_sub_exp_rank.update_traces(texttemplate='%{text:,.1f}', textposition='outside')
                        st.plotly_chart(fig_sub_exp_rank, use_container_width=True, key="exp_sub2_single_chart")

                else:
                    st.info(f"💡 「{exp_parent_options[selected_exp_parent]}」には詳細な細分化データが含まれていないため、総額（合計）を比較表示します。")
                    avail_sub_exp_years = df_pref_exp['年度'].astype(str).unique()
                    selected_sub_exp_year_single = st.selectbox("比較年度を選択", avail_sub_exp_years, index=len(avail_sub_exp_years)-1, key="single_tot_exp_year")

                    df_pref_sub_e_y = df_pref_exp[df_pref_exp['年度'].astype(str) == str(selected_sub_exp_year_single)].groupby(group_c_cols_e, as_index=False)[selected_exp_parent].sum()
                    df_pref_sub_e_y['人口_num'] = get_population_series(df_pref_sub_e_y, df_overview, selected_sub_exp_year_single)

                    val_s = pd.to_numeric(df_pref_sub_e_y[selected_exp_parent], errors='coerce').fillna(0)
                    pop_s = pd.to_numeric(df_pref_sub_e_y['人口_num'], errors='coerce').replace(0, np.nan)
                    df_pref_sub_e_y['1人当たり金額(千円)'] = (val_s / pop_s).round(2)

                    sub_exp_rank_mode = st.radio("比較表示モード", ["1人当たり金額（千円/人）", "総額（千円）"], horizontal=True, key="sub_exp_tot_mode")
                    target_rank_col_e = '1人当たり金額(千円)' if sub_exp_rank_mode == "1人当たり金額（千円/人）" else selected_exp_parent

                    df_rank_sub_e = df_pref_sub_e_y.sort_values(target_rank_col_e, ascending=False).copy()
                    clean_selected_city = str(selected_city).strip()
                    df_rank_sub_e['表示色'] = df_rank_sub_e[c_city_col].apply(lambda x: '選択中の自治体' if clean_selected_city in str(x) else 'その他自治体')

                    fig_sub_exp_rank = px.bar(
                        df_rank_sub_e, x=c_city_col, y=target_rank_col_e, color='表示色', text=target_rank_col_e,
                        title=f"{scope_label}（{selected_sub_exp_year_single}年度）{exp_parent_options[selected_exp_parent]} {sub_exp_rank_mode} 比較",
                        color_discrete_map={'選択中の自治体': '#FF4B4B', 'その他自治体': '#1F77B4'},
                        custom_data=[c_pref_col if c_pref_col in df_rank_sub_e.columns else c_city_col, selected_exp_parent]
                    )
                    fig_sub_exp_rank.update_traces(texttemplate='%{text:,.1f}', textposition='outside')
                    st.plotly_chart(fig_sub_exp_rank, use_container_width=True, key="exp_sub_tot_single_chart")

            with subtab_exp_rank:
                st.subheader("🏆 全項目一括可視化 & 自治体力点分析（性質別）")
                df_pref_exp_all = get_comparison_df(df_exp_nature)
                avail_exp_years = sorted(df_pref_exp_all['年度'].astype(str).unique()) if not df_pref_exp_all.empty else []
                
                if avail_exp_years:
                    sel_exp_rank_year = st.selectbox("分析年度を選択", avail_exp_years, index=len(avail_exp_years)-1, key="exp_rank_tab_year")
                    c_city_col = '団体名' if '団体名' in df_pref_exp_all.columns else ('市町村名' if '市町村名' in df_pref_exp_all.columns else df_pref_exp_all.columns[0])
                    c_pref_col = '都道府県' if '都道府県' in df_pref_exp_all.columns else '都道府県名'
                    group_er_cols = [c for c in [c_pref_col, c_city_col] if c in df_pref_exp_all.columns]

                    exp_matrix_data = []
                    for cat_col in main_categories:
                        cat_name = clean_col_label(cat_col)
                        df_calc_tmp = df_pref_exp_all[df_pref_exp_all['年度'].astype(str) == str(sel_exp_rank_year)].groupby(group_er_cols, as_index=False)[cat_col].sum()
                        df_calc_tmp['人口_num'] = get_population_series(df_calc_tmp, df_overview, sel_exp_rank_year)
                        df_calc_valid = df_calc_tmp[df_calc_tmp['人口_num'] > 0].copy()
                        df_calc_valid['pc_val'] = (df_calc_valid[cat_col] / df_calc_valid['人口_num']).round(1)
                        cat_avg = df_calc_valid['pc_val'].mean()
                        
                        for _, row in df_calc_valid.iterrows():
                            c_name = row[c_city_col]
                            pc_val = row['pc_val']
                            ratio = round(pc_val / cat_avg, 2) if cat_avg > 0 else 1.0
                            exp_matrix_data.append({'自治体名': c_name, '項目名': cat_name, '1人当たり金額': pc_val, '対平均倍率': ratio})

                    if exp_matrix_data:
                        df_exp_mat = pd.DataFrame(exp_matrix_data)
                        exp_item_summary = []
                        for item_name, group in df_exp_mat.groupby('項目名'):
                            top_row = group.sort_values('1人当たり金額', ascending=False).iloc[0]
                            worst_row = group.sort_values('1人当たり金額', ascending=True).iloc[0]
                            avg_val = group['1人当たり金額'].mean()
                            exp_item_summary.append({
                                '性質別項目': item_name,
                                'トップ自治体名': top_row['自治体名'],
                                'トップ1人当たり金額': top_row['1人当たり金額'],
                                '🥇 トップ自治体': f"{top_row['自治体名']}（{top_row['1人当たり金額']:,.1f} 千円/人）",
                                '⚓ ワースト自治体': f"{worst_row['自治体名']}（{worst_row['1人当たり金額']:,.1f} 千円/人）",
                                '地域平均': f"{avg_val:,.1f} 千円/人"
                            })
                        
                        df_exp_item_summary = pd.DataFrame(exp_item_summary)
                        cards_per_row = 4
                        cols = st.columns(cards_per_row)
                        for i, (_, row) in enumerate(df_exp_item_summary.iterrows()):
                            col = cols[i % cards_per_row]
                            with col:
                                st.metric(label=f"📌 {row['性質別項目']} トップ", value=row['トップ自治体名'], delta=f"{row['トップ1人当たり金額']:,.1f} 千円/人")

                        st.markdown("##### 📋 全性質別項目 トップ・ワースト比較表")
                        st.dataframe(df_exp_item_summary[['性質別項目', '🥇 トップ自治体', '⚓ ワースト自治体', '地域平均']], use_container_width=True, hide_index=True)
                        st.markdown("---")

                        df_ratio_pivot = df_exp_mat.pivot(index='自治体名', columns='項目名', values='対平均倍率')
                        st.markdown(f"#### 🗺️ {scope_label} 性質別歳出 特化度ヒートマップ（{sel_exp_rank_year}年度）")

                        fig_exp_heatmap = px.imshow(
                            df_ratio_pivot, labels=dict(x="性質別支出項目", y="自治体名", color="対平均倍率"),
                            x=df_ratio_pivot.columns, y=df_ratio_pivot.index,
                            color_continuous_scale="Reds", aspect="auto", text_auto=".2f"
                        )
                        fig_exp_heatmap.update_xaxes(side="top")
                        fig_exp_heatmap.update_layout(height=max(450, len(df_ratio_pivot) * 30))
                        st.plotly_chart(fig_exp_heatmap, use_container_width=True, key="exp_heatmap")

                        clean_sel_city = str(selected_city).strip()
                        df_sel_city_exp = df_exp_mat[df_exp_mat['自治体名'].str.contains(clean_sel_city, regex=False)].sort_values('対平均倍率', ascending=True)

                        if not df_sel_city_exp.empty:
                            st.markdown(f"#### 📍 **{selected_city}** の全性質別項目 ポジショニング（対平均倍率）")
                            fig_sel_exp_bar = px.bar(
                                df_sel_city_exp, x='対平均倍率', y='項目名', orientation='h',
                                text='対平均倍率', color='対平均倍率', color_continuous_scale='Reds', custom_data=['1人当たり金額']
                            )
                            fig_sel_exp_bar.add_vline(x=1.0, line_dash="dash", line_color="black", annotation_text="地域平均 (1.00倍)")
                            fig_sel_exp_bar.update_traces(texttemplate='%{text:.2f} 倍', textposition='outside')
                            fig_sel_exp_bar.update_layout(xaxis_title="対平均倍率（1.0以上で高配分）", yaxis_title="支出項目", height=400)
                            st.plotly_chart(fig_sel_exp_bar, use_container_width=True, key="sel_city_exp_bar")

# ==========================================
# メニュー4: 目的別歳出
# ==========================================
elif menu == "目的別歳出":
    st.markdown("### 目的別歳出の推移と分析")
    
    purp_kw_map = {
        '議会費': ['議会費'], '総務費': ['総務費'], '民生費': ['民生費'], '衛生費': ['衛生費'],
        '労働費': ['労働費'], '農林水産業費': ['農林水産'], '商工費': ['商工費'],
        '土木費': ['土木費'], '消防費': ['消防費'], '教育費': ['教育費'], '公債費': ['公債費']
    }

    main_purp_categories = []
    if not df_exp_purpose.empty:
        for label, kws in purp_kw_map.items():
            matched = [
                c for c in df_exp_purpose.columns 
                if any(kw in c for kw in kws) 
                and not any(ex in c for ex in ['1人当たり', 'パーセント', '%', '割合', '比率'])
            ]
            if matched:
                main_purp_categories.append(matched[0])

    purp_category_order = [clean_col_label(c) for c in main_purp_categories]

    tab_purp1, tab_purp_comp = st.tabs(["📈 自治体単体分析", "🏛️ 自治体間比較"])

    # --- 1. 単体分析 ---
    with tab_purp1:
        st.subheader("1. 目的別歳出の時系列推移（総額 vs 人口1人当たり）")
        
        # A. df_purp_city に詳細データが存在する場合
        if not df_purp_city.empty and main_purp_categories:
            group_cols_p = [c for c in ['都道府県', '団体名', '年度'] if c in df_purp_city.columns]
            df_plot_p_base = df_purp_city.groupby(group_cols_p, as_index=False)[main_purp_categories].sum()
            df_plot_p_base['目的別歳出合計'] = df_plot_p_base[main_purp_categories].sum(axis=1)
            df_plot_p_base['人口_num'] = get_population_series(df_plot_p_base, df_overview, "latest")

            # 「自治体間比較」と一致した項目名「💰 総額」「👥 1人当たり」に変更
            sub_purp_tot, sub_purp_pc = st.tabs(["💰 総額", "👥 1人当たり"])
            
            # --- 総額タブ ---
            with sub_purp_tot:
                df_melt_p = df_plot_p_base.melt(id_vars=['年度'], value_vars=main_purp_categories, var_name='項目_raw', value_name='金額')
                df_melt_p['項目名'] = df_melt_p['項目_raw'].apply(clean_col_label)
                df_melt_p = df_melt_p.groupby(['年度', '項目名'], as_index=False)['金額'].sum()

                year_totals = df_melt_p.groupby('年度')['金額'].transform('sum')
                df_melt_p['目的別歳出合計'] = year_totals
                df_melt_p['割合(%)'] = (df_melt_p['金額'] / df_melt_p['目的別歳出合計'].replace(0, np.nan) * 100).fillna(0).round(1)

                fig_p = px.bar(
                    df_melt_p, x='年度', y='金額', color='項目名', 
                    title=f"{selected_city} 目的別歳出（総額）", barmode='stack',
                    custom_data=['項目名', '割合(%)'],
                    category_orders={"項目名": purp_category_order}
                )
                fig_p.update_layout(yaxis_tickformat=",", yaxis_title="金額（千円）", legend_title_text="項目名")
                fig_p.update_traces(hovertemplate="<b>%{customdata[0]}</b><br>金額: %{y:,.0f} 千円<br>構成比: %{customdata[1]}%<extra></extra>")
                st.plotly_chart(fig_p, use_container_width=True, key="purp_tot_trend_chart")

            # --- 1人当たりタブ ---
            with sub_purp_pc:
                if '人口_num' in df_plot_p_base.columns and (df_plot_p_base['人口_num'] > 0).any():
                    df_pc_p_base = df_plot_p_base.copy()
                    pc_cols_p = []
                    for c in main_purp_categories:
                        pc_col_name = c + '_1人当たり'
                        df_pc_p_base[pc_col_name] = (df_pc_p_base[c] / df_pc_p_base['人口_num'].replace(0, np.nan)).round(2)
                        pc_cols_p.append(pc_col_name)

                    df_melt_p_pc = df_pc_p_base.melt(id_vars=['年度'], value_vars=pc_cols_p, var_name='項目_raw', value_name='1人当たり金額')
                    df_melt_p_pc['項目名'] = df_melt_p_pc['項目_raw'].apply(lambda x: clean_col_label(x.replace('_1人当たり', '')))
                    df_melt_p_pc = df_melt_p_pc.groupby(['年度', '項目名'], as_index=False)['1人当たり金額'].sum()

                    pc_year_totals = df_melt_p_pc.groupby('年度')['1人当たり金額'].transform('sum')
                    df_melt_p_pc['1人当たり目的別歳出合計'] = pc_year_totals
                    df_melt_p_pc['割合(%)'] = (df_melt_p_pc['1人当たり金額'] / df_melt_p_pc['1人当たり目的別歳出合計'].replace(0, np.nan) * 100).fillna(0).round(1)

                    fig_p_pc = px.bar(
                        df_melt_p_pc, x='年度', y='1人当たり金額', color='項目名', 
                        title=f"{selected_city} 目的別歳出（1人当たり）", barmode='stack',
                        custom_data=['項目名', '割合(%)'],
                        category_orders={"項目名": purp_category_order}
                    )
                    fig_p_pc.update_layout(yaxis_tickformat=",.1f", yaxis_title="1人当たり金額（千円/人）", legend_title_text="項目名")
                    fig_p_pc.update_traces(hovertemplate="<b>%{customdata[0]}</b><br>1人当たり金額: %{y:,.2f} 千円/人<br>構成比: %{customdata[1]}%<extra></extra>")
                    st.plotly_chart(fig_p_pc, use_container_width=True, key="purp_pc_trend_chart")

        # B. 詳細データが存在しない場合はメッセージのみ表示
        else:
            st.info(f"💡 **{selected_city}** の目的別歳出データはありません。")

        # --- 2. 自治体間比較 ---
        with tab_purp_comp:
            subtab_purp_tot, subtab_purp_pc, subtab_purp_sub, subtab_purp_rank = st.tabs(["💰 総額", "👥 1人当たり", "🔍 細分化項目比較（事業費内訳一括・個別）", "🏆 項目別ランキング・自治体力点分析"])

            with subtab_purp_tot:
                st.subheader(f"{scope_label} 目的別歳出比較（総額）")
                df_pref_purp = get_comparison_df(df_exp_purpose)
                if not df_pref_purp.empty:
                    comp_year_purp = st.selectbox("比較する年度を選択", df_pref_purp['年度'].astype(str).unique(), index=len(df_pref_purp['年度'].astype(str).unique())-1, key="comp_purp_year")
                    c_city_col = '団体名' if '団体名' in df_pref_purp.columns else ('市町村名' if '市町村名' in df_pref_purp.columns else df_pref_purp.columns[0])
                    c_pref_col = '都道府県' if '都道府県' in df_pref_purp.columns else '都道府県名'
                    group_c_cols = [c for c in [c_pref_col, c_city_col] if c in df_pref_purp.columns]

                    df_comp_p = df_pref_purp[df_pref_purp['年度'].astype(str) == str(comp_year_purp)].groupby(group_c_cols, as_index=False)[main_purp_categories].sum()
                    df_comp_p['目的別歳出合計'] = df_comp_p[main_purp_categories].sum(axis=1)
                    df_comp_p = df_comp_p.sort_values('目的別歳出合計', ascending=False)
                    sorted_cities_p = df_comp_p[c_city_col].tolist()

                    df_melt_cp = df_comp_p.melt(id_vars=group_c_cols + ['目的別歳出合計'], value_vars=main_purp_categories, var_name='項目_raw', value_name='金額')
                    df_melt_cp['項目名'] = df_melt_cp['項目_raw'].apply(clean_col_label)
                    df_melt_cp = df_melt_cp.groupby(group_c_cols + ['目的別歳出合計', '項目名'], as_index=False)['金額'].sum()
                    df_melt_cp['割合(%)'] = (df_melt_cp['金額'] / df_melt_cp['目的別歳出合計'].replace(0, np.nan) * 100).fillna(0).round(1)

                    fig_cp = px.bar(
                        df_melt_cp, x=c_city_col, y='金額', color='項目名', 
                        title=f"{scope_label}（{comp_year_purp}年度）目的別歳出比較（総額・大きい順）", barmode='stack',
                        custom_data=[c_pref_col if c_pref_col in df_melt_cp.columns else c_city_col, '項目名', '割合(%)'],
                        category_orders={"項目名": purp_category_order, c_city_col: sorted_cities_p}
                    )
                    fig_cp.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
                    st.plotly_chart(fig_cp, use_container_width=True, key="purp_tot_comp_chart")

            with subtab_purp_pc:
                st.subheader(f"{scope_label} 目的別歳出比較（人口1人当たり）")
                df_pref_purp = get_comparison_df(df_exp_purpose)
                if not df_pref_purp.empty:
                    comp_year_purp_pop = st.selectbox("比較する年度を選択", df_pref_purp['年度'].astype(str).unique(), index=len(df_pref_purp['年度'].astype(str).unique())-1, key="comp_purp_pop_year")
                    c_city_col = '団体名' if '団体名' in df_pref_purp.columns else ('市町村名' if '市町村名' in df_pref_purp.columns else df_pref_purp.columns[0])
                    c_pref_col = '都道府県' if '都道府県' in df_pref_purp.columns else '都道府県名'
                    group_c_cols = [c for c in [c_pref_col, c_city_col] if c in df_pref_purp.columns]

                    df_comp_p_pop = df_pref_purp[df_pref_purp['年度'].astype(str) == str(comp_year_purp_pop)].groupby(group_c_cols, as_index=False)[main_purp_categories].sum()
                    df_comp_p_pop['人口_num'] = get_population_series(df_comp_p_pop, df_overview, comp_year_purp_pop)
                    df_comp_p_pop = df_comp_p_pop[df_comp_p_pop['人口_num'] > 0].copy()
                    
                    pc_cols_p = []
                    for c in main_purp_categories:
                        pc_c = c + '_1人当たり'
                        df_comp_p_pop[pc_c] = (df_comp_p_pop[c] / df_comp_p_pop['人口_num']).round(2)
                        pc_cols_p.append(pc_c)

                    df_comp_p_pop['1人当たり目的別歳出合計'] = df_comp_p_pop[pc_cols_p].sum(axis=1)
                    df_comp_p_pop = df_comp_p_pop.sort_values('1人当たり目的別歳出合計', ascending=False)
                    sorted_cities_p_pop = df_comp_p_pop[c_city_col].tolist()

                    df_melt_cp_pc = df_comp_p_pop.melt(id_vars=group_c_cols + ['1人当たり目的別歳出合計'], value_vars=pc_cols_p, var_name='項目_raw', value_name='1人当たり金額')
                    df_melt_cp_pc['項目名'] = df_melt_cp_pc['項目_raw'].apply(lambda x: clean_col_label(x.replace('_1人当たり', '')))
                    df_melt_cp_pc = df_melt_cp_pc.groupby(group_c_cols + ['1人当たり目的別歳出合計', '項目名'], as_index=False)['1人当たり金額'].sum()
                    df_melt_cp_pc['割合(%)'] = (df_melt_cp_pc['1人当たり金額'] / df_melt_cp_pc['1人当たり目的別歳出合計'].replace(0, np.nan) * 100).fillna(0).round(1)

                    fig_pc_p = px.bar(
                        df_melt_cp_pc, x=c_city_col, y='1人当たり金額', color='項目名', 
                        title=f"{scope_label}（{comp_year_purp_pop}年度）自治体別 1人当たり目的別歳出比較（大きい順）", barmode='stack',
                        custom_data=[c_pref_col if c_pref_col in df_melt_cp_pc.columns else c_city_col, '項目名', '割合(%)'],
                        category_orders={"項目名": purp_category_order, c_city_col: sorted_cities_p_pop}
                    )
                    fig_pc_p.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
                    st.plotly_chart(fig_pc_p, use_container_width=True, key="purp_pc_comp_chart")

            with subtab_purp_sub:
                st.subheader("🔍 目的別歳出 細分化事業内訳の比較分析")
                df_pref_purp = get_comparison_df(df_exp_purpose)
                purp_parent_options = {c: clean_col_label(c) for c in main_purp_categories}
                selected_purp_parent = st.selectbox("分析する歳出の大項目（目的別）を選択", list(purp_parent_options.keys()), format_func=lambda x: purp_parent_options[x], key="sub_purp_parent")
                
                prefix_purp = selected_purp_parent.replace('_合計', '') + '_'
                sub_purp_cols = [c for c in df_exp_purpose.columns if c.startswith(prefix_purp) and c != selected_purp_parent and '小計' not in c]
                if not sub_purp_cols and selected_purp_parent in df_exp_purpose.columns:
                    sub_purp_cols = [selected_purp_parent]

                if sub_purp_cols:
                    sub_purp_labels = {c: (clean_col_label(c) if c == selected_purp_parent else c.replace(prefix_purp, '')) for c in sub_purp_cols}
                    if len(sub_purp_cols) == 1 and sub_purp_cols[0] == selected_purp_parent:
                        st.info(f"💡 「{clean_col_label(selected_purp_parent)}」には細分化内訳データがないため、総額データで比較表示しています。")

                    sub_purp_mode1, sub_purp_mode2 = st.tabs(["📊 傘下全項目の一括自治体比較", "🔍 特定の細分化項目の個別比較"])
                    c_city_col = '団体名' if '団体名' in df_pref_purp.columns else ('市町村名' if '市町村名' in df_pref_purp.columns else df_pref_purp.columns[0])
                    c_pref_col = '都道府県' if '都道府県' in df_pref_purp.columns else '都道府県名'
                    group_c_cols = [c for c in [c_pref_col, c_city_col] if c in df_pref_purp.columns]

                    with sub_purp_mode1:
                        avail_sub_purp_years = df_pref_purp['年度'].astype(str).unique()
                        selected_sub_purp_year = st.selectbox("比較年度を選択", avail_sub_purp_years, index=len(avail_sub_purp_years)-1, key="sub_purp_year_select")
                        unit_mode_p = st.radio("表示単位", ["1人当たり金額（千円/人）", "総額（千円）"], horizontal=True, key="unit_purp_sub")

                        df_pref_sub_p_y = df_pref_purp[df_pref_purp['年度'].astype(str) == str(selected_sub_purp_year)].groupby(group_c_cols, as_index=False)[sub_purp_cols].sum()
                        df_pref_sub_p_y['人口_num'] = get_population_series(df_pref_sub_p_y, df_overview, selected_sub_purp_year)

                        if unit_mode_p == "1人当たり金額（千円/人）":
                            plot_sub_cols_p = []
                            for c in sub_purp_cols:
                                pc_c = c + '_1人当たり'
                                val_s = pd.to_numeric(df_pref_sub_p_y[c], errors='coerce').fillna(0)
                                pop_s = pd.to_numeric(df_pref_sub_p_y['人口_num'], errors='coerce').replace(0, np.nan)
                                df_pref_sub_p_y[pc_c] = (val_s / pop_s).round(2)
                                plot_sub_cols_p.append(pc_c)
                            
                            df_pref_sub_p_y['内訳合計_calc'] = df_pref_sub_p_y[plot_sub_cols_p].sum(axis=1)
                            df_pref_sub_p_y = df_pref_sub_p_y.sort_values('内訳合計_calc', ascending=False)
                            sorted_cities_sub1 = df_pref_sub_p_y[c_city_col].tolist()

                            df_melt_all_sub_p = df_pref_sub_p_y.melt(id_vars=group_c_cols + ['内訳合計_calc'], value_vars=plot_sub_cols_p, var_name='項目_raw', value_name='数値')
                            df_melt_all_sub_p['内訳名'] = df_melt_all_sub_p['項目_raw'].apply(lambda x: sub_purp_labels.get(x.replace('_1人当たり', ''), clean_col_label(x)))
                            df_melt_all_sub_p = df_melt_all_sub_p.groupby(group_c_cols + ['内訳合計_calc', '内訳名'], as_index=False)['数値'].sum()
                            df_melt_all_sub_p['割合(%)'] = (df_melt_all_sub_p['数値'] / df_melt_all_sub_p['内訳合計_calc'].replace(0, np.nan) * 100).fillna(0).round(1)

                            fig_all_sub_p = px.bar(
                                df_melt_all_sub_p, x=c_city_col, y='数値', color='内訳名',
                                title=f"{scope_label}（{selected_sub_purp_year}年度）{purp_parent_options[selected_purp_parent]} 事業内訳一括比較（1人当たり）",
                                barmode='stack', custom_data=[c_pref_col if c_pref_col in df_melt_all_sub_p.columns else c_city_col, '内訳名', '割合(%)'],
                                category_orders={c_city_col: sorted_cities_sub1}
                            )
                            fig_all_sub_p.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
                            st.plotly_chart(fig_all_sub_p, use_container_width=True, key="purp_sub_pc_chart")
                        else:
                            df_pref_sub_p_y['内訳合計_calc'] = df_pref_sub_p_y[sub_purp_cols].sum(axis=1)
                            df_pref_sub_p_y = df_pref_sub_p_y.sort_values('内訳合計_calc', ascending=False)
                            sorted_cities_sub2 = df_pref_sub_p_y[c_city_col].tolist()

                            df_melt_all_sub_p = df_pref_sub_p_y.melt(id_vars=group_c_cols + ['内訳合計_calc'], value_vars=sub_purp_cols, var_name='項目_raw', value_name='数値')
                            df_melt_all_sub_p['内訳名'] = df_melt_all_sub_p['項目_raw'].apply(lambda x: sub_purp_labels.get(x, clean_col_label(x)))
                            df_melt_all_sub_p = df_melt_all_sub_p.groupby(group_c_cols + ['内訳合計_calc', '内訳名'], as_index=False)['数値'].sum()
                            df_melt_all_sub_p['割合(%)'] = (df_melt_all_sub_p['数値'] / df_melt_all_sub_p['内訳合計_calc'].replace(0, np.nan) * 100).fillna(0).round(1)

                            fig_all_sub_p = px.bar(
                                df_melt_all_sub_p, x=c_city_col, y='数値', color='内訳名',
                                title=f"{scope_label}（{selected_sub_purp_year}年度）{purp_parent_options[selected_purp_parent]} 事業内訳一括比較（総額）",
                                barmode='stack', custom_data=[c_pref_col if c_pref_col in df_melt_all_sub_p.columns else c_city_col, '内訳名', '割合(%)'],
                                category_orders={c_city_col: sorted_cities_sub2}
                            )
                            fig_all_sub_p.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
                            st.plotly_chart(fig_all_sub_p, use_container_width=True, key="purp_sub_tot_chart")

                    with sub_purp_mode2:
                        selected_sub_purp_item = st.selectbox("比較する細分化項目を選択", list(sub_purp_labels.keys()), format_func=lambda x: sub_purp_labels[x], key="single_sub_purp_item")
                        sub_purp_item_name = sub_purp_labels[selected_sub_purp_item]
                        avail_sub_purp_years = df_pref_purp['年度'].astype(str).unique()
                        selected_sub_purp_year_single = st.selectbox("比較年度を選択", avail_sub_purp_years, index=len(avail_sub_purp_years)-1, key="single_sub_purp_year")

                        df_pref_sub_p_y = df_pref_purp[df_pref_purp['年度'].astype(str) == str(selected_sub_purp_year_single)].groupby(group_c_cols, as_index=False)[selected_sub_purp_item].sum()
                        df_pref_sub_p_y['人口_num'] = get_population_series(df_pref_sub_p_y, df_overview, selected_sub_purp_year_single)

                        val_s = pd.to_numeric(df_pref_sub_p_y[selected_sub_purp_item], errors='coerce').fillna(0)
                        pop_s = pd.to_numeric(df_pref_sub_p_y['人口_num'], errors='coerce').replace(0, np.nan)
                        df_pref_sub_p_y['1人当たり金額(千円)'] = (val_s / pop_s).round(2)

                        sub_purp_rank_mode = st.radio("比較表示モード", ["1人当たり金額（千円/人）", "総額（千円）"], horizontal=True, key="sub_purp_single_mode")
                        target_rank_col_p = '1人当たり金額(千円)' if sub_purp_rank_mode == "1人当たり金額（千円/人）" else selected_sub_purp_item

                        df_rank_sub_p = df_pref_sub_p_y.sort_values(target_rank_col_p, ascending=False).copy()
                        clean_selected_city = str(selected_city).strip()
                        df_rank_sub_p['表示色'] = df_rank_sub_p[c_city_col].apply(lambda x: '選択中の自治体' if clean_selected_city in str(x) else 'その他自治体')

                        fig_sub_purp_rank = px.bar(
                            df_rank_sub_p, x=c_city_col, y=target_rank_col_p, color='表示色', text=target_rank_col_p,
                            title=f"{scope_label}（{selected_sub_purp_year_single}年度）{sub_purp_item_name} {sub_purp_rank_mode} 比較",
                            color_discrete_map={'選択中の自治体': '#FF4B4B', 'その他自治体': '#1F77B4'},
                            custom_data=[c_pref_col if c_pref_col in df_rank_sub_p.columns else c_city_col, selected_sub_purp_item]
                        )
                        fig_sub_purp_rank.update_traces(texttemplate='%{text:,.1f}', textposition='outside')
                        st.plotly_chart(fig_sub_purp_rank, use_container_width=True, key="purp_sub2_single_chart")
                else:
                    st.info("選択された項目には詳細な事業内訳データが含まれていません。")

            with subtab_purp_rank:
                st.subheader("🏆 全項目一括可視化 & 自治体力点分析（目的別）")
                df_pref_purp_all = get_comparison_df(df_exp_purpose)
                avail_purp_years = sorted(df_pref_purp_all['年度'].astype(str).unique()) if not df_pref_purp_all.empty else []
                
                if avail_purp_years:
                    sel_purp_rank_year = st.selectbox("分析年度を選択", avail_purp_years, index=len(avail_purp_years)-1, key="purp_rank_tab_year")
                    c_city_col = '団体名' if '団体名' in df_pref_purp_all.columns else ('市町村名' if '市町村名' in df_pref_purp_all.columns else df_pref_purp_all.columns[0])
                    c_pref_col = '都道府県' if '都道府県' in df_pref_purp_all.columns else '都道府県名'
                    group_r_cols = [c for c in [c_pref_col, c_city_col] if c in df_pref_purp_all.columns]

                    purp_matrix_data = []
                    for cat_col in main_purp_categories:
                        cat_name = clean_col_label(cat_col)
                        df_calc_tmp = df_pref_purp_all[df_pref_purp_all['年度'].astype(str) == str(sel_purp_rank_year)].groupby(group_r_cols, as_index=False)[cat_col].sum()
                        df_calc_tmp['人口_num'] = get_population_series(df_calc_tmp, df_overview, sel_purp_rank_year)
                        df_calc_valid = df_calc_tmp[df_calc_tmp['人口_num'] > 0].copy()
                        df_calc_valid['pc_val'] = (df_calc_valid[cat_col] / df_calc_valid['人口_num']).round(1)
                        cat_avg = df_calc_valid['pc_val'].mean()
                        
                        for _, row in df_calc_valid.iterrows():
                            c_name = row[c_city_col]
                            pc_val = row['pc_val']
                            ratio = round(pc_val / cat_avg, 2) if cat_avg > 0 else 1.0
                            purp_matrix_data.append({'自治体名': c_name, '項目名': cat_name, '1人当たり金額': pc_val, '対平均倍率': ratio})

                    if purp_matrix_data:
                        df_purp_mat = pd.DataFrame(purp_matrix_data)
                        purp_item_summary = []
                        for item_name, group in df_purp_mat.groupby('項目名'):
                            top_row = group.sort_values('1人当たり金額', ascending=False).iloc[0]
                            worst_row = group.sort_values('1人当たり金額', ascending=True).iloc[0]
                            avg_val = group['1人当たり金額'].mean()
                            purp_item_summary.append({
                                '事業・目的項目': item_name,
                                'トップ自治体名': top_row['自治体名'],
                                'トップ1人当たり金額': top_row['1人当たり金額'],
                                '🥇 トップ自治体': f"{top_row['自治体名']}（{top_row['1人当たり金額']:,.1f} 千円/人）",
                                '⚓ ワースト自治体': f"{worst_row['自治体名']}（{worst_row['1人当たり金額']:,.1f} 千円/人）",
                                '地域平均': f"{avg_val:,.1f} 千円/人"
                            })
                        
                        df_purp_item_summary = pd.DataFrame(purp_item_summary)
                        cards_per_row = 4
                        cols_p = st.columns(cards_per_row)
                        for i, (_, row) in enumerate(df_purp_item_summary.iterrows()):
                            col = cols_p[i % cards_per_row]
                            with col:
                                st.metric(label=f"📌 {row['事業・目的項目']} トップ", value=row['トップ自治体名'], delta=f"{row['トップ1人当たり金額']:,.1f} 千円/人")

                        st.markdown("##### 📋 全目的別項目 トップ・ワースト比較表")
                        st.dataframe(df_purp_item_summary[['事業・目的項目', '🥇 トップ自治体', '⚓ ワースト自治体', '地域平均']], use_container_width=True, hide_index=True)
                        st.markdown("---")

                        df_purp_ratio_pivot = df_purp_mat.pivot(index='自治体名', columns='項目名', values='対平均倍率')
                        st.markdown(f"#### 🗺️ {scope_label} 目的別歳出 特化度ヒートマップ（{sel_purp_rank_year}年度）")

                        fig_purp_heatmap = px.imshow(
                            df_purp_ratio_pivot, labels=dict(x="目的別支出項目", y="自治体名", color="対平均倍率"),
                            x=df_purp_ratio_pivot.columns, y=df_purp_ratio_pivot.index,
                            color_continuous_scale="Reds", aspect="auto", text_auto=".2f"
                        )
                        fig_purp_heatmap.update_xaxes(side="top")
                        fig_purp_heatmap.update_layout(height=max(450, len(df_purp_ratio_pivot) * 30))
                        st.plotly_chart(fig_purp_heatmap, use_container_width=True, key="purp_heatmap")

                        clean_sel_city = str(selected_city).strip()
                        df_sel_city_purp = df_purp_mat[df_purp_mat['自治体名'].str.contains(clean_sel_city, regex=False)].sort_values('対平均倍率', ascending=True)

                        if not df_sel_city_purp.empty:
                            st.markdown(f"#### 📍 **{selected_city}** の全目的別項目 支出力点ポジショニング（対平均倍率）")
                            fig_sel_purp_bar = px.bar(
                                df_sel_city_purp, x='対平均倍率', y='項目名', orientation='h',
                                text='対平均倍率', color='対平均倍率', color_continuous_scale='Reds', custom_data=['1人当たり金額']
                            )
                            fig_sel_purp_bar.add_vline(x=1.0, line_dash="dash", line_color="black", annotation_text="地域平均 (1.00倍)")
                            fig_sel_purp_bar.update_traces(texttemplate='%{text:.2f} 倍', textposition='outside')
                            fig_sel_purp_bar.update_layout(xaxis_title="対平均倍率（1.0以上で重点投資）", yaxis_title="事業項目", height=400)
                            st.plotly_chart(fig_sel_purp_bar, use_container_width=True, key="sel_city_purp_bar")

# ==========================================
# メニュー5: 地方債・基金
# ==========================================
elif menu == "地方債・基金":
    st.markdown("### 地方債・積立金（基金）現在高の推移と分析")
    
    if not df_bonds.empty:
        tab_bonds1, tab_bonds_comp = st.tabs(["📈 自治体単体分析", "🏛️ 自治体間比較"])

        with tab_bonds1:
            st.subheader("1. 地方債・基金の推移")
            if not df_bonds_city.empty:
                df_plot_b = df_bonds_city.copy()
                fig_b = go.Figure()
                if '地方債現在高_合計' in df_plot_b.columns:
                    fig_b.add_trace(go.Scatter(x=df_plot_b['年度'], y=df_plot_b['地方債現在高_合計'], mode='lines+markers', name='地方債現在高', line=dict(color='red', width=3)))
                if '積立金現在高_合計' in df_plot_b.columns:
                    fig_b.add_trace(go.Scatter(x=df_plot_b['年度'], y=df_plot_b['積立金現在高_合計'], mode='lines+markers', name='積立金現在高（基金）', line=dict(color='green', width=3)))
                fig_b.update_layout(title=f"{selected_city} 地方債現在高 vs 積立金現在高の推移", xaxis_title="年度", yaxis_title="金額（千円）", yaxis_tickformat=",")
                st.plotly_chart(fig_b, use_container_width=True, key="bonds_trend_chart")
            else:
                st.info("選択された自治体の地方債・基金データが存在しません。")

        with tab_bonds_comp:
            subtab_bonds_tot, subtab_bonds_pc, subtab_bonds_sub = st.tabs(["💰 総額", "👥 1人当たり", "🔍 細分化項目比較（基金・繰出金等）"])

            with subtab_bonds_tot:
                st.subheader(f"{scope_label} 地方債・積立金比較（総額）")
                df_pref_bonds = get_comparison_df(df_bonds)
                if not df_pref_bonds.empty:
                    comp_year_bonds = st.selectbox("比較する年度を選択", df_pref_bonds['年度'].astype(str).unique(), index=len(df_pref_bonds['年度'].astype(str).unique())-1, key="comp_bonds_year")
                    df_comp_b = df_pref_bonds[df_pref_bonds['年度'].astype(str) == str(comp_year_bonds)].copy()
                    target_bonds_main = [c for c in ['地方債現在高_合計', '積立金現在高_合計'] if c in df_comp_b.columns]
                    if target_bonds_main:
                        df_comp_b = df_comp_b.sort_values(target_bonds_main[0], ascending=False)
                        df_melt_cb = df_comp_b.melt(id_vars=['都道府県', '団体名'], value_vars=target_bonds_main, var_name='項目_raw', value_name='金額')
                        df_melt_cb['項目名'] = df_melt_cb['項目_raw'].apply(clean_col_label)

                        fig_cb = px.bar(df_melt_cb, x='団体名', y='金額', color='項目名', title=f"{scope_label}（{comp_year_bonds}年度）地方債 vs 積立金比較（総額）", barmode='group')
                        fig_cb.update_layout(yaxis_tickformat=",", yaxis_title="金額（千円）")
                        st.plotly_chart(fig_cb, use_container_width=True, key="bonds_tot_comp_chart")

            with subtab_bonds_pc:
                st.subheader(f"{scope_label} 地方債・積立金比較（人口1人当たり）")
                df_pref_bonds = get_comparison_df(df_bonds)
                if not df_pref_bonds.empty:
                    comp_year_bonds_pop = st.selectbox("比較する年度を選択", df_pref_bonds['年度'].astype(str).unique(), index=len(df_pref_bonds['年度'].astype(str).unique())-1, key="comp_bonds_pop_year")
                    df_comp_b_pop = df_pref_bonds[df_pref_bonds['年度'].astype(str) == str(comp_year_bonds_pop)].copy()
                    df_comp_b_pop['人口_num'] = get_population_series(df_comp_b_pop, df_overview, comp_year_bonds_pop)
                    df_comp_b_pop = df_comp_b_pop[df_comp_b_pop['人口_num'] > 0].copy()

                    if not df_comp_b_pop.empty:
                        target_pc_bonds = []
                        if '地方債現在高_合計' in df_comp_b_pop.columns:
                            df_comp_b_pop['1人当たり地方債現在高'] = (df_comp_b_pop['地方債現在高_合計'] / df_comp_b_pop['人口_num']).round(2)
                            target_pc_bonds.append('1人当たり地方債現在高')
                        if '積立金現在高_合計' in df_comp_b_pop.columns:
                            df_comp_b_pop['1人当たり積立金現在高'] = (df_comp_b_pop['積立金現在高_合計'] / df_comp_b_pop['人口_num']).round(2)
                            target_pc_bonds.append('1人当たり積立金現在高')

                        if target_pc_bonds:
                            df_comp_b_pop = df_comp_b_pop.sort_values(target_pc_bonds[0], ascending=False)
                            df_melt_cb_pc = df_comp_b_pop.melt(id_vars=['都道府県', '団体名'], value_vars=target_pc_bonds, var_name='項目_raw', value_name='1人当たり金額')
                            df_melt_cb_pc['項目名'] = df_melt_cb_pc['項目_raw'].apply(clean_col_label)

                            fig_pc_b = px.bar(df_melt_cb_pc, x='団体名', y='1人当たり金額', color='項目名', title=f"{scope_label}（{comp_year_bonds_pop}年度）1人当たり地方債 vs 積立金比較", barmode='group')
                            fig_pc_b.update_layout(yaxis_tickformat=",.1f", yaxis_title="1人当たり金額（千円/人）")
                            st.plotly_chart(fig_pc_b, use_container_width=True, key="bonds_pc_comp_chart")

            with subtab_bonds_sub:
                st.subheader("🔍 地方債・基金・繰出金 細分化項目の比較分析")
                df_pref_bonds_comp = get_comparison_df(df_bonds)
                
                cand_bonds_parents = [c for c in df_bonds.columns if c.endswith('_合計') and c not in ['年度', '都道府県', '都市区分', '自治体種別', '団体名']]
                if not cand_bonds_parents:
                    cand_bonds_parents = [c for c in df_bonds.columns if c not in ['年度', '都道府県', '都市区分', '自治体種別', '団体名']]

                bonds_parent_options = {c: clean_col_label(c) for c in cand_bonds_parents}
                selected_bonds_parent = st.selectbox("分析する地方債・基金の大項目を選択", list(bonds_parent_options.keys()), format_func=lambda x: bonds_parent_options[x], key="sub_bonds_parent")
                
                prefix_bonds = selected_bonds_parent.replace('_合計', '') + '_'
                sub_bonds_cols = [c for c in df_bonds.columns if c.startswith(prefix_bonds) and c != selected_bonds_parent and '小計' not in c]
                
                c_city_col = '団体名' if '団体名' in df_pref_bonds_comp.columns else ('市町村名' if '市町村名' in df_pref_bonds_comp.columns else df_pref_bonds_comp.columns[0])
                c_pref_col = '都道府県' if '都道府県' in df_pref_bonds_comp.columns else '都道府県名'
                group_c_cols_b = [c for c in [c_pref_col, c_city_col] if c in df_pref_bonds_comp.columns]

                if sub_bonds_cols:
                    sub_bonds_labels = {c: c.replace(prefix_bonds, '') for c in sub_bonds_cols}
                    sub_bonds_mode1, sub_bonds_mode2 = st.tabs(["📊 傘下全項目の一括自治体比較", "🔍 特定の細分化項目の個別比較"])

                    with sub_bonds_mode1:
                        avail_sub_bonds_years = df_pref_bonds_comp['年度'].astype(str).unique()
                        selected_sub_bonds_year = st.selectbox("比較年度を選択", avail_sub_bonds_years, index=len(avail_sub_bonds_years)-1, key="sub_bonds_year_select")
                        unit_mode_b = st.radio("表示単位", ["1人当たり金額（千円/人）", "総額（千円）"], horizontal=True, key="unit_bonds_sub")

                        df_pref_sub_b_y = df_pref_bonds_comp[df_pref_bonds_comp['年度'].astype(str) == str(selected_sub_bonds_year)].groupby(group_c_cols_b, as_index=False)[sub_bonds_cols].sum()
                        df_pref_sub_b_y['人口_num'] = get_population_series(df_pref_sub_b_y, df_overview, selected_sub_bonds_year)

                        if unit_mode_b == "1人当たり金額（千円/人）":
                            plot_sub_cols_b = []
                            for c in sub_bonds_cols:
                                pc_c = c + '_1人当たり'
                                val_s = pd.to_numeric(df_pref_sub_b_y[c], errors='coerce').fillna(0)
                                pop_s = pd.to_numeric(df_pref_sub_b_y['人口_num'], errors='coerce').replace(0, np.nan)
                                df_pref_sub_b_y[pc_c] = (val_s / pop_s).round(2)
                                plot_sub_cols_b.append(pc_c)
                            
                            df_pref_sub_b_y['内訳合計_calc'] = df_pref_sub_b_y[plot_sub_cols_b].sum(axis=1)
                            df_pref_sub_b_y = df_pref_sub_b_y.sort_values('内訳合計_calc', ascending=False)
                            sorted_cities_bonds_sub1 = df_pref_sub_b_y[c_city_col].tolist()

                            df_melt_all_sub_b = df_pref_sub_b_y.melt(id_vars=group_c_cols_b + ['内訳合計_calc'], value_vars=plot_sub_cols_b, var_name='項目_raw', value_name='数値')
                            df_melt_all_sub_b['内訳名'] = df_melt_all_sub_b['項目_raw'].apply(lambda x: sub_bonds_labels.get(x.replace('_1人当たり', ''), clean_col_label(x)))
                            df_melt_all_sub_b = df_melt_all_sub_b.groupby(group_c_cols_b + ['内訳合計_calc', '内訳名'], as_index=False)['数値'].sum()
                            df_melt_all_sub_b['割合(%)'] = (df_melt_all_sub_b['数値'] / df_melt_all_sub_b['内訳合計_calc'].replace(0, np.nan) * 100).fillna(0).round(1)

                            fig_all_sub_b = px.bar(
                                df_melt_all_sub_b, x=c_city_col, y='数値', color='内訳名',
                                title=f"{scope_label}（{selected_sub_bonds_year}年度）{bonds_parent_options[selected_bonds_parent]} 内訳一括比較（1人当たり）",
                                barmode='stack', custom_data=[c_pref_col if c_pref_col in df_melt_all_sub_b.columns else c_city_col, '内訳名', '割合(%)'],
                                category_orders={c_city_col: sorted_cities_bonds_sub1}
                            )
                            fig_all_sub_b.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
                            st.plotly_chart(fig_all_sub_b, use_container_width=True, key="bonds_sub_pc_chart")
                        else:
                            df_pref_sub_b_y['内訳合計_calc'] = df_pref_sub_b_y[sub_bonds_cols].sum(axis=1)
                            df_pref_sub_b_y = df_pref_sub_b_y.sort_values('内訳合計_calc', ascending=False)
                            sorted_cities_bonds_sub2 = df_pref_sub_b_y[c_city_col].tolist()

                            df_melt_all_sub_b = df_pref_sub_b_y.melt(id_vars=group_c_cols_b + ['内訳合計_calc'], value_vars=sub_bonds_cols, var_name='項目_raw', value_name='数値')
                            df_melt_all_sub_b['内訳名'] = df_melt_all_sub_b['項目_raw'].apply(lambda x: sub_bonds_labels.get(x, clean_col_label(x)))
                            df_melt_all_sub_b = df_melt_all_sub_b.groupby(group_c_cols_b + ['内訳合計_calc', '内訳名'], as_index=False)['数値'].sum()
                            df_melt_all_sub_b['割合(%)'] = (df_melt_all_sub_b['数値'] / df_melt_all_sub_b['内訳合計_calc'].replace(0, np.nan) * 100).fillna(0).round(1)

                            fig_all_sub_b = px.bar(
                                df_melt_all_sub_b, x=c_city_col, y='数値', color='内訳名',
                                title=f"{scope_label}（{selected_sub_bonds_year}年度）{bonds_parent_options[selected_bonds_parent]} 内訳一括比較（総額）",
                                barmode='stack', custom_data=[c_pref_col if c_pref_col in df_melt_all_sub_b.columns else c_city_col, '内訳名', '割合(%)'],
                                category_orders={c_city_col: sorted_cities_bonds_sub2}
                            )
                            fig_all_sub_b.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
                            st.plotly_chart(fig_all_sub_b, use_container_width=True, key="bonds_sub_tot_chart")

                    with sub_bonds_mode2:
                        selected_sub_bonds_item = st.selectbox("比較する細分化項目を選択", list(sub_bonds_labels.keys()), format_func=lambda x: sub_bonds_labels[x], key="single_sub_bonds_item")
                        sub_bonds_item_name = sub_bonds_labels[selected_sub_bonds_item]
                        avail_sub_bonds_years = df_pref_bonds_comp['年度'].astype(str).unique()
                        selected_sub_bonds_year_single = st.selectbox("比較年度を選択", avail_sub_bonds_years, index=len(avail_sub_bonds_years)-1, key="single_sub_bonds_year")

                        df_pref_sub_b_y = df_pref_bonds_comp[df_pref_bonds_comp['年度'].astype(str) == str(selected_sub_bonds_year_single)].groupby(group_c_cols_b, as_index=False)[selected_sub_bonds_item].sum()
                        df_pref_sub_b_y['人口_num'] = get_population_series(df_pref_sub_b_y, df_overview, selected_sub_bonds_year_single)

                        val_s = pd.to_numeric(df_pref_sub_b_y[selected_sub_bonds_item], errors='coerce').fillna(0)
                        pop_s = pd.to_numeric(df_pref_sub_b_y['人口_num'], errors='coerce').replace(0, np.nan)
                        df_pref_sub_b_y['1人当たり金額(千円)'] = (val_s / pop_s).round(2)

                        sub_bonds_rank_mode = st.radio("比較表示モード", ["1人当たり金額（千円/人）", "総額（千円）"], horizontal=True, key="sub_bonds_single_mode")
                        target_rank_col_b = '1人当たり金額(千円)' if sub_bonds_rank_mode == "1人当たり金額（千円/人）" else selected_sub_bonds_item

                        df_rank_sub_b = df_pref_sub_b_y.sort_values(target_rank_col_b, ascending=False).copy()
                        clean_selected_city = str(selected_city).strip()
                        df_rank_sub_b['表示色'] = df_rank_sub_b[c_city_col].apply(lambda x: '選択中の自治体' if clean_selected_city in str(x) else 'その他自治体')

                        fig_sub_bonds_rank = px.bar(
                            df_rank_sub_b, x=c_city_col, y=target_rank_col_b, color='表示色', text=target_rank_col_b,
                            title=f"{scope_label}（{selected_sub_bonds_year_single}年度）{sub_bonds_item_name} {sub_bonds_rank_mode} 比較",
                            color_discrete_map={'選択中の自治体': '#FF4B4B', 'その他自治体': '#1F77B4'},
                            custom_data=[c_pref_col if c_pref_col in df_rank_sub_b.columns else c_city_col, selected_sub_bonds_item]
                        )
                        fig_sub_bonds_rank.update_traces(texttemplate='%{text:,.1f}', textposition='outside')
                        st.plotly_chart(fig_sub_bonds_rank, use_container_width=True, key="bonds_sub2_single_chart")

                else:
                    st.info(f"💡 「{bonds_parent_options[selected_bonds_parent]}」には詳細な細分化データが含まれていないため、総額（合計）を比較表示します。")
                    avail_sub_bonds_years = df_pref_bonds_comp['年度'].astype(str).unique()
                    selected_sub_bonds_year_single = st.selectbox("比較年度を選択", avail_sub_bonds_years, index=len(avail_sub_bonds_years)-1, key="single_tot_bonds_year")

                    df_pref_sub_b_y = df_pref_bonds_comp[df_pref_bonds_comp['年度'].astype(str) == str(selected_sub_bonds_year_single)].groupby(group_c_cols_b, as_index=False)[selected_bonds_parent].sum()
                    df_pref_sub_b_y['人口_num'] = get_population_series(df_pref_sub_b_y, df_overview, selected_sub_bonds_year_single)

                    val_s = pd.to_numeric(df_pref_sub_b_y[selected_bonds_parent], errors='coerce').fillna(0)
                    pop_s = pd.to_numeric(df_pref_sub_b_y['人口_num'], errors='coerce').replace(0, np.nan)
                    df_pref_sub_b_y['1人当たり金額(千円)'] = (val_s / pop_s).round(2)

                    sub_bonds_rank_mode = st.radio("比較表示モード", ["1人当たり金額（千円/人）", "総額（千円）"], horizontal=True, key="sub_bonds_tot_mode")
                    target_rank_col_b = '1人当たり金額(千円)' if sub_bonds_rank_mode == "1人当たり金額（千円/人）" else selected_bonds_parent

                    df_rank_sub_b = df_pref_sub_b_y.sort_values(target_rank_col_b, ascending=False).copy()
                    clean_selected_city = str(selected_city).strip()
                    df_rank_sub_b['表示色'] = df_rank_sub_b[c_city_col].apply(lambda x: '選択中の自治体' if clean_selected_city in str(x) else 'その他自治体')

                    fig_sub_bonds_rank = px.bar(
                        df_rank_sub_b, x=c_city_col, y=target_rank_col_b, color='表示色', text=target_rank_col_b,
                        title=f"{scope_label}（{selected_sub_bonds_year_single}年度）{bonds_parent_options[selected_bonds_parent]} {sub_bonds_rank_mode} 比較",
                        color_discrete_map={'選択中の自治体': '#FF4B4B', 'その他自治体': '#1F77B4'},
                        custom_data=[c_pref_col if c_pref_col in df_rank_sub_b.columns else c_city_col, selected_bonds_parent]
                    )
                    fig_sub_bonds_rank.update_traces(texttemplate='%{text:,.1f}', textposition='outside')
                    st.plotly_chart(fig_sub_bonds_rank, use_container_width=True, key="bonds_sub_tot_single_chart")