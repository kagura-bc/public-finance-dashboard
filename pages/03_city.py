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

# --- フィルター処理関数 ---
def filter_by_city(df, pref, city):
    if not df.empty and '団体名' in df.columns:
        if pref != "全国" and '都道府県' in df.columns:
            return df[(df['都道府県'] == pref) & (df['団体名'] == city)].sort_values('年度', key=lambda x: x.astype(str))
        else:
            return df[df['団体名'] == city].sort_values('年度', key=lambda x: x.astype(str))
    return df

def get_comparison_df(df):
    if df.empty:
        return df
    res = df
    if selected_type != "すべて" and '都市区分' in res.columns:
        res = res[res['都市区分'] == selected_type]
    if selected_pref != "全国" and '都道府県' in res.columns:
        res = res[res['都道府県'] == selected_pref]
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
def get_population_series(df_target, df_ov, target_year):
    pop_col = get_population_col(df_ov)
    if not pop_col or df_ov.empty:
        return pd.Series(np.nan, index=df_target.index)
    
    has_pref = '都道府県' in df_target.columns and '都道府県' in df_ov.columns
    
    if has_pref:
        df_ov_y = df_ov[df_ov['年度'].astype(str) == str(target_year)]
        pop_map_year = df_ov_y.drop_duplicates(subset=['都道府県', '団体名']).set_index(['都道府県', '団体名'])[pop_col].to_dict() if not df_ov_y.empty and pop_col in df_ov_y.columns else {}
        
        df_ov_latest = df_ov.sort_values('年度', key=lambda x: x.astype(str)).groupby(['都道府県', '団体名']).last().reset_index() if not df_ov.empty and pop_col in df_ov.columns else pd.DataFrame()
        pop_map_latest = df_ov_latest.set_index(['都道府県', '団体名'])[pop_col].to_dict() if not df_ov_latest.empty and pop_col in df_ov_latest.columns else {}
        
        target_idx = pd.MultiIndex.from_frame(df_target[['都道府県', '団体名']])
        s_year = pd.Series(target_idx.map(pop_map_year), index=df_target.index)
        s_latest = pd.Series(target_idx.map(pop_map_latest), index=df_target.index)
        pop_series = s_year.fillna(s_latest)
    else:
        df_ov_y = df_ov[df_ov['年度'].astype(str) == str(target_year)]
        pop_dict_year = df_ov_y.drop_duplicates(subset=['団体名']).set_index('団体名')[pop_col].to_dict() if not df_ov_y.empty and pop_col in df_ov_y.columns else {}
        
        df_ov_latest = df_ov.sort_values('年度', key=lambda x: x.astype(str)).groupby('団体名').last().reset_index() if not df_ov.empty and pop_col in df_ov.columns else pd.DataFrame()
        pop_dict_latest = df_ov_latest.set_index('団体名')[pop_col].to_dict() if not df_ov_latest.empty and pop_col in df_ov_latest.columns else {}
        
        s_year = df_target['団体名'].map(pop_dict_year)
        s_latest = df_target['団体名'].map(pop_dict_latest)
        pop_series = s_year.fillna(s_latest)
        
    return pd.to_numeric(pop_series, errors='coerce')

# 選択された自治体のデータを抽出
df_ov_city = filter_by_city(df_overview, selected_pref, selected_city)
df_rev_city = filter_by_city(df_revenue, selected_pref, selected_city)
df_exp_city = filter_by_city(df_exp_nature, selected_pref, selected_city)
df_purp_city = filter_by_city(df_exp_purpose, selected_pref, selected_city)
df_bonds_city = filter_by_city(df_bonds, selected_pref, selected_city)

st.write(f"**{scope_label} {selected_city}** のデータをご案内します。")

# ==========================================
# メニュー1: 概要
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

        # --- Tab 1: 総合ポイントランキング & 各種指標ランキング ---
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
                
                # 全国全体データ（比較用）を構築
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
                        
                        df_rev_calc = df_rev_all.copy()
                        df_rev_calc['自主財源_合計'] = df_rev_calc[jishu_exist].sum(axis=1) if jishu_exist else 0
                        all_rev_cols = [c for c in df_rev_calc.columns if c.endswith('_合計')]
                        df_rev_calc['歳入総額_calc'] = df_rev_calc[all_rev_cols].sum(axis=1) if all_rev_cols else 0
                        
                        rev_merge_cols = ['都道府県', '団体名', '地方税_合計', '自主財源_合計', '歳入総額_calc']
                        rev_merge_cols = [c for c in rev_merge_cols if c in df_rev_calc.columns]
                        df_rank_base = pd.merge(df_rank_base, df_rev_calc[rev_merge_cols].drop_duplicates(subset=['都道府県', '団体名']), on=['都道府県', '団体名'], how='left')

                    # 全国の人口を付与
                    df_rank_base['人口_num'] = get_population_series(df_rank_base, df_overview, selected_rank_year)

                    # 指標の計算（全国全自治体）
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

                    # 将来負担比率のカラム抽出
                    future_burden_cols = [c for c in df_rank_base.columns if '将来負担比率' in c]
                    if future_burden_cols:
                        df_rank_base['将来負担比率(%)'] = pd.to_numeric(df_rank_base[future_burden_cols[0]], errors='coerce').round(1)

                    # スコア化関数
                    def calc_score(series, is_higher_better=True):
                        s = pd.to_numeric(series, errors='coerce')
                        min_v, max_v = s.min(), s.max()
                        if pd.isna(min_v) or pd.isna(max_v) or max_v == min_v:
                            return pd.Series(50.0, index=s.index)
                        return ((s - min_v) / (max_v - min_v) * 100).round(1) if is_higher_better else ((max_v - s) / (max_v - min_v) * 100).round(1)

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

                    # サイドバーの絞り込み表示用フィルターを適用
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

                        # --- 🩺 財政状況診断（強み・課題・全国平均・適正水準の表示機能） ---
                        st.markdown("---")
                        st.markdown(f"#### 🩺 {selected_city} の財政状況診断（強み・課題・総合評価）")

                        # 全国平均の計算（該当年度の全自治体平均）
                        avg_tax_pc = df_rank_base['1人当たり地方税収入(千円)'].mean() if '1人当たり地方税収入(千円)' in df_rank_base.columns else np.nan
                        avg_pow_idx = df_rank_base['財政力指数'].mean() if '財政力指数' in df_rank_base.columns else np.nan
                        avg_jishu = df_rank_base['自主財源比率(%)'].mean() if '自主財源比率(%)' in df_rank_base.columns else np.nan
                        avg_keijo = df_rank_base['経常収支比率'].mean() if '経常収支比率' in df_rank_base.columns else np.nan
                        avg_fund_pc = df_rank_base['1人当たり基金(千円)'].mean() if '1人当たり基金(千円)' in df_rank_base.columns else np.nan
                        avg_debt_pc = df_rank_base['1人当たり実質将来負担(千円)'].mean() if '1人当たり実質将来負担(千円)' in df_rank_base.columns else np.nan

                        # 判定定義マップ（指標スコア名: (日本語ラベル, 実数値, 単位, 全国平均値, 目安・目標水準, 強み理由, 課題理由)）
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
                                    weaknesses_list.append(f"**{m_label}**（スコア: {sc_val:.1f} pt）<br>└ {info_meta}<br>└ {weak_desc}")

                        # 1. 総合評価サマリーメッセージの決定
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

                        # 2. 強みと課題の2コラム表示
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

                        # --- SubTab 1: 総合ランキング ---
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

                        # --- SubTab 2: 指標別 Top/Worst ランキング ---
                        with subtab_rank2:
                            st.markdown("##### 🥇 指標別 自治体ランキング（全国・同一県内・同一都市区分）")
                            
                            # 指標の定義（(列名, 表示名, 高いほうが優秀か否か, 単位)）
                            ranking_metrics_map = {
                                '財政力指数': ('財政力指数', True, ''),
                                '経常収支比率': ('経常収支比率（固定費の割合）', False, '%'),
                                '将来負担比率(%)': ('将来負担比率', False, '%'),
                                '1人当たり地方税収入(千円)': ('1人当たり地方税収入（地域の稼ぐ力）', True, '千円'),
                                '1人当たり基金(千円)': ('1人当たり基金残高（自治体の貯蓄力）', True, '千円'),
                                '1人当たり実質将来負担(千円)': ('1人当たり実質将来負担残高（実質借金）', False, '千円'),
                                '自主財源比率(%)': ('自主財源比率（自力調達の割合）', True, '%'),
                                '実質単年度収支': ('実質単年度収支（純損益）', True, '千円'),
                            }
                            
                            # 利用可能な指標のみ抽出
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

                            # 比較データセットの準備
                            if "同一県内" in scope_opt and selected_pref != "全国":
                                df_target_rank = df_rank_base[df_rank_base['都道府県'] == selected_pref].copy()
                            elif "同一都市区分" in scope_opt and selected_type != "すべて":
                                df_target_rank = df_rank_base[df_rank_base['都市区分'] == selected_type].copy()
                            else:
                                df_target_rank = df_rank_base.copy()

                            metric_info = available_metrics[selected_m_key]
                            is_higher_better = metric_info[1]
                            unit_str = metric_info[2]

                            # ソート方向の判定
                            if "ベスト" in rank_order_mode:
                                ascending = not is_higher_better
                            else:
                                ascending = is_higher_better

                            df_m_sorted = df_target_rank.dropna(subset=[selected_m_key]).sort_values(selected_m_key, ascending=ascending).copy()
                            
                            # 順位カラムの追加
                            rank_asc = not is_higher_better
                            df_m_sorted['順位'] = df_m_sorted[selected_m_key].rank(ascending=rank_asc, method='min').astype(int)

                            # 表示件数制限
                            if top_n != "全件":
                                df_plot_rank = df_m_sorted.head(int(top_n)).copy()
                            else:
                                df_plot_rank = df_m_sorted.copy()

                            df_plot_rank['表示色'] = df_plot_rank['団体名'].apply(lambda x: '選択中の自治体' if x == selected_city else 'その他自治体')

                            # Y軸用ユニークラベル
                            df_plot_rank['順位表示名'] = df_plot_rank['順位'].astype(str) + "位 " + df_plot_rank['団体名'] + "（" + df_plot_rank['都道府県'] + "）"

                            # 順位順に見やすくソート
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

                            # テーブル表示
                            st.markdown(f"##### 📋 {scope_opt} {metric_info[0]} データテーブル（{len(df_m_sorted)}自治体中）")
                            disp_m_cols = ['順位', '都道府県', '団体名', selected_m_key]
                            if '人口_num' in df_m_sorted.columns:
                                disp_m_cols.append('人口_num')
                            
                            st.dataframe(df_m_sorted[disp_m_cols], use_container_width=True)

        # --- Tab 2: 財政力 ---
        with tab2:
            st.markdown("#### 💪 財政力・財源基盤の推移と自治体間比較")
            subtab_pow1, subtab_pow2 = st.tabs(["📈 単体推移（需要額・収入額 vs 指数）", "📊 財政力指数の自治体間比較"])
            
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
            st.markdown("#### ⚙️ 財政効率性・収支構造の推移")
            subtab_eff1, subtab_eff2 = st.tabs(["📊 経常収支比率（固定費率）", "💰 単年度損益・収支バランス"])
            
            with subtab_eff1:
                cols_keijo = get_cols_by_keywords(['経常収支比率'])
                if cols_keijo:
                    fig_k = px.line(df_ov_city, x='年度', y=cols_keijo, markers=True, title="経常収支比率の推移")
                    fig_k.add_hline(y=80.0, line_dash="dash", line_color="green", annotation_text="適正水準 (80%)", annotation_position="bottom right")
                    fig_k.add_hline(y=90.0, line_dash="dash", line_color="red", annotation_text="硬直化警戒 (90%)", annotation_position="top right")
                    st.plotly_chart(fig_k, use_container_width=True, key="eff_keijo_chart")

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

                    fig1.update_yaxes(
                        range=[y_lower, y_upper],
                        tickformat=",", 
                        title="金額（千円）",
                        zeroline=True,
                        zerolinewidth=2,
                        zerolinecolor='black'
                    )

                    fig1.update_layout(xaxis_title="年度")
                    st.plotly_chart(fig1, use_container_width=True, key="eff_scale_chart")

        # --- Tab 4: 健全性 ---
        with tab4:
            st.markdown("### 🚨 地方財政健全化法に基づく健全化判断比率")
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

        # --- Tab 5: 都市構造 ---
        with tab5:
            st.markdown("#### 🏙️ 人口密度・都市構造とインフラ効率性の分析")
            
            with st.expander("💡 なぜ都市構造・人口密度が財政力や行政コストに影響を与えるのか？", expanded=True):
                st.markdown("""
                同じ「住民1人当たりの地方税収入」がある自治体同士であっても、**財政力指数（税収入 ÷ 行政コスト）に大きな差が生じる最大の要因は「都市構造と人口密度」**にあります。
                
                * **高密度・コンパクト都市（例：市川市など）：**
                  狭い面積に人口が集積しているため、道路・下水道・ごみ収集・公共施設などのインフラ維持管理コスト（基準財政需要額）が1人当たりで低く抑えられ、**財政力指数が高くなりやすい**構造です。
                * **低密度・広域都市（例：甲府市など）：**
                  広い市域にインフラを行き渡らせる必要があるため、住民1人当たりのインフラ維持費や広域行政コスト（中核市・県庁所在地機能など）が大きく膨らみ、需要額が大きくなることで**財政力指数が低くなりやすい**構造になります。
                """)

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
                            elif area_col and '面積_num' in c_struct:
                                st.metric("行政面積", f"{c_struct['面積_num']:,.2f} km²")
                        with m2:
                            if '1人当たり基準財政需要額(千円)' in c_struct and not pd.isna(c_struct['1人当たり基準財政需要額(千円)']):
                                st.metric("1人当たり行政コスト(需要額)", f"{c_struct['1人当たり基準財政需要額(千円)']:,.1f} 千円")
                        with m3:
                            if '財政力指数_num' in c_struct and not pd.isna(c_struct['財政力指数_num']):
                                st.metric("財政力指数", f"{c_struct['財政力指数_num']:.2f}")
                        with m4:
                            if '人口_num' in c_struct:
                                st.metric("総人口", f"{int(c_struct['人口_num']):,} 人")

                    st.markdown("---")
                    sub_st1, sub_st2, sub_st3 = st.tabs(["📊 散布図分析（都市構造 vs 財政力）", "📈 自治体別 インフラ効率性・コスト比較", "🏛️ 財政力指数 自治体間比較"])

                    with sub_st1:
                        st.markdown("##### 📍 都市構造（人口密度・行政コスト）と財政力指数の相関ポジショニングマップ")
                        x_axis_col = '人口密度(人/km2)' if '人口密度(人/km2)' in df_ov_y.columns and df_ov_y['人口密度(人/km2)'].notna().any() else '1人当たり基準財政需要額(千円)'
                        
                        if x_axis_col in df_ov_y.columns and '財政力指数_num' in df_ov_y.columns:
                            df_scatter = df_ov_y.dropna(subset=[x_axis_col, '財政力指数_num']).copy()
                            df_scatter['強調'] = df_scatter['団体名'].apply(lambda x: selected_city if x == selected_city else 'その他自治体')
                            
                            fig_sc = px.scatter(
                                df_scatter, x=x_axis_col, y='財政力指数_num',
                                color='強調', text='団体名', size='人口_num' if '人口_num' in df_scatter.columns else None,
                                hover_data=['都道府県', '団体名'],
                                title=f"{scope_label}（{selected_struct_year}年度）{x_axis_col} vs 財政力指数",
                                color_discrete_map={selected_city: '#FF4B4B', 'その他自治体': '#1F77B4'}
                            )
                            fig_sc.update_traces(textposition='top center')
                            fig_sc.add_hline(y=1.0, line_dash="dash", line_color="red", annotation_text="財政自立ライン (1.0)")
                            st.plotly_chart(fig_sc, use_container_width=True, key="struct_scatter_chart")

                    with sub_st2:
                        st.markdown("##### 📊 1人当たり基準財政需要額（行政サービス・インフラ維持コスト）自治体比較")
                        if '1人当たり基準財政需要額(千円)' in df_ov_y.columns:
                            df_dem_sorted = df_ov_y.dropna(subset=['1人当たり基準財政需要額(千円)']).sort_values('1人当たり基準財政需要額(千円)', ascending=False).copy()
                            df_dem_sorted['表示色'] = df_dem_sorted['団体名'].apply(lambda x: '選択中の自治体' if x == selected_city else 'その他自治体')
                            
                            fig_dem = px.bar(
                                df_dem_sorted, x='団体名', y='1人当たり基準財政需要額(千円)', color='表示色', text='1人当たり基準財政需要額(千円)',
                                title=f"{scope_label}（{selected_struct_year}年度）住民1人当たり基準財政需要額 比較（高い順＝広域・インフラ維持コスト増）",
                                color_discrete_map={'選択中の自治体': '#FF4B4B', 'その他自治体': '#1F77B4'},
                                custom_data=['都道府県']
                            )
                            fig_dem.update_traces(texttemplate='%{text:,.1f} 千円', textposition='outside', hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>1人当たり需要額: %{y:,.1f} 千円<extra></extra>")
                            fig_dem.update_layout(xaxis_title="自治体名", yaxis_title="1人当たり基準財政需要額（千円）")
                            st.plotly_chart(fig_dem, use_container_width=True, key="struct_dem_chart")

                            disp_struct_cols = ['都道府県', '団体名', '人口_num', '1人当たり基準財政需要額(千円)', '財政力指数_num']
                            if '人口密度(人/km2)' in df_ov_y.columns:
                                disp_struct_cols.insert(3, '人口密度(人/km2)')
                            disp_struct_cols = [c for c in disp_struct_cols if c in df_ov_y.columns]
                            st.dataframe(df_dem_sorted[disp_struct_cols], use_container_width=True)

                    with sub_st3:
                        st.markdown("##### 🏛️ 財政力指数 自治体間ランキング比較")
                        if '財政力指数_num' in df_ov_y.columns:
                            df_pow_struct = df_ov_y.dropna(subset=['財政力指数_num']).sort_values('財政力指数_num', ascending=False).copy()
                            df_pow_struct['表示色'] = df_pow_struct['団体名'].apply(lambda x: '選択中の自治体' if x == selected_city else 'その他自治体')

                            fig_pow_st = px.bar(
                                df_pow_struct, x='団体名', y='財政力指数_num', color='表示色', text='財政力指数_num',
                                title=f"{scope_label}（{selected_struct_year}年度）財政力指数 自治体間比較（高い順）",
                                color_discrete_map={'選択中の自治体': '#FF4B4B', 'その他自治体': '#1F77B4'},
                                custom_data=['都道府県']
                            )
                            fig_pow_st.add_hline(y=1.0, line_dash="dash", line_color="red", annotation_text="財政自立ライン (1.0)", annotation_position="top right")
                            fig_pow_st.update_traces(texttemplate='%{text:.2f}', textposition='outside', hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>財政力指数: %{y:.2f}<extra></extra>")
                            fig_pow_st.update_layout(xaxis_title="自治体名", yaxis_title="財政力指数")
                            st.plotly_chart(fig_pow_st, use_container_width=True, key="tab5_pow_comp_chart")

        # --- Tab 6: 人口・産業 ---
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

        # --- Tab 7: データ一覧 ---
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

        tab_rev1, tab_rev_jishu, tab_rev2, tab_rev3, tab_rev4 = st.tabs([
            "📈 自治体単体分析", 
            "🏛️ 自主財源分析",
            "📊 自治体間比較（総額）", 
            "👥 自治体間比較（1人当たり）",
            "🔍 細分化項目比較（全税目・内訳一覧）"
        ])

        with tab_rev1:
            st.subheader("1. 歳入構造の時系列推移（総額 vs 人口1人当たり）")
            df_plot = df_rev_city.copy()
            df_plot['歳入合計'] = df_plot[main_revenue_categories].sum(axis=1)
            df_plot['人口_num'] = get_population_series(df_plot, df_overview, "latest")

            sub_tot, sub_pc = st.tabs(["💰 総額推移", "👥 人口1人当たり推移"])
            with sub_tot:
                df_melt = df_plot.melt(id_vars=['年度', '歳入合計'], value_vars=main_revenue_categories, var_name='項目_raw', value_name='金額')
                df_melt['項目名'] = df_melt['項目_raw'].apply(clean_col_label)
                df_melt['割合(%)'] = (df_melt['金額'] / df_melt['歳入合計'] * 100).fillna(0).round(1)

                fig = px.bar(
                    df_melt, x='年度', y='金額', color='項目名', 
                    title=f"{selected_city} 歳入構成の推移（総額）", barmode='stack',
                    custom_data=['項目名', '割合(%)']
                )
                fig.update_layout(yaxis_tickformat=",", yaxis_title="金額（千円）")
                fig.update_traces(hovertemplate="<b>%{customdata[0]}</b><br>金額: %{y:,.0f} 千円<br>構成比: %{customdata[1]}%<extra></extra>")
                st.plotly_chart(fig, use_container_width=True, key="rev_tot_trend")

            with sub_pc:
                if '人口_num' in df_plot.columns and (df_plot['人口_num'] > 0).any():
                    pc_cols = []
                    for c in main_revenue_categories:
                        pc_col_name = c + '_1人当たり'
                        df_plot[pc_col_name] = (df_plot[c] / df_plot['人口_num'].replace(0, np.nan)).round(2)
                        pc_cols.append(pc_col_name)
                    df_plot['1人当たり歳入合計'] = (df_plot['歳入合計'] / df_plot['人口_num'].replace(0, np.nan)).round(2)

                    df_melt_pc = df_plot.melt(id_vars=['年度', '1人当たり歳入合計'], value_vars=pc_cols, var_name='項目_raw', value_name='1人当たり金額')
                    df_melt_pc['項目名'] = df_melt_pc['項目_raw'].apply(clean_col_label)
                    df_melt_pc['割合(%)'] = (df_melt_pc['1人当たり金額'] / df_melt_pc['1人当たり歳入合計'] * 100).fillna(0).round(1)

                    fig_pc = px.bar(
                        df_melt_pc, x='年度', y='1人当たり金額', color='項目名', 
                        title=f"{selected_city} 歳入構成の推移（1人当たり）", barmode='stack',
                        custom_data=['項目名', '割合(%)']
                    )
                    fig_pc.update_layout(yaxis_tickformat=",.1f", yaxis_title="1人当たり金額（千円/人）")
                    fig_pc.update_traces(hovertemplate="<b>%{customdata[0]}</b><br>1人当たり金額: %{y:,.2f} 千円/人<br>構成比: %{customdata[1]}%<extra></extra>")
                    st.plotly_chart(fig_pc, use_container_width=True, key="rev_pc_trend")

        with tab_rev_jishu:
            st.subheader("🏛️ 自主財源の総額・比率および自治体間比較")
            if jishu_cols_exist and izon_cols_exist:
                df_jishu_calc = df_rev_city.copy()
                df_jishu_calc['自主財源_合計'] = df_jishu_calc[jishu_cols_exist].sum(axis=1)
                df_jishu_calc['依存財源_合計'] = df_jishu_calc[izon_cols_exist].sum(axis=1)
                df_jishu_calc['歳入総額_calc'] = df_jishu_calc['自主財源_合計'] + df_jishu_calc['依存財源_合計']
                df_jishu_calc['自主財源比率(%)'] = (df_jishu_calc['自主財源_合計'] / df_jishu_calc['歳入総額_calc'].replace(0, np.nan) * 100).fillna(0).round(1)

                subtab_jishu1, subtab_jishu2, subtab_jishu3 = st.tabs([
                    "📈 単体推移（総額 & 比率）", 
                    "📊 自治体間比較（総額内訳）",
                    "👥 自治体間比較（1人当たり内訳）"
                ])

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
                        df_comp_j = df_pref_rev[df_pref_rev['年度'].astype(str) == str(comp_year_j)].copy()
                        df_comp_j['自主財源_合計'] = df_comp_j[jishu_cols_exist].sum(axis=1)
                        df_comp_j = df_comp_j.sort_values('自主財源_合計', ascending=False)
                        
                        df_comp_j_melt = df_comp_j.melt(id_vars=['都道府県', '団体名', '自主財源_合計'], value_vars=jishu_cols_exist, var_name='項目_raw', value_name='金額')
                        df_comp_j_melt['項目名'] = df_comp_j_melt['項目_raw'].apply(clean_col_label)
                        df_comp_j_melt['割合(%)'] = (df_comp_j_melt['金額'] / df_comp_j_melt['自主財源_合計'].replace(0, np.nan) * 100).fillna(0).round(1)

                        fig_comp_j_stack = px.bar(
                            df_comp_j_melt, x='団体名', y='金額', color='項目名',
                            title=f"{scope_label}（{comp_year_j}年度）自治体別 自主財源内訳比較（総額・大きい順）", barmode='stack',
                            custom_data=['都道府県', '項目名', '割合(%)']
                        )
                        fig_comp_j_stack.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
                        fig_comp_j_stack.update_traces(hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>項目名: %{customdata[1]}<br>金額: %{y:,.0f} 千円<br>構成比: %{customdata[2]}%<extra></extra>")
                        st.plotly_chart(fig_comp_j_stack, use_container_width=True, key="jishu_tot_comp_chart")

                with subtab_jishu3:
                    df_pref_rev = get_comparison_df(df_revenue)
                    if not df_pref_rev.empty:
                        comp_year_j_pop = st.selectbox("比較する年度を選択", df_pref_rev['年度'].astype(str).unique(), index=len(df_pref_rev['年度'].astype(str).unique())-1, key="comp_jishu_pop_year")
                        df_comp_j_pop = df_pref_rev[df_pref_rev['年度'].astype(str) == str(comp_year_j_pop)].copy()
                        
                        df_comp_j_pop['人口_num'] = get_population_series(df_comp_j_pop, df_overview, comp_year_j_pop)
                        df_comp_j_pop = df_comp_j_pop[df_comp_j_pop['人口_num'] > 0].copy()

                        jishu_pc_cols = []
                        for c in jishu_cols_exist:
                            pc_col_name = c + '_1人当たり'
                            df_comp_j_pop[pc_col_name] = (df_comp_j_pop[c] / df_comp_j_pop['人口_num']).round(2)
                            jishu_pc_cols.append(pc_col_name)

                        df_comp_j_pop['1人当たり自主財源合計'] = df_comp_j_pop[jishu_pc_cols].sum(axis=1)
                        df_comp_j_pop = df_comp_j_pop.sort_values('1人当たり自主財源合計', ascending=False)

                        df_melt_j_pc = df_comp_j_pop.melt(id_vars=['都道府県', '団体名', '1人当たり自主財源合計'], value_vars=jishu_pc_cols, var_name='項目_raw', value_name='1人当たり金額')
                        df_melt_j_pc['項目名'] = df_melt_j_pc['項目_raw'].apply(clean_col_label)
                        df_melt_j_pc['割合(%)'] = (df_melt_j_pc['1人当たり金額'] / df_melt_j_pc['1人当たり自主財源合計'].replace(0, np.nan) * 100).fillna(0).round(1)

                        fig_j_pc = px.bar(
                            df_melt_j_pc, x='団体名', y='1人当たり金額', color='項目名',
                            title=f"{scope_label}（{comp_year_j_pop}年度）自治体別 1人当たり自主財源内訳比較（大きい順）", barmode='stack',
                            custom_data=['都道府県', '項目名', '割合(%)']
                        )
                        fig_j_pc.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
                        fig_j_pc.update_traces(hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>項目名: %{customdata[1]}<br>1人当たり金額: %{y:,.2f} 千円/人<br>構成比: %{customdata[2]}%<extra></extra>")
                        st.plotly_chart(fig_j_pc, use_container_width=True, key="jishu_pc_comp_chart")

                        st.markdown("##### 📋 1人当たり自主財源内訳データテーブル")
                        disp_j_pc_cols = ['都道府県', '団体名', '人口_num', '1人当たり自主財源合計'] + jishu_pc_cols
                        rename_j_dict = {'人口_num': '人口(人)', '1人当たり自主財源合計': '1人当たり自主財源(千円)'}
                        for c in jishu_pc_cols:
                            rename_j_dict[c] = clean_col_label(c) + '(千円/人)'
                        st.dataframe(df_comp_j_pop[disp_j_pc_cols].rename(columns=rename_j_dict), use_container_width=True)

        with tab_rev2:
            st.subheader(f"{scope_label} 自治体歳入比較（総額）")
            df_pref_rev = get_comparison_df(df_revenue)
            if not df_pref_rev.empty:
                comp_year_rev = st.selectbox("比較する年度を選択", df_pref_rev['年度'].astype(str).unique(), index=len(df_pref_rev['年度'].astype(str).unique())-1, key="comp_rev_year")
                df_comp = df_pref_rev[df_pref_rev['年度'].astype(str) == str(comp_year_rev)].copy()
                df_comp['歳入合計'] = df_comp[main_revenue_categories].sum(axis=1)
                df_comp = df_comp.sort_values('歳入合計', ascending=False)

                df_melt_comp = df_comp.melt(id_vars=['都道府県', '団体名', '歳入合計'], value_vars=main_revenue_categories, var_name='項目_raw', value_name='金額')
                df_melt_comp['項目名'] = df_melt_comp['項目_raw'].apply(clean_col_label)
                df_melt_comp['割合(%)'] = (df_melt_comp['金額'] / df_melt_comp['歳入合計'].replace(0, np.nan) * 100).fillna(0).round(1)

                fig_c = px.bar(
                    df_melt_comp, x='団体名', y='金額', color='項目名', 
                    title=f"{scope_label}（{comp_year_rev}年度）自治体別 歳入構成比較（総額・大きい順）", barmode='stack',
                    custom_data=['都道府県', '項目名', '割合(%)']
                )
                fig_c.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
                fig_c.update_traces(hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>項目名: %{customdata[1]}<br>金額: %{y:,.0f} 千円<br>構成比: %{customdata[2]}%<extra></extra>")
                st.plotly_chart(fig_c, use_container_width=True, key="rev_tot_comp_chart")

        with tab_rev3:
            st.subheader(f"{scope_label} 自治体歳入比較（人口1人当たり）")
            df_pref_rev = get_comparison_df(df_revenue)
            if not df_pref_rev.empty:
                comp_year_rev_pop = st.selectbox("比較する年度を選択", df_pref_rev['年度'].astype(str).unique(), index=len(df_pref_rev['年度'].astype(str).unique())-1, key="comp_rev_pop_year")
                df_comp_pop = df_pref_rev[df_pref_rev['年度'].astype(str) == str(comp_year_rev_pop)].copy()
                
                df_comp_pop['人口_num'] = get_population_series(df_comp_pop, df_overview, comp_year_rev_pop)
                df_comp_pop = df_comp_pop[df_comp_pop['人口_num'] > 0].copy()
                
                pc_cols = []
                for c in main_revenue_categories:
                    pc_col_name = c + '_1人当たり'
                    df_comp_pop[pc_col_name] = (df_comp_pop[c] / df_comp_pop['人口_num']).round(2)
                    pc_cols.append(pc_col_name)

                df_comp_pop['1人当たり歳入合計'] = df_comp_pop[pc_cols].sum(axis=1)
                df_comp_pop = df_comp_pop.sort_values('1人当たり歳入合計', ascending=False)

                df_melt_pc_all = df_comp_pop.melt(id_vars=['都道府県', '団体名', '1人当たり歳入合計'], value_vars=pc_cols, var_name='項目_raw', value_name='1人当たり金額')
                df_melt_pc_all['項目名'] = df_melt_pc_all['項目_raw'].apply(clean_col_label)
                df_melt_pc_all['割合(%)'] = (df_melt_pc_all['1人当たり金額'] / df_melt_pc_all['1人当たり歳入合計'].replace(0, np.nan) * 100).fillna(0).round(1)

                fig_pc = px.bar(
                    df_melt_pc_all, x='団体名', y='1人当たり金額', color='項目名',
                    title=f"{scope_label}（{comp_year_rev_pop}年度）自治体別 1人当たり歳入構成比較（大きい順）", barmode='stack',
                    custom_data=['都道府県', '項目名', '割合(%)']
                )
                fig_pc.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
                fig_pc.update_traces(hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>項目名: %{customdata[1]}<br>1人当たり金額: %{y:,.2f} 千円/人<br>構成比: %{customdata[2]}%<extra></extra>")
                st.plotly_chart(fig_pc, use_container_width=True, key="rev_pc_comp_chart")

        with tab_rev4:
            st.subheader("🔍 細分化項目・全税目等の自治体間比較・内訳深掘り")
            df_pref_rev = get_comparison_df(df_revenue)
            rev_parent_options = {c: clean_col_label(c) for c in main_revenue_categories}
            selected_parent = st.selectbox("分析する歳出の大項目を選択", list(rev_parent_options.keys()), format_func=lambda x: rev_parent_options[x], key="sub_rev_parent")
            
            prefix = selected_parent.replace('_合計', '') + '_' if '_合計' in selected_parent else selected_parent + '_'
            sub_rev_cols = [c for c in df_revenue.columns if c.startswith(prefix) and c != selected_parent and '小計' not in c and '不納欠損' not in c and '参考_' not in c]
            
            if sub_rev_cols:
                sub_rev_labels = {c: c.replace(prefix, '').replace('寄附金_', '').replace('寄付金_', '') for c in sub_rev_cols}
                sub_mode1, sub_mode2 = st.tabs(["📊 傘下全項目（全税目等）の一括自治体比較", "🔍 特定の細分化項目の個別比較"])

                with sub_mode1:
                    avail_sub_years = df_pref_rev['年度'].astype(str).unique()
                    selected_sub_year = st.selectbox("比較年度を選択", avail_sub_years, index=len(avail_sub_years)-1, key="all_sub_rev_year")
                    unit_mode = st.radio("表示単位", ["1人当たり金額（千円/人）", "総額（千円）"], horizontal=True, key="unit_all_sub_rev")

                    df_pref_sub_y = df_pref_rev[df_pref_rev['年度'].astype(str) == str(selected_sub_year)].copy()
                    df_pref_sub_y['人口_num'] = get_population_series(df_pref_sub_y, df_overview, selected_sub_year)

                    if unit_mode == "1人当たり金額（千円/人）":
                        plot_sub_cols = []
                        for c in sub_rev_cols:
                            pc_c = c + '_1人当たり'
                            df_pref_sub_y[pc_c] = (df_pref_sub_y[c] / df_pref_sub_y['人口_num'].replace(0, np.nan)).round(2)
                            plot_sub_cols.append(pc_c)
                        
                        df_pref_sub_y['内訳合計_calc'] = df_pref_sub_y[plot_sub_cols].sum(axis=1)
                        df_pref_sub_y = df_pref_sub_y.sort_values('内訳合計_calc', ascending=False)

                        df_melt_all_sub = df_pref_sub_y.melt(id_vars=['都道府県', '団体名', '内訳合計_calc'], value_vars=plot_sub_cols, var_name='項目_raw', value_name='数値')
                        df_melt_all_sub['内訳名'] = df_melt_all_sub['項目_raw'].apply(lambda x: sub_rev_labels.get(x.replace('_1人当たり', ''), clean_col_label(x)))
                        df_melt_all_sub['割合(%)'] = (df_melt_all_sub['数値'] / df_melt_all_sub['内訳合計_calc'].replace(0, np.nan) * 100).fillna(0).round(1)

                        fig_all_sub = px.bar(
                            df_melt_all_sub, x='団体名', y='数値', color='内訳名',
                            title=f"{scope_label}（{selected_sub_year}年度）{rev_parent_options[selected_parent]} 内訳全項目 1人当たり比較",
                            barmode='stack', custom_data=['都道府県', '内訳名', '割合(%)']
                        )
                        fig_all_sub.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
                        fig_all_sub.update_traces(hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>内訳: %{customdata[1]}<br>1人当たり: %{y:,.2f} 千円/人<br>構成比: %{customdata[2]}%<extra></extra>")
                        st.plotly_chart(fig_all_sub, use_container_width=True, key="rev_sub1_pc_chart")
                    else:
                        df_pref_sub_y['内訳合計_calc'] = df_pref_sub_y[sub_rev_cols].sum(axis=1)
                        df_pref_sub_y = df_pref_sub_y.sort_values('内訳合計_calc', ascending=False)

                        df_melt_all_sub = df_pref_sub_y.melt(id_vars=['都道府県', '団体名', '内訳合計_calc'], value_vars=sub_rev_cols, var_name='項目_raw', value_name='数値')
                        df_melt_all_sub['内訳名'] = df_melt_all_sub['項目_raw'].apply(lambda x: sub_rev_labels.get(x, clean_col_label(x)))
                        df_melt_all_sub['割合(%)'] = (df_melt_all_sub['数値'] / df_melt_all_sub['内訳合計_calc'].replace(0, np.nan) * 100).fillna(0).round(1)

                        fig_all_sub = px.bar(
                            df_melt_all_sub, x='団体名', y='数値', color='内訳名',
                            title=f"{scope_label}（{selected_sub_year}年度）{rev_parent_options[selected_parent]} 内訳全項目 総額比較",
                            barmode='stack', custom_data=['都道府県', '内訳名', '割合(%)']
                        )
                        fig_all_sub.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
                        fig_all_sub.update_traces(hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>内訳: %{customdata[1]}<br>金額: %{y:,.0f} 千円<br>構成比: %{customdata[2]}%<extra></extra>")
                        st.plotly_chart(fig_all_sub, use_container_width=True, key="rev_sub1_tot_chart")

                with sub_mode2:
                    selected_sub_item = st.selectbox("比較する細分化項目を選択", list(sub_rev_labels.keys()), format_func=lambda x: sub_rev_labels[x], key="single_sub_rev_item")
                    sub_item_name = sub_rev_labels[selected_sub_item]
                    
                    avail_sub_years = df_pref_rev['年度'].astype(str).unique()
                    selected_sub_year_single = st.selectbox("比較年度を選択", avail_sub_years, index=len(avail_sub_years)-1, key="single_sub_rev_year")

                    df_pref_sub_y = df_pref_rev[df_pref_rev['年度'].astype(str) == str(selected_sub_year_single)].copy()
                    df_pref_sub_y['人口_num'] = get_population_series(df_pref_sub_y, df_overview, selected_sub_year_single)

                    val_s = pd.to_numeric(df_pref_sub_y[selected_sub_item], errors='coerce').fillna(0)
                    pop_s = pd.to_numeric(df_pref_sub_y['人口_num'], errors='coerce').replace(0, np.nan)
                    df_pref_sub_y['1人当たり金額(千円)'] = (val_s / pop_s).round(2)

                    sub_rank_mode = st.radio("比較表示モード", ["1人当たり金額（千円/人）", "総額（千円）"], horizontal=True, key="sub_rev_single_mode")
                    target_rank_col = '1人当たり金額(千円)' if sub_rank_mode == "1人当たり金額（千円/人）" else selected_sub_item

                    df_rank_sub = df_pref_sub_y.sort_values(target_rank_col, ascending=False).copy()
                    df_rank_sub['表示色'] = df_rank_sub['団体名'].apply(lambda x: '選択中の自治体' if x == selected_city else 'その他自治体')

                    fig_sub_rank = px.bar(
                        df_rank_sub, x='団体名', y=target_rank_col, color='表示色', text=target_rank_col,
                        title=f"{scope_label}（{selected_sub_year_single}年度）{sub_item_name} {sub_rank_mode} 比較",
                        color_discrete_map={'選択中の自治体': '#FF4B4B', 'その他自治体': '#1F77B4'},
                        custom_data=['都道府県', selected_sub_item]
                    )
                    fig_sub_rank.update_traces(texttemplate='%{text:,.1f}', textposition='outside', hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>数値: %{y:,.2f}<br>総額: %{customdata[1]:,.0f} 千円<extra></extra>")
                    st.plotly_chart(fig_sub_rank, use_container_width=True, key="rev_sub2_single_chart")

# ==========================================
# メニュー3: 性質別歳出
# ==========================================
elif menu == "性質別歳出":
    st.markdown("### 性質別歳出の推移と分析")
    if not df_exp_city.empty:
        main_categories = [
            '人件費_合計', '物件費_合計', '維持補修費_合計', '扶助費_合計', '補助費等_合計', 
            '普通建設事業費_合計', '災害復旧事業費_合計', '失業対策事業費_合計', 
            '公債費_合計', '積立金_合計', '投資及び出資金_合計', '貸付金_合計', '繰出金_合計'
        ]
        main_categories = [c for c in main_categories if c in df_exp_nature.columns]

        tab_exp1, tab_exp2, tab_exp3, tab_exp4 = st.tabs([
            "📈 自治体単体分析", 
            "📊 自治体間比較（総額）", 
            "👥 自治体間比較（1人当たり）",
            "🔍 細分化項目比較（内訳一括・個別）"
        ])

        with tab_exp1:
            st.subheader("1. 性質別歳出の推移")
            df_plot = df_exp_city.copy()
            df_plot['歳出合計'] = df_plot[main_categories].sum(axis=1)

            df_melt_e = df_plot.melt(id_vars=['年度', '歳出合計'], value_vars=main_categories, var_name='項目_raw', value_name='金額')
            df_melt_e['項目名'] = df_melt_e['項目_raw'].apply(clean_col_label)

            fig_exp = px.bar(df_melt_e, x='年度', y='金額', color='項目名', title=f"{selected_city} 性質別歳出の推移", barmode='stack')
            fig_exp.update_layout(yaxis_tickformat=",", yaxis_title="金額（千円）")
            st.plotly_chart(fig_exp, use_container_width=True, key="exp_nature_trend")

        with tab_exp2:
            st.subheader(f"{scope_label} 性質別歳出比較（総額）")
            df_pref_exp = get_comparison_df(df_exp_nature)
            if not df_pref_exp.empty:
                comp_year_exp = st.selectbox("比較する年度を選択", df_pref_exp['年度'].astype(str).unique(), index=len(df_pref_exp['年度'].astype(str).unique())-1, key="comp_exp_year")
                df_comp_e = df_pref_exp[df_pref_exp['年度'].astype(str) == str(comp_year_exp)].copy()
                df_comp_e['歳出合計'] = df_comp_e[main_categories].sum(axis=1)
                df_comp_e = df_comp_e.sort_values('歳出合計', ascending=False)

                df_melt_ce = df_comp_e.melt(id_vars=['都道府県', '団体名', '歳出合計'], value_vars=main_categories, var_name='項目_raw', value_name='金額')
                df_melt_ce['項目名'] = df_melt_ce['項目_raw'].apply(clean_col_label)

                fig_ce = px.bar(df_melt_ce, x='団体名', y='金額', color='項目名', title=f"{scope_label}（{comp_year_exp}年度）性質別歳出比較（総額）", barmode='stack')
                fig_ce.update_layout(yaxis_tickformat=",", yaxis_title="金額（千円）")
                st.plotly_chart(fig_ce, use_container_width=True, key="exp_nature_tot_comp")

        with tab_exp3:
            st.subheader(f"{scope_label} 性質別歳出比較（人口1人当たり）")
            df_pref_exp = get_comparison_df(df_exp_nature)
            if not df_pref_exp.empty:
                comp_year_exp_pop = st.selectbox("比較する年度を選択", df_pref_exp['年度'].astype(str).unique(), index=len(df_pref_exp['年度'].astype(str).unique())-1, key="comp_exp_pop_year")
                df_comp_e_pop = df_pref_exp[df_pref_exp['年度'].astype(str) == str(comp_year_exp_pop)].copy()
                
                df_comp_e_pop['人口_num'] = get_population_series(df_comp_e_pop, df_overview, comp_year_exp_pop)
                df_comp_e_pop = df_comp_e_pop[df_comp_e_pop['人口_num'] > 0].copy()
                
                pc_cols_e = []
                for c in main_categories:
                    pc_c = c + '_1人当たり'
                    df_comp_e_pop[pc_c] = (df_comp_e_pop[c] / df_comp_e_pop['人口_num']).round(2)
                    pc_cols_e.append(pc_c)

                df_comp_e_pop['1人当たり歳出合計'] = df_comp_e_pop[pc_cols_e].sum(axis=1)
                df_comp_e_pop = df_comp_e_pop.sort_values('1人当たり歳出合計', ascending=False)

                df_melt_ce_pc = df_comp_e_pop.melt(id_vars=['都道府県', '団体名', '1人当たり歳出合計'], value_vars=pc_cols_e, var_name='項目_raw', value_name='1人当たり金額')
                df_melt_ce_pc['項目名'] = df_melt_ce_pc['項目_raw'].apply(clean_col_label)

                fig_pc_e = px.bar(df_melt_ce_pc, x='団体名', y='1人当たり金額', color='項目名', title=f"{scope_label}（{comp_year_exp_pop}年度）1人当たり性質別歳出比較", barmode='stack')
                fig_pc_e.update_layout(yaxis_tickformat=",.1f", yaxis_title="1人当たり金額（千円/人）")
                st.plotly_chart(fig_pc_e, use_container_width=True, key="exp_nature_pc_comp")

        with tab_exp4:
            st.subheader("🔍 性質別歳出 細分化項目の比較分析")
            df_pref_exp = get_comparison_df(df_exp_nature)
            exp_parent_options = {c: clean_col_label(c) for c in main_categories}
            selected_exp_parent = st.selectbox("分析する歳出の大項目を選択", list(exp_parent_options.keys()), format_func=lambda x: exp_parent_options[x], key="sub_exp_parent")
            
            prefix_exp = selected_exp_parent.replace('_合計', '') + '_'
            sub_exp_cols = [c for c in df_exp_nature.columns if c.startswith(prefix_exp) and c != selected_exp_parent and '小計' not in c]
            
            if sub_exp_cols:
                sub_exp_labels = {c: c.replace(prefix_exp, '') for c in sub_exp_cols}
                avail_sub_exp_years = df_pref_exp['年度'].astype(str).unique()
                selected_sub_exp_year = st.selectbox("比較年度を選択", avail_sub_exp_years, index=len(avail_sub_exp_years)-1, key="sub_exp_year_select")
                unit_mode_e = st.radio("表示単位", ["1人当たり金額（千円/人）", "総額（千円）"], horizontal=True, key="unit_exp_sub")

                df_pref_sub_e_y = df_pref_exp[df_pref_exp['年度'].astype(str) == str(selected_sub_exp_year)].copy()
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

                    df_melt_all_sub_e = df_pref_sub_e_y.melt(id_vars=['都道府県', '団体名', '内訳合計_calc'], value_vars=plot_sub_cols_e, var_name='項目_raw', value_name='数値')
                    df_melt_all_sub_e['内訳名'] = df_melt_all_sub_e['項目_raw'].apply(lambda x: sub_exp_labels.get(x.replace('_1人当たり', ''), clean_col_label(x)))

                    fig_all_sub_e = px.bar(
                        df_melt_all_sub_e, x='団体名', y='数値', color='内訳名',
                        title=f"{scope_label}（{selected_sub_exp_year}年度）{exp_parent_options[selected_exp_parent]} 細分化内訳一括比較（1人当たり）",
                        barmode='stack'
                    )
                    fig_all_sub_e.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
                    st.plotly_chart(fig_all_sub_e, use_container_width=True, key="exp_sub_pc_chart")
                else:
                    df_pref_sub_e_y['内訳合計_calc'] = df_pref_sub_e_y[sub_exp_cols].sum(axis=1)
                    df_pref_sub_e_y = df_pref_sub_e_y.sort_values('内訳合計_calc', ascending=False)

                    df_melt_all_sub_e = df_pref_sub_e_y.melt(id_vars=['都道府県', '団体名', '内訳合計_calc'], value_vars=sub_exp_cols, var_name='項目_raw', value_name='数値')
                    df_melt_all_sub_e['内訳名'] = df_melt_all_sub_e['項目_raw'].apply(lambda x: sub_exp_labels.get(x, clean_col_label(x)))

                    fig_all_sub_e = px.bar(
                        df_melt_all_sub_e, x='団体名', y='数値', color='内訳名',
                        title=f"{scope_label}（{selected_sub_exp_year}年度）{exp_parent_options[selected_exp_parent]} 細分化内訳一括比較（総額）",
                        barmode='stack'
                    )
                    fig_all_sub_e.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
                    st.plotly_chart(fig_all_sub_e, use_container_width=True, key="exp_sub_tot_chart")

# ==========================================
# メニュー4: 目的別歳出
# ==========================================
elif menu == "目的別歳出":
    st.markdown("### 目的別歳出の推移と分析")
    if not df_purp_city.empty:
        candidate_purp_cats = [
            '議会費_合計', '総務費_合計', '民生費_合計', '衛生費_合計', '労働費_合計',
            '農林水産業費_合計', '商工費_合計', '土木費_合計', '消防費_合計', 
            '教育費_合計', '災害復旧費_合計', '公債費_合計', '諸支出金_合計', '前年度繰上充用金'
        ]
        main_purp_categories = [c for c in candidate_purp_cats if c in df_exp_purpose.columns]

        tab_purp1, tab_purp2, tab_purp3, tab_purp4 = st.tabs([
            "📈 自治体単体分析", 
            "📊 自治体間比較（総額）", 
            "👥 自治体間比較（1人当たり）",
            "🔍 細分化項目比較（事業費内訳一括）"
        ])

        with tab_purp1:
            st.subheader("1. 目的別歳出の推移")
            df_plot_p = df_purp_city.copy()
            df_plot_p['目的別歳出合計'] = df_plot_p[main_purp_categories].sum(axis=1)

            df_melt_p = df_plot_p.melt(id_vars=['年度', '目的別歳出合計'], value_vars=main_purp_categories, var_name='項目_raw', value_name='金額')
            df_melt_p['項目名'] = df_melt_p['項目_raw'].apply(clean_col_label)

            fig_p = px.bar(df_melt_p, x='年度', y='金額', color='項目名', title=f"{selected_city} 目的別歳出の推移", barmode='stack')
            fig_p.update_layout(yaxis_tickformat=",", yaxis_title="金額（千円）")
            st.plotly_chart(fig_p, use_container_width=True, key="purp_trend_chart")

        with tab_purp2:
            st.subheader(f"{scope_label} 目的別歳出比較（総額）")
            df_pref_purp = get_comparison_df(df_exp_purpose)
            if not df_pref_purp.empty:
                comp_year_purp = st.selectbox("比較する年度を選択", df_pref_purp['年度'].astype(str).unique(), index=len(df_pref_purp['年度'].astype(str).unique())-1, key="comp_purp_year")
                df_comp_p = df_pref_purp[df_pref_purp['年度'].astype(str) == str(comp_year_purp)].copy()
                df_comp_p['目的別歳出合計'] = df_comp_p[main_purp_categories].sum(axis=1)
                df_comp_p = df_comp_p.sort_values('目的別歳出合計', ascending=False)

                df_melt_cp = df_comp_p.melt(id_vars=['都道府県', '団体名', '目的別歳出合計'], value_vars=main_purp_categories, var_name='項目_raw', value_name='金額')
                df_melt_cp['項目名'] = df_melt_cp['項目_raw'].apply(clean_col_label)

                fig_cp = px.bar(df_melt_cp, x='団体名', y='金額', color='項目名', title=f"{scope_label}（{comp_year_purp}年度）目的別歳出比較（総額）", barmode='stack')
                fig_cp.update_layout(yaxis_tickformat=",", yaxis_title="金額（千円）")
                st.plotly_chart(fig_cp, use_container_width=True, key="purp_tot_comp_chart")

        with tab_purp3:
            st.subheader(f"{scope_label} 目的別歳出比較（人口1人当たり）")
            df_pref_purp = get_comparison_df(df_exp_purpose)
            if not df_pref_purp.empty:
                comp_year_purp_pop = st.selectbox("比較する年度を選択", df_pref_purp['年度'].astype(str).unique(), index=len(df_pref_purp['年度'].astype(str).unique())-1, key="comp_purp_pop_year")
                df_comp_p_pop = df_pref_purp[df_pref_purp['年度'].astype(str) == str(comp_year_purp_pop)].copy()
                
                df_comp_p_pop['人口_num'] = get_population_series(df_comp_p_pop, df_overview, comp_year_purp_pop)
                df_comp_p_pop = df_comp_p_pop[df_comp_p_pop['人口_num'] > 0].copy()
                
                pc_cols_p = []
                for c in main_purp_categories:
                    pc_c = c + '_1人当たり'
                    df_comp_p_pop[pc_c] = (df_comp_p_pop[c] / df_comp_p_pop['人口_num']).round(2)
                    pc_cols_p.append(pc_c)

                df_comp_p_pop['1人当たり目的別歳出合計'] = df_comp_p_pop[pc_cols_p].sum(axis=1)
                df_comp_p_pop = df_comp_p_pop.sort_values('1人当たり目的別歳出合計', ascending=False)

                df_melt_cp_pc = df_comp_p_pop.melt(id_vars=['都道府県', '団体名', '1人当たり目的別歳出合計'], value_vars=pc_cols_p, var_name='項目_raw', value_name='1人当たり金額')
                df_melt_cp_pc['項目名'] = df_melt_cp_pc['項目_raw'].apply(clean_col_label)

                fig_pc_p = px.bar(df_melt_cp_pc, x='団体名', y='1人当たり金額', color='項目名', title=f"{scope_label}（{comp_year_purp_pop}年度）1人当たり目的別歳出比較", barmode='stack')
                fig_pc_p.update_layout(yaxis_tickformat=",.1f", yaxis_title="1人当たり金額（千円/人）")
                st.plotly_chart(fig_pc_p, use_container_width=True, key="purp_pc_comp_chart")

        with tab_purp4:
            st.subheader("🔍 目的別歳出 細分化事業内訳の比較分析")
            df_pref_purp = get_comparison_df(df_exp_purpose)
            purp_parent_options = {c: clean_col_label(c) for c in main_purp_categories}
            selected_purp_parent = st.selectbox("分析する歳出の大項目（目的別）を選択", list(purp_parent_options.keys()), format_func=lambda x: purp_parent_options[x], key="sub_purp_parent")
            
            prefix_purp = selected_purp_parent.replace('_合計', '') + '_'
            sub_purp_cols = [c for c in df_exp_purpose.columns if c.startswith(prefix_purp) and c != selected_purp_parent and '小計' not in c]
            
            if sub_purp_cols:
                sub_purp_labels = {c: c.replace(prefix_purp, '') for c in sub_purp_cols}
                avail_sub_purp_years = df_pref_purp['年度'].astype(str).unique()
                selected_sub_purp_year = st.selectbox("比較年度を選択", avail_sub_purp_years, index=len(avail_sub_purp_years)-1, key="sub_purp_year_select")
                unit_mode_p = st.radio("表示単位", ["1人当たり金額（千円/人）", "総額（千円）"], horizontal=True, key="unit_purp_sub")

                df_pref_sub_p_y = df_pref_purp[df_pref_purp['年度'].astype(str) == str(selected_sub_purp_year)].copy()
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

                    df_melt_all_sub_p = df_pref_sub_p_y.melt(id_vars=['都道府県', '団体名', '内訳合計_calc'], value_vars=plot_sub_cols_p, var_name='項目_raw', value_name='数値')
                    df_melt_all_sub_p['内訳名'] = df_melt_all_sub_p['項目_raw'].apply(lambda x: sub_purp_labels.get(x.replace('_1人当たり', ''), clean_col_label(x)))

                    fig_all_sub_p = px.bar(
                        df_melt_all_sub_p, x='団体名', y='数値', color='内訳名',
                        title=f"{scope_label}（{selected_sub_purp_year}年度）{purp_parent_options[selected_purp_parent]} 事業内訳一括比較（1人当たり）",
                        barmode='stack'
                    )
                    fig_all_sub_p.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
                    st.plotly_chart(fig_all_sub_p, use_container_width=True, key="purp_sub_pc_chart")
                else:
                    df_pref_sub_p_y['内訳合計_calc'] = df_pref_sub_p_y[sub_purp_cols].sum(axis=1)
                    df_pref_sub_p_y = df_pref_sub_p_y.sort_values('内訳合計_calc', ascending=False)

                    df_melt_all_sub_p = df_pref_sub_p_y.melt(id_vars=['都道府県', '団体名', '内訳合計_calc'], value_vars=sub_purp_cols, var_name='項目_raw', value_name='数値')
                    df_melt_all_sub_p['内訳名'] = df_melt_all_sub_p['項目_raw'].apply(lambda x: sub_purp_labels.get(x, clean_col_label(x)))

                    fig_all_sub_p = px.bar(
                        df_melt_all_sub_p, x='団体名', y='数値', color='内訳名',
                        title=f"{scope_label}（{selected_sub_purp_year}年度）{purp_parent_options[selected_purp_parent]} 事業内訳一括比較（総額）",
                        barmode='stack'
                    )
                    fig_all_sub_p.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
                    st.plotly_chart(fig_all_sub_p, use_container_width=True, key="purp_sub_tot_chart")

# ==========================================
# メニュー5: 地方債・基金
# ==========================================
elif menu == "地方債・基金":
    st.markdown("### 地方債・積立金（基金）現在高の推移と分析")
    
    if not df_bonds_city.empty:
        tab_bonds1, tab_bonds2, tab_bonds3, tab_bonds4 = st.tabs([
            "📈 自治体単体分析", 
            "📊 自治体間比較（総額）", 
            "👥 自治体間比較（1人当たり）",
            "🔍 細分化項目比較（基金・繰出金等）"
        ])

        with tab_bonds1:
            st.subheader("1. 地方債・基金の推移")
            df_plot_b = df_bonds_city.copy()
            fig_b = go.Figure()
            if '地方債現在高_合計' in df_plot_b.columns:
                fig_b.add_trace(go.Scatter(x=df_plot_b['年度'], y=df_plot_b['地方債現在高_合計'], mode='lines+markers', name='地方債現在高', line=dict(color='red', width=3)))
            if '積立金現在高_合計' in df_plot_b.columns:
                fig_b.add_trace(go.Scatter(x=df_plot_b['年度'], y=df_plot_b['積立金現在高_合計'], mode='lines+markers', name='積立金現在高（基金）', line=dict(color='green', width=3)))
            fig_b.update_layout(title=f"{selected_city} 地方債現在高 vs 積立金現在高の推移", xaxis_title="年度", yaxis_title="金額（千円）", yaxis_tickformat=",")
            st.plotly_chart(fig_b, use_container_width=True, key="bonds_trend_chart")

        with tab_bonds2:
            st.subheader(f"{scope_label} 地方債・積立金比較（総額）")
            df_pref_bonds = get_comparison_df(df_bonds)
            if not df_pref_bonds.empty:
                comp_year_bonds = st.selectbox("比較する年度を選択", df_pref_bonds['年度'].astype(str).unique(), index=len(df_pref_bonds['年度'].astype(str).unique())-1, key="comp_bonds_year")
                df_comp_b = df_pref_bonds[df_pref_bonds['年度'].astype(str) == str(comp_year_bonds)].copy()
                df_comp_b = df_comp_b.sort_values('地方債現在高_合計', ascending=False)

                df_melt_cb = df_comp_b.melt(id_vars=['都道府県', '団体名'], value_vars=['地方債現在高_合計', '積立金現在高_合計'], var_name='項目_raw', value_name='金額')
                df_melt_cb['項目名'] = df_melt_cb['項目_raw'].apply(clean_col_label)

                fig_cb = px.bar(df_melt_cb, x='団体名', y='金額', color='項目名', title=f"{scope_label}（{comp_year_bonds}年度）地方債 vs 積立金比較（総額）", barmode='group')
                fig_cb.update_layout(yaxis_tickformat=",", yaxis_title="金額（千円）")
                st.plotly_chart(fig_cb, use_container_width=True, key="bonds_tot_comp_chart")

        with tab_bonds3:
            st.subheader(f"{scope_label} 地方債・積立金比較（人口1人当たり）")
            df_pref_bonds = get_comparison_df(df_bonds)
            if not df_pref_bonds.empty:
                comp_year_bonds_pop = st.selectbox("比較する年度を選択", df_pref_bonds['年度'].astype(str).unique(), index=len(df_pref_bonds['年度'].astype(str).unique())-1, key="comp_bonds_pop_year")
                df_comp_b_pop = df_pref_bonds[df_pref_bonds['年度'].astype(str) == str(comp_year_bonds_pop)].copy()

                df_comp_b_pop['人口_num'] = get_population_series(df_comp_b_pop, df_overview, comp_year_bonds_pop)
                df_comp_b_pop = df_comp_b_pop[df_comp_b_pop['人口_num'] > 0].copy()

                if not df_comp_b_pop.empty:
                    df_comp_b_pop['1人当たり地方債現在高'] = (df_comp_b_pop['地方債現在高_合計'] / df_comp_b_pop['人口_num']).round(2)
                    df_comp_b_pop['1人当たり積立金現在高'] = (df_comp_b_pop['積立金現在高_合計'] / df_comp_b_pop['人口_num']).round(2)
                    df_comp_b_pop = df_comp_b_pop.sort_values('1人当たり地方債現在高', ascending=False)

                    df_melt_cb_pc = df_comp_b_pop.melt(id_vars=['都道府県', '団体名'], value_vars=['1人当たり地方債現在高', '1人当たり積立金現在高'], var_name='項目_raw', value_name='1人当たり金額')
                    df_melt_cb_pc['項目名'] = df_melt_cb_pc['項目_raw'].apply(clean_col_label)

                    fig_pc_b = px.bar(df_melt_cb_pc, x='団体名', y='1人当たり金額', color='項目名', title=f"{scope_label}（{comp_year_bonds_pop}年度）1人当たり地方債 vs 積立金比較", barmode='group')
                    fig_pc_b.update_layout(yaxis_tickformat=",.1f", yaxis_title="1人当たり金額（千円/人）")
                    st.plotly_chart(fig_pc_b, use_container_width=True, key="bonds_pc_comp_chart")
                else:
                    st.warning("表示対象の人口データまたは地方債・積立金データが存在しません。")

        # --- 細分化項目分析 ---
        with tab_bonds4:
            st.subheader("🔍 地方債・基金・繰出金 細分化項目の比較分析")
            all_bonds_items = [c for c in df_bonds.columns if c not in ['年度', '都道府県', '都市区分', '自治体種別', '団体名']]
            if all_bonds_items:
                bonds_item_labels = {c: clean_col_label(c) for c in all_bonds_items}
                selected_bonds_col = st.selectbox("分析する詳細項目（基金種別・繰出金会計等）を選択", all_bonds_items, format_func=lambda x: bonds_item_labels[x], key="sub_bonds_col")
                bonds_item_name = bonds_item_labels[selected_bonds_col]

                df_pref_bonds_comp = get_comparison_df(df_bonds)
                avail_sub_bonds_years = df_pref_bonds_comp['年度'].astype(str).unique()
                selected_sub_bonds_year = st.selectbox("比較年度を選択", avail_sub_bonds_years, index=len(avail_sub_bonds_years)-1, key="sub_bonds_year_select")

                df_pref_sub_b_y = df_pref_bonds_comp[df_pref_bonds_comp['年度'].astype(str) == str(selected_sub_bonds_year)].copy()
                df_pref_sub_b_y['人口_num'] = get_population_series(df_pref_sub_b_y, df_overview, selected_sub_bonds_year)

                val_s = pd.to_numeric(df_pref_sub_b_y[selected_bonds_col], errors='coerce').fillna(0)
                pop_s = pd.to_numeric(df_pref_sub_b_y['人口_num'], errors='coerce').replace(0, np.nan)
                df_pref_sub_b_y['1人当たり金額(千円)'] = (val_s / pop_s).round(2)
                
                sub_bonds_rank_mode = st.radio("比較表示モード", ["1人当たり金額（千円/人）", "総額（千円）"], horizontal=True, key="sub_bonds_mode")
                target_bonds_rank_col = '1人当たり金額(千円)' if sub_bonds_rank_mode == "1人当たり金額（千円/人）" else selected_bonds_col
                
                df_rank_sub_bonds = df_pref_sub_b_y.sort_values(target_bonds_rank_col, ascending=False).copy()
                df_rank_sub_bonds['表示色'] = df_rank_sub_bonds['団体名'].apply(lambda x: '選択中の自治体' if x == selected_city else 'その他自治体')
                
                fig_sub_bonds_rank = px.bar(
                    df_rank_sub_bonds, x='団体名', y=target_bonds_rank_col, color='表示色', text=target_bonds_rank_col,
                    title=f"{scope_label}（{selected_sub_bonds_year}年度）{bonds_item_name} {sub_bonds_rank_mode} 比較",
                    color_discrete_map={'選択中の自治体': '#FF4B4B', 'その他自治体': '#1F77B4'},
                    custom_data=['都道府県', selected_bonds_col]
                )
                fig_sub_bonds_rank.update_traces(texttemplate='%{text:,.1f}', textposition='outside', hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>数値: %{y:,.2f}<br>総額: %{customdata[1]:,.0f} 千円<extra></extra>")
                st.plotly_chart(fig_sub_bonds_rank, use_container_width=True, key="bonds_sub_rank_chart")