import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from utils.data_loader import load_data

# データの呼び出し（スプレッドシートからのロード結果を取得）
loaded_data = load_data()
if isinstance(loaded_data, (tuple, list)) and len(loaded_data) >= 5:
    df_overview, df_revenue, df_exp_nature, df_exp_purpose, df_bonds = loaded_data[:5]
else:
    df_overview, df_revenue, df_exp_nature, df_exp_purpose = loaded_data[:4]
    df_bonds = pd.DataFrame()

# 地方債データの数値項目クリーニング（ハイフンやカンマの自動変換）
if not df_bonds.empty:
    bonds_num_cols = [c for c in df_bonds.columns if c not in ['年度', '都道府県', '都市区分', '自治体種別', '団体名']]
    for c in bonds_num_cols:
        df_bonds[c] = pd.to_numeric(
            df_bonds[c].astype(str).str.replace(',', '').str.replace('-', '0'), 
            errors='coerce'
        ).fillna(0)

st.title("🏘️ 市町村 財政分析")

# --- 市町村専用のサイドバーフィルター ---
st.sidebar.markdown("---")
st.sidebar.subheader("データ絞り込み")

pref_list = df_overview['都道府県'].dropna().unique() if not df_overview.empty else []
pref_default_idx = list(pref_list).index('山梨県') if '山梨県' in pref_list else 0
selected_pref = st.sidebar.selectbox("都道府県を選択", pref_list, index=pref_default_idx) if len(pref_list) > 0 else st.sidebar.text("都道府県データなし")

city_list = df_overview[df_overview['都道府県'] == selected_pref]['団体名'].dropna().unique() if not df_overview.empty and isinstance(selected_pref, str) else []
city_default_idx = list(city_list).index('甲府市') if '甲府市' in city_list else 0
selected_city = st.sidebar.selectbox("市町村を選択", city_list, index=city_default_idx) if len(city_list) > 0 else st.sidebar.text("市町村データなし")

# 「地方債」メニューを追加
menu = st.sidebar.radio("表示メニュー", ["概要", "歳入", "性質別歳出", "目的別歳出", "地方債"])

# --- フィルター処理関数 ---
def filter_by_city(df, pref, city):
    if not df.empty and '都道府県' in df.columns and '団体名' in df.columns:
        return df[(df['都道府県'] == pref) & (df['団体名'] == city)].sort_values('年度', key=lambda x: x.astype(str))
    return df

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

# 選択された自治体のデータを抽出
df_ov_city = filter_by_city(df_overview, selected_pref, selected_city)
df_rev_city = filter_by_city(df_revenue, selected_pref, selected_city)
df_exp_city = filter_by_city(df_exp_nature, selected_pref, selected_city)
df_purp_city = filter_by_city(df_exp_purpose, selected_pref, selected_city)
df_bonds_city = filter_by_city(df_bonds, selected_pref, selected_city)

st.write(f"**{selected_pref} {selected_city}** のデータをご案内します。")

# ==========================================
# メニュー1: 概要
# ==========================================
if menu == "概要":
    st.markdown("### 財政状況の概要（パッケージ表示）")
    if not df_ov_city.empty:
        # タブに「🏆 県内ランキング・総合指標」を追加
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
            "🏆 県内ランキング・総合指標",
            "⚖️ 基準財政・財政力・標準規模", 
            "💰 財政規模・バランス", 
            "👥 人口・職員数", 
            "🏗️ 産業割合",
            "📊 経常収支比率",
            "🚨 健全化判断比率",
            "🏛️ 公債費負担比率",
            "📋 データ一覧"
        ])
        
        num_cols = df_ov_city.select_dtypes(include=['number']).columns.tolist()
        
        def get_cols_by_keywords(keywords):
            return [col for col in num_cols if any(kw in col for kw in keywords)]

        # --- 新設タブ: 🏆 県内ランキング・総合指標 ---
        with tab1:
            st.markdown("#### 🏆 県内自治体における財政指標ランキング & 総合健全化指標")
            
            # 対象年度の選択
            available_ov_years = sorted(df_overview['年度'].astype(str).unique())
            latest_year = available_ov_years[-1] if available_ov_years else ""
            selected_rank_year = st.selectbox("分析対象年度を選択", available_ov_years, index=len(available_ov_years)-1, key="rank_year_select")
            
            # 県内全自治体データの抽出と統合
            df_ov_pref_y = df_overview[(df_overview['都道府県'] == selected_pref) & (df_overview['年度'].astype(str) == str(selected_rank_year))].copy()
            df_bonds_pref_y = df_bonds[(df_bonds['都道府県'] == selected_pref) & (df_bonds['年度'].astype(str) == str(selected_rank_year))].copy() if not df_bonds.empty else pd.DataFrame()
            
            if not df_ov_pref_y.empty:
                # 地方債・基金データのマージ
                if not df_bonds_pref_y.empty:
                    b_cols = ['団体名', '地方債現在高_合計', '積立金現在高_合計', '債務負担行為額(翌年度以降支出予定額)_合計']
                    b_cols_exist = [c for c in b_cols if c in df_bonds_pref_y.columns]
                    df_rank = pd.merge(df_ov_pref_y, df_bonds_pref_y[b_cols_exist], on='団体名', how='left')
                else:
                    df_rank = df_ov_pref_y.copy()
                
                # 人口カラムの取得
                pop_col = get_population_col(df_rank)
                if pop_col:
                    df_rank['人口_num'] = pd.to_numeric(df_rank[pop_col].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce').fillna(0)
                else:
                    df_rank['人口_num'] = 0
                
                # 数値データの補正
                for target_c in ['地方債現在高_合計', '積立金現在高_合計', '債務負担行為額(翌年度以降支出予定額)_合計', '財政力指数', '経常収支比率', '実質公債費比率', '将来負担比率']:
                    if target_c in df_rank.columns:
                        df_rank[target_c] = pd.to_numeric(df_rank[target_c].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce')
                
                # 複合・健全化指標の事前計算
                if all(c in df_rank.columns for c in ['地方債現在高_合計', '積立金現在高_合計']):
                    debt_val = df_rank['地方債現在高_合計'].fillna(0)
                    fund_val = df_rank['積立金現在高_合計'].fillna(0)
                    commit_val = df_rank['債務負担行為額(翌年度以降支出予定額)_合計'].fillna(0) if '債務負担行為額(翌年度以降支出予定額)_合計' in df_rank.columns else 0
                    
                    # 実質将来負担残高（推計） = 地方債 ＋ 債務負担行為額 － 基金
                    df_rank['実質将来負担残高_推計'] = debt_val + commit_val - fund_val
                
                if '人口_num' in df_rank.columns:
                    df_rank['1人当たり地方債(千円)'] = (df_rank['地方債現在高_合計'] / df_rank['人口_num']).round(1)
                    df_rank['1人当たり基金(千円)'] = (df_rank['積立金現在高_合計'] / df_rank['人口_num']).round(1)
                    df_rank['1人当たり実質将来負担(千円)'] = (df_rank['実質将来負担残高_推計'] / df_rank['人口_num']).round(1)

                total_cities_count = len(df_rank)
                
                # --- ランキング順位の算出 ---
                if '財政力指数' in df_rank.columns:
                    df_rank['財政力指数_順位'] = df_rank['財政力指数'].rank(ascending=False, method='min')
                if '経常収支比率' in df_rank.columns:
                    df_rank['経常収支比率_順位'] = df_rank['経常収支比率'].rank(ascending=True, method='min') # 比率が低いほど良好
                if '1人当たり基金(千円)' in df_rank.columns:
                    df_rank['1人当たり基金_順位'] = df_rank['1人当たり基金(千円)'].rank(ascending=False, method='min')
                if '1人当たり実質将来負担(千円)' in df_rank.columns:
                    df_rank['1人当たり実質将来負担_順位'] = df_rank['1人当たり実質将来負担(千円)'].rank(ascending=True, method='min') # 負担が少ないほど良好

                # 選択された自治体データの取得
                city_rank_row = df_rank[df_rank['団体名'] == selected_city]
                
                if not city_rank_row.empty:
                    c_data = city_rank_row.iloc[0]
                    
                    st.markdown(f"##### 📍 {selected_pref}内における **{selected_city}** の順位・健全化要約（{selected_rank_year}年度 / 全{total_cities_count}自治体）")
                    
                    # 1. 概要カード (st.metric) の表示
                    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
                    
                    with m_col1:
                        if '財政力指数' in c_data and not pd.isna(c_data['財政力指数']):
                            st.metric(
                                label="財政力指数", 
                                value=f"{c_data['財政力指数']:.2f}", 
                                delta=f"県内 {int(c_data['財政力指数_順位'])}位 / {total_cities_count}",
                                delta_color="normal"
                            )
                    
                    with m_col2:
                        if '経常収支比率' in c_data and not pd.isna(c_data['経常収支比率']):
                            st.metric(
                                label="経常収支比率", 
                                value=f"{c_data['経常収支比率']:.1f}%", 
                                delta=f"県内 {int(c_data['経常収支比率_順位'])}位（低い順）",
                                delta_color="inverse"
                            )
                    
                    with m_col3:
                        if '1人当たり基金(千円)' in c_data and not pd.isna(c_data['1人当たり基金(千円)']):
                            st.metric(
                                label="1人当たり基金（貯金）", 
                                value=f"{c_data['1人当たり基金(千円)']:,.1f} 千円", 
                                delta=f"県内 {int(c_data['1人当たり基金_順位'])}位",
                                delta_color="normal"
                            )

                    with m_col4:
                        if '1人当たり実質将来負担(千円)' in c_data and not pd.isna(c_data['1人当たり実質将来負担(千円)']):
                            st.metric(
                                label="1人当たり実質将来負担", 
                                value=f"{c_data['1人当たり実質将来負担(千円)']:,.1f} 千円", 
                                delta=f"県内 {int(c_data['1人当たり実質将来負担_順位'])}位（少ない順）",
                                delta_color="inverse"
                            )

                    st.markdown("---")
                    st.markdown("##### 📊 県内比較チャート")
                    
                    # 表示対象指標の選択
                    rank_chart_options = {
                        '財政力指数': '財政力指数（高い順＝自立度高）',
                        '経常収支比率': '経常収支比率（低い順＝弾力性高）',
                        '1人当たり基金(千円)': '1人当たり基金残高（高い順＝貯金多）',
                        '1人当たり実質将来負担(千円)': '1人当たり実質将来負担残高（低い順＝将来負担少）'
                    }
                    rank_chart_options = {k: v for k, v in rank_chart_options.items() if k in df_rank.columns}
                    
                    selected_rank_col = st.selectbox("比較指標を選択", list(rank_chart_options.keys()), format_func=lambda x: rank_chart_options[x], key="rank_col_select")
                    
                    # 昇順・降順ソート設定
                    asc_flag = True if '比率' in selected_rank_col or '負担' in selected_rank_col else False
                    df_rank_sorted = df_rank.sort_values(selected_rank_col, ascending=asc_flag).copy()
                    
                    # 選択された市町村をハイライト表示するための色カラム
                    df_rank_sorted['表示色'] = df_rank_sorted['団体名'].apply(lambda x: '選択中の自治体' if x == selected_city else 'その他自治体')
                    
                    fig_rank = px.bar(
                        df_rank_sorted, x='団体名', y=selected_rank_col, color='表示色',
                        text=selected_rank_col,
                        title=f"{selected_pref}（{selected_rank_year}年度）{rank_chart_options[selected_rank_col]} 比較",
                        color_discrete_map={'選択中の自治体': '#FF4B4B', 'その他自治体': '#1F77B4'}
                    )
                    fig_rank.update_traces(texttemplate='%{text:,.2f}', textposition='outside')
                    fig_rank.update_layout(xaxis_title="自治体名", yaxis_title=selected_rank_col, showlegend=True)
                    st.plotly_chart(fig_rank, use_container_width=True)
                    
                    # 比較テーブルの表示
                    st.markdown("##### 📋 県内財政健全化指標 比較テーブル")
                    disp_rank_cols = ['団体名', '財政力指数', '経常収支比率', '1人当たり基金(千円)', '1人当たり実質将来負担(千円)']
                    disp_rank_cols = [c for c in disp_rank_cols if c in df_rank_sorted.columns]
                    st.dataframe(df_rank_sorted[disp_rank_cols], use_container_width=True)
                else:
                    st.warning("選択した自治体のデータが見つかりません。")
            else:
                st.info("該当年度の県内比較データが存在しません。")

# ==========================================
# メニュー2: 歳入
# ==========================================
elif menu == "歳入":
    st.markdown("### 歳入の推移と分析")
    if not df_rev_city.empty:
        general_revenue_cols = [
            '地方税_合計', '地方譲与税_合計', '都道府県税交付金_合計', 
            '地方特例交付金_合計', '地方交付税_合計', '交通安全対策特別交付金', 
            '特別区財政調整交付金'
        ]
        specific_revenue_cols = [
            '国庫支出金_合計', '都道府県支出金_合計', '地方債_合計', 
            '分担金及び負担金_合計', '使用料_合計', '手数料_合計', 
            '財産収入_合計', '寄附金_合計', '繰入金_合計', '繰越金_合計', 
            '諸収入_合計', '国有提供施設等所在市町村助成交付金'
        ]

        candidate_main_rev = general_revenue_cols + specific_revenue_cols
        main_revenue_categories = [c for c in candidate_main_rev if c in df_revenue.columns]
        gen_rev_categories = [c for c in general_revenue_cols if c in df_revenue.columns]
        spec_rev_categories = [c for c in specific_revenue_cols if c in df_revenue.columns]
        
        tab_rev1, tab_rev2, tab_rev3, tab_rev4 = st.tabs([
            "📈 自治体単体分析", 
            "📊 同一県内自治体比較（総額）", 
            "👥 同一県内自治体比較（1人当たり）",
            "🔍 歳入分析"
        ])

        def plot_time_series_revenue(df_city, target_cols, title_prefix, total_col_name):
            if not target_cols:
                st.info("該当する項目データが見つかりません。")
                return
            
            df_plot = df_city.copy()
            for c in target_cols:
                df_plot[c] = pd.to_numeric(
                    df_plot[c].astype(str).str.replace(',', '').str.replace('-', '0'), 
                    errors='coerce'
                ).fillna(0)
            
            df_plot[total_col_name] = df_plot[target_cols].sum(axis=1)
            df_melt = df_plot.melt(
                id_vars=['年度', total_col_name], 
                value_vars=target_cols, 
                var_name='項目_raw', 
                value_name='金額'
            )
            df_melt['項目名'] = df_melt['項目_raw'].str.replace('_合計', '')
            df_melt['割合(%)'] = (df_melt['金額'] / df_melt[total_col_name] * 100).fillna(0).round(1)

            display_cats = [c.replace('_合計', '') for c in target_cols]

            fig = px.bar(
                df_melt, x='年度', y='金額', color='項目名', 
                title=f"{title_prefix} 構成の推移", barmode='stack',
                category_orders={'項目名': display_cats},
                custom_data=['項目名', '割合(%)']
            )
            fig.update_layout(yaxis_tickformat=",")
            fig.update_yaxes(title_text="金額（千円）")
            fig.update_traces(
                hovertemplate="<b>項目名: %{customdata[0]}</b><br>金額: %{y:,.0f} 千円<br>構成比: %{customdata[1]}%<extra></extra>"
            )
            
            for i, row in df_plot.iterrows():
                if row[total_col_name] > 0:
                    fig.add_annotation(
                        x=row['年度'], y=row[total_col_name],
                        text=f"{row[total_col_name]:,.0f}", showarrow=False, yshift=10, font=dict(size=10)
                    )
            st.plotly_chart(fig, use_container_width=True)

        def plot_pref_comp_revenue(df_pref, target_cols, comp_year, title_suffix, total_col_name):
            if not target_cols or df_pref.empty:
                st.info("該当する比較データが見つかりません。")
                return

            df_comp = df_pref[df_pref['年度'].astype(str) == str(comp_year)].copy()
            for c in target_cols:
                df_comp[c] = pd.to_numeric(
                    df_comp[c].astype(str).str.replace(',', '').str.replace('-', '0'), 
                    errors='coerce'
                ).fillna(0)
            
            df_comp[total_col_name] = df_comp[target_cols].sum(axis=1)
            df_comp = df_comp.sort_values(total_col_name, ascending=False)
            sorted_cities = df_comp['団体名'].tolist()
            
            df_melt = df_comp.melt(
                id_vars=['団体名', total_col_name], 
                value_vars=target_cols, 
                var_name='項目_raw', 
                value_name='金額'
            )
            df_melt['項目名'] = df_melt['項目_raw'].str.replace('_合計', '')
            df_melt['割合(%)'] = (df_melt['金額'] / df_melt[total_col_name] * 100).fillna(0).round(1)

            fig = px.bar(
                df_melt, x='団体名', y='金額', color='項目名',
                title=f"{selected_pref}（{comp_year}年度）自治体別{title_suffix}構成比較（総額・大きい順）", barmode='stack',
                category_orders={
                    '団体名': sorted_cities, 
                    '項目名': [c.replace('_合計', '') for c in target_cols]
                },
                custom_data=['項目名', '割合(%)']
            )
            fig.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
            fig.update_traces(
                hovertemplate="<b>自治体: %{x}</b><br>項目名: %{customdata[0]}<br>金額: %{y:,.0f} 千円<br>構成比: %{customdata[1]}%<extra></extra>"
            )
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown(f"#### {title_suffix}比較データテーブル（総額）")
            st.dataframe(df_comp[['団体名', total_col_name] + target_cols], use_container_width=True)

        def plot_pref_comp_pop_revenue(df_pref, df_pref_ov, target_cols, comp_year, pop_col, title_suffix, total_col_name):
            if not target_cols or df_pref.empty or not pop_col:
                st.info("該当する人口・比較データが見つかりません。")
                return

            df_comp = df_pref[df_pref['年度'].astype(str) == str(comp_year)].copy()
            df_ov_year = df_pref_ov[df_pref_ov['年度'].astype(str) == str(comp_year)].copy()
            df_ov_year['人口_num'] = pd.to_numeric(
                df_ov_year[pop_col].astype(str).str.replace(',', '').str.replace('-', '0'), 
                errors='coerce'
            ).fillna(0)
            
            df_comp_pop = df_comp.merge(df_ov_year[['団体名', '人口_num']], on='団体名', how='left')
            df_comp_pop['人口_num'] = df_comp_pop['人口_num'].fillna(0)
            df_comp_pop = df_comp_pop[df_comp_pop['人口_num'] > 0].copy()
            
            if df_comp_pop.empty:
                st.warning("該当年度の人口データが見つからないか、全自治体の人口が0です。")
                return

            for c in target_cols:
                df_comp_pop[c] = pd.to_numeric(
                    df_comp_pop[c].astype(str).str.replace(',', '').str.replace('-', '0'), 
                    errors='coerce'
                ).fillna(0)
                df_comp_pop[c + '_1人当たり'] = (df_comp_pop[c] / df_comp_pop['人口_num']).round(2)
            
            df_comp_pop[total_col_name] = df_comp_pop[target_cols].sum(axis=1)
            per_capita_total = f"1人当たり{total_col_name}"
            df_comp_pop[per_capita_total] = (df_comp_pop[total_col_name] / df_comp_pop['人口_num']).round(2)
            
            df_comp_pop = df_comp_pop.sort_values(per_capita_total, ascending=False)
            sorted_cities = df_comp_pop['団体名'].tolist()
            
            per_capita_cols = [c + '_1人当たり' for c in target_cols]
            df_melt = df_comp_pop.melt(
                id_vars=['団体名', per_capita_total, '人口_num'], 
                value_vars=per_capita_cols, 
                var_name='項目_raw', 
                value_name='1人当たり金額'
            )
            df_melt['項目名'] = df_melt['項目_raw'].str.replace('_合計', '').str.replace('_1人当たり', '')
            df_melt['割合(%)'] = (df_melt['1人当たり金額'] / df_melt[per_capita_total] * 100).fillna(0).round(1)

            fig = px.bar(
                df_melt, x='団体名', y='1人当たり金額', color='項目名',
                title=f"{selected_pref}（{comp_year}年度）自治体別1人当たり{title_suffix}構成比較（大きい順 / 人口参照: {pop_col}）", barmode='stack',
                category_orders={
                    '団体名': sorted_cities, 
                    '項目名': [c.replace('_合計', '') for c in target_cols]
                },
                custom_data=['項目名', '割合(%)']
            )
            fig.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
            fig.update_traces(
                hovertemplate="<b>自治体: %{x}</b><br>項目名: %{customdata[0]}<br>1人当たり金額: %{y:,.2f} 千円/人<br>構成比: %{customdata[1]}%<extra></extra>"
            )
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown(f"#### 1人当たり{title_suffix}比較データテーブル")
            disp_cols = ['団体名', '人口_num', per_capita_total] + per_capita_cols
            rename_dict = {'人口_num': f'人口({pop_col})', per_capita_total: f'1人当たり{total_col_name}(千円)'}
            for c in per_capita_cols:
                rename_dict[c] = c.replace('_合計', '').replace('_1人当たり', '') + '(千円/人)'
            
            st.dataframe(df_comp_pop[disp_cols].rename(columns=rename_dict), use_container_width=True)

        with tab_rev1:
            st.subheader("1. 時系列推移分析")
            subtab1_all, subtab1_gen, subtab1_spec = st.tabs(["🌐 歳入全体", "🏛️ 一般財源", "🎯 特定財源"])
            
            with subtab1_all:
                plot_time_series_revenue(df_rev_city, main_revenue_categories, "歳入全体", "歳入合計")
            with subtab1_gen:
                plot_time_series_revenue(df_rev_city, gen_rev_categories, "一般財源", "一般財源合計")
            with subtab1_spec:
                plot_time_series_revenue(df_rev_city, spec_rev_categories, "特定財源", "特定財源合計")

            st.markdown("---")
            st.subheader("2. 項目別 内訳分析")
            
            available_years = df_rev_city['年度'].astype(str).unique()
            selected_year = st.selectbox("確認したい年度を選択", available_years, index=len(available_years)-1, key="rev_year")
            
            rev_category_labels = {c: c.replace('_合計', '') for c in main_revenue_categories}
            selected_rev_label = st.selectbox("深掘りする大項目を選択", list(rev_category_labels.values()), key="rev_main_label")
            selected_main = [k for k, v in rev_category_labels.items() if v == selected_rev_label][0]
            
            prefix = selected_main.replace('_合計', '') + '_' if '_合計' in selected_main else selected_main + '_'
            
            if prefix in ['寄附金_', '寄付金_']:
                sub_categories = [c for c in df_rev_city.columns if (c.startswith('寄附金_') or c.startswith('寄付金_')) and c != selected_main and '小計' not in c]
            else:
                sub_categories = [c for c in df_rev_city.columns if c.startswith(prefix) and c != selected_main and '小計' not in c]
            
            if sub_categories:
                df_year_rev = df_rev_city[df_rev_city['年度'].astype(str) == str(selected_year)]
                if not df_year_rev.empty:
                    row_data = df_year_rev.iloc[0]
                    sub_data = []
                    for sc in sub_categories:
                        if '不納欠損額' in sc or '参考_' in sc:
                            continue
                        val = pd.to_numeric(str(row_data[sc]).replace(',', '').replace('-', '0'), errors='coerce')
                        if not pd.isna(val) and val > 0:
                            clean_sub_name = sc.replace('寄附金_', '').replace('寄付金_', '').replace(prefix, '')
                            sub_data.append({'内訳': clean_sub_name, '金額': val})
                    
                    sub_df = pd.DataFrame(sub_data)
                    if not sub_df.empty:
                        fig_bar_rev = px.bar(
                            sub_df.sort_values('金額', ascending=True), 
                            x='金額', y='内訳', orientation='h', 
                            title=f"{selected_year}年度 {selected_rev_label} の内訳分析"
                        )
                        fig_bar_rev.update_layout(xaxis_tickformat=",")
                        fig_bar_rev.update_xaxes(title_text="金額（千円）")
                        st.plotly_chart(fig_bar_rev, use_container_width=True)
                        st.dataframe(sub_df, use_container_width=True)
                    else:
                        st.info("選択した年度の内訳金額がすべて0円です。")
            else:
                st.info("この項目には主要な内訳データが存在しません。")

        with tab_rev2:
            st.subheader(f"{selected_pref}内 自治体歳入比較（総額）")
            df_pref_rev = df_revenue[df_revenue['都道府県'] == selected_pref].copy()
            
            if not df_pref_rev.empty:
                avail_years_pref = df_pref_rev['年度'].astype(str).unique()
                comp_year_rev = st.selectbox("比較する年度を選択", avail_years_pref, index=len(avail_years_pref)-1, key="comp_rev_year")
                
                subtab2_all, subtab2_gen, subtab2_spec = st.tabs(["🌐 歳入全体", "🏛️ 一般財源", "🎯 特定財源"])
                
                with subtab2_all:
                    plot_pref_comp_revenue(df_pref_rev, main_revenue_categories, comp_year_rev, "歳入全体", "歳入合計")
                with subtab2_gen:
                    plot_pref_comp_revenue(df_pref_rev, gen_rev_categories, comp_year_rev, "一般財源", "一般財源合計")
                with subtab2_spec:
                    plot_pref_comp_revenue(df_pref_rev, spec_rev_categories, comp_year_rev, "特定財源", "特定財源合計")
            else:
                st.info("該当する県内データが見つかりません。")

        with tab_rev3:
            st.subheader(f"{selected_pref}内 自治体歳入比較（人口1人当たり）")
            df_pref_rev = df_revenue[df_revenue['都道府県'] == selected_pref].copy()
            df_pref_ov = df_overview[df_overview['都道府県'] == selected_pref].copy()
            pop_col = get_population_col(df_overview)
            
            if not df_pref_rev.empty and pop_col:
                avail_years_pref = df_pref_rev['年度'].astype(str).unique()
                comp_year_rev_pop = st.selectbox("比較する年度を選択", avail_years_pref, index=len(avail_years_pref)-1, key="comp_rev_pop_year")
                
                subtab3_all, subtab3_gen, subtab3_spec = st.tabs(["🌐 歳入全体", "🏛️ 一般財源", "🎯 特定財源"])
                
                with subtab3_all:
                    plot_pref_comp_pop_revenue(df_pref_rev, df_pref_ov, main_revenue_categories, comp_year_rev_pop, pop_col, "歳入全体", "歳入合計")
                with subtab3_gen:
                    plot_pref_comp_pop_revenue(df_pref_rev, df_pref_ov, gen_rev_categories, comp_year_rev_pop, pop_col, "一般財源", "一般財源合計")
                with subtab3_spec:
                    plot_pref_comp_pop_revenue(df_pref_rev, df_pref_ov, spec_rev_categories, comp_year_rev_pop, pop_col, "特定財源", "特定財源合計")
            else:
                st.info("人口データまたは県内歳入データが見つかりません。")

        with tab_rev4:
            st.subheader(f"{selected_pref}内 自治体歳入分析（全期間変化率ランキング）")
            df_pref_rev = df_revenue[df_revenue['都道府県'] == selected_pref].copy()
            
            if not df_pref_rev.empty:
                all_years = sorted([str(y) for y in df_pref_rev['年度'].unique()])
                min_year = all_years[0]
                max_year = all_years[-1]
                
                st.caption(f"分析期間: **{min_year}年度** ➔ **{max_year}年度**（データ内全期間）")
                
                for c in main_revenue_categories:
                    df_pref_rev[c] = pd.to_numeric(
                        df_pref_rev[c].astype(str).str.replace(',', '').str.replace('-', '0'), 
                        errors='coerce'
                    ).fillna(0)
                df_pref_rev['歳入合計'] = df_pref_rev[main_revenue_categories].sum(axis=1)
                
                if gen_rev_categories:
                    df_pref_rev['一般財源合計'] = df_pref_rev[gen_rev_categories].sum(axis=1)
                if spec_rev_categories:
                    df_pref_rev['特定財源合計'] = df_pref_rev[spec_rev_categories].sum(axis=1)
                
                rev_options = {'歳入合計': '歳入合計（全体）'}
                if gen_rev_categories:
                    rev_options['一般財源合計'] = '一般財源合計'
                if spec_rev_categories:
                    rev_options['特定財源合計'] = '特定財源合計'
                    
                for c in main_revenue_categories:
                    rev_options[c] = c.replace('_合計', '')
                
                selected_target_col = st.selectbox("分析対象の項目を選択", list(rev_options.keys()), format_func=lambda x: rev_options[x], key="rev_analysis_target")
                
                df_min = df_pref_rev[df_pref_rev['年度'].astype(str) == min_year][['団体名', selected_target_col]].rename(columns={selected_target_col: '初期金額'})
                df_max = df_pref_rev[df_pref_rev['年度'].astype(str) == max_year][['団体名', selected_target_col]].rename(columns={selected_target_col: '最新金額'})
                
                df_growth = df_min.merge(df_max, on='団体名', how='inner')
                df_growth = df_growth[df_growth['初期金額'] > 0].copy()
                
                df_growth['増加額'] = df_growth['最新金額'] - df_growth['初期金額']
                df_growth['増加率(%)'] = ((df_growth['増加額'] / df_growth['初期金額']) * 100).round(1)
                df_growth = df_growth.sort_values('増加率(%)', ascending=False)
                
                target_name = rev_options[selected_target_col]
                
                fig_growth = px.bar(
                    df_growth, x='団体名', y='増加率(%)', text='増加率(%)',
                    title=f"{selected_pref}内自治体 {target_name} 増加率ランキング（{min_year}➔{max_year}年度）",
                    color='増加率(%)', color_continuous_scale='RdBu_r'
                )
                fig_growth.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_growth.update_layout(xaxis_title="自治体名", yaxis_title="増加率（%）")
                st.plotly_chart(fig_growth, use_container_width=True)
                
                st.markdown(f"#### {target_name} 全期間変化率データテーブル")
                st.dataframe(
                    df_growth.rename(columns={
                        '初期金額': f'{min_year}年度金額(千円)',
                        '最新金額': f'{max_year}年度金額(千円)',
                        '増加額': '増加額(千円)'
                    }),
                    use_container_width=True
                )
            else:
                st.info("該当する県内データが見つかりません。")

# ==========================================
# メニュー3: 性質別歳出
# ==========================================
elif menu == "性質別歳出":
    st.markdown("### 性質別歳出の推移と分析")
    if not df_exp_city.empty:
        bukken_cols = ['物件費_賃金', '物件費_旅費', '物件費_交際費', '物件費_需用費', '物件費_役務費', '物件費_備品購入費', '物件費_委託料', '物件費_その他']
        
        main_categories = [
            '人件費_合計', '物件費_合計', '維持補修費_合計', '扶助費_合計', '補助費等_合計', 
            '普通建設事業費_合計', '災害復旧事業費_合計', '失業対策事業費_合計', 
            '公債費_合計', '積立金_合計', '投資及び出資金_合計', '貸付金_合計', '繰出金_合計'
        ]
        main_categories = [c for c in main_categories if c in df_exp_nature.columns]

        tab_exp1, tab_exp2, tab_exp3, tab_exp4 = st.tabs([
            "📈 自治体単体分析", 
            "📊 同一県内自治体比較（総額）", 
            "👥 同一県内自治体比較（1人当たり）",
            "🔍 歳出分析"
        ])

        with tab_exp1:
            df_exp_city_clean = df_exp_city.copy()
            for c in bukken_cols:
                if c in df_exp_city_clean.columns:
                    df_exp_city_clean[c] = pd.to_numeric(df_exp_city_clean[c].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce')
            if '物件費_合計' in df_exp_city_clean.columns and all(c in df_exp_city_clean.columns for c in bukken_cols):
                calc_buk = df_exp_city_clean[bukken_cols].sum(axis=1)
                df_exp_city_clean.loc[df_exp_city_clean['物件費_合計'] < 10000, '物件費_合計'] = calc_buk[df_exp_city_clean['物件費_合計'] < 10000]

            st.subheader("1. 歳出大項目の時系列推移")
            if main_categories:
                df_plot = df_exp_city_clean.copy()
                for c in main_categories:
                    df_plot[c] = pd.to_numeric(df_plot[c].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce').fillna(0)
                
                df_plot['歳出合計'] = df_plot[main_categories].sum(axis=1)
                df_melt = df_plot.melt(id_vars=['年度', '歳出合計'], value_vars=main_categories, var_name='項目_raw', value_name='金額')
                df_melt['項目名'] = df_melt['項目_raw'].str.replace('_合計', '')
                df_melt['割合(%)'] = (df_melt['金額'] / df_melt['歳出合計'] * 100).round(1)

                display_categories = [c.replace('_合計', '') for c in main_categories]

                fig_exp_line = px.bar(
                    df_melt, x='年度', y='金額', color='項目名',
                    title="性質別歳出構成の推移", barmode='stack',
                    category_orders={'項目名': display_categories},
                    custom_data=['項目名', '割合(%)']
                )
                fig_exp_line.update_layout(yaxis_tickformat=",")
                fig_exp_line.update_yaxes(title_text="金額（千円）")
                fig_exp_line.update_traces(
                    hovertemplate="<b>項目名: %{customdata[0]}</b><br>金額: %{y:,.0f} 千円<br>構成比: %{customdata[1]}%<extra></extra>"
                )
                for i, row in df_plot.iterrows():
                    if row['歳出合計'] > 0:
                        fig_exp_line.add_annotation(
                            x=row['年度'], y=row['歳出合計'],
                            text=f"{row['歳出合計']:,.0f}", showarrow=False, yshift=10, font=dict(size=10)
                        )
                st.plotly_chart(fig_exp_line, use_container_width=True)

            st.markdown("---")
            st.subheader("2. 項目別 内訳分析")
            
            available_exp_years = df_exp_city_clean['年度'].astype(str).unique()
            selected_year_exp = st.selectbox("確認したい年度を選択", available_exp_years, index=len(available_exp_years)-1, key="exp_year")
            
            category_labels = {c: c.replace('_合計', '') for c in main_categories}
            selected_label = st.selectbox("深掘りする大項目を選択", list(category_labels.values()), key="exp_main_label")
            selected_main_exp = [k for k, v in category_labels.items() if v == selected_label][0]
            
            prefix = selected_main_exp.replace('_合計', '') + '_'
            sub_categories = [c for c in df_exp_city_clean.columns if c.startswith(prefix) and c != selected_main_exp and '小計' not in c]
            
            if sub_categories:
                df_year_exp = df_exp_city_clean[df_exp_city_clean['年度'].astype(str) == str(selected_year_exp)]
                if not df_year_exp.empty:
                    row_data = df_year_exp.iloc[0]
                    
                    if prefix == '人件費_':
                        groups = {
                            '議員報酬・委員等報酬': [c for c in sub_categories if '議員報酬' in c or ('委員等報酬' in c and '会計年度' not in c)],
                            '特別職給与': [c for c in sub_categories if '特別職の給与' in c],
                            '任期の定めのない常勤職員': [c for c in sub_categories if '任期の定めのない常勤職員' in c],
                            '任期付職員': [c for c in sub_categories if '任期付職員' in c],
                            '再任用職員': [c for c in sub_categories if '再任用職員' in c],
                            '会計年度任用職員': [c for c in sub_categories if '会計年度任用職員' in c or 'パートタイム' in c],
                            '共済組合等負担金': [c for c in sub_categories if '共済組合' in c],
                            '退職金': [c for c in sub_categories if '退職金' in c],
                            '恩給・災害補償・その他': [c for c in sub_categories if '恩給' in c or '災害補償' in c or c == '人件費_その他']
                        }
                        
                        grouped_result = []
                        assigned_cols = set()
                        for g_name, cols in groups.items():
                            s = 0
                            for vc in cols:
                                if vc in row_data.index:
                                    val = pd.to_numeric(str(row_data[vc]).replace(',', '').replace('-', '0'), errors='coerce')
                                    if not pd.isna(val):
                                        s += val
                                    assigned_cols.add(vc)
                            if s > 0:
                                grouped_result.append({'区分': g_name, '金額': s})
                                
                        rem_cols = [c for c in sub_categories if c not in assigned_cols]
                        rem_sum = 0
                        for rc in rem_cols:
                            val = pd.to_numeric(str(row_data[rc]).replace(',', '').replace('-', '0'), errors='coerce')
                            if not pd.isna(val):
                                rem_sum += val
                        if rem_sum > 0:
                            grouped_result.append({'区分': 'その他', '金額': rem_sum})
                            
                        df_grouped = pd.DataFrame(grouped_result)
                    else:
                        grouped_dict = {}
                        for sub_col in sub_categories:
                            rel_name = sub_col[len(prefix):]
                            parts = rel_name.split('_')
                            group_name = parts[0]
                            val = pd.to_numeric(str(row_data[sub_col]).replace(',', '').replace('-', '0'), errors='coerce')
                            if pd.isna(val):
                                val = 0
                            grouped_dict[group_name] = grouped_dict.get(group_name, 0) + val
                        
                        df_grouped = pd.DataFrame([{'区分': k, '金額': v} for k, v in grouped_dict.items() if v > 0])
                    
                    if not df_grouped.empty:
                        fig_bar_exp = px.bar(
                            df_grouped.sort_values('金額', ascending=True), 
                            x='金額', y='区分', orientation='h', 
                            title=f"{selected_year_exp}年度 {selected_label} の内訳分析"
                        )
                        fig_bar_exp.update_layout(xaxis_tickformat=",")
                        fig_bar_exp.update_xaxes(title_text="金額（千円）")
                        st.plotly_chart(fig_bar_exp, use_container_width=True)
                        st.dataframe(df_grouped, use_container_width=True)
                    else:
                        st.info("選択した年度の内訳金額がすべて0円です。")
            else:
                st.info("この項目には主要な内訳データが存在しません。")

        with tab_exp2:
            st.subheader(f"{selected_pref}内 自治体性質別歳出比較（総額）")
            df_pref_exp = df_exp_nature[df_exp_nature['都道府県'] == selected_pref].copy()
            
            if not df_pref_exp.empty:
                avail_years_exp_pref = df_pref_exp['年度'].astype(str).unique()
                comp_year_exp = st.selectbox("比較する年度を選択", avail_years_exp_pref, index=len(avail_years_exp_pref)-1, key="comp_exp_year")
                
                df_comp_exp = df_pref_exp[df_pref_exp['年度'].astype(str) == str(comp_year_exp)].copy()
                
                for c in main_categories:
                    df_comp_exp[c] = pd.to_numeric(df_comp_exp[c].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce').fillna(0)
                
                df_comp_exp['歳出合計'] = df_comp_exp[main_categories].sum(axis=1)
                df_comp_exp = df_comp_exp.sort_values('歳出合計', ascending=False)
                sorted_cities_exp = df_comp_exp['団体名'].tolist()
                
                df_melt_comp_exp = df_comp_exp.melt(id_vars=['団体名', '歳出合計'], value_vars=main_categories, var_name='項目_raw', value_name='金額')
                df_melt_comp_exp['項目名'] = df_melt_comp_exp['項目_raw'].str.replace('_合計', '')
                df_melt_comp_exp['割合(%)'] = (df_melt_comp_exp['金額'] / df_melt_comp_exp['歳出合計'] * 100).round(1)

                fig_comp_exp = px.bar(
                    df_melt_comp_exp, x='団体名', y='金額', color='項目名',
                    title=f"{selected_pref}（{comp_year_exp}年度）自治体別性質別歳出構成比較（総額・大きい順）", barmode='stack',
                    category_orders={'団体名': sorted_cities_exp, '項目名': [c.replace('_合計', '') for c in main_categories]},
                    custom_data=['項目名', '割合(%)']
                )
                fig_comp_exp.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
                fig_comp_exp.update_traces(
                    hovertemplate="<b>自治体: %{x}</b><br>項目名: %{customdata[0]}<br>金額: %{y:,.0f} 千円<br>構成比: %{customdata[1]}%<extra></extra>"
                )
                st.plotly_chart(fig_comp_exp, use_container_width=True)
                
                st.markdown("#### 性質別歳出比較データテーブル（総額）")
                st.dataframe(df_comp_exp[['団体名', '歳出合計'] + main_categories], use_container_width=True)
            else:
                st.info("該当する県内データが見つかりません。")

        with tab_exp3:
            st.subheader(f"{selected_pref}内 自治体性質別歳出比較（人口1人当たり）")
            df_pref_exp = df_exp_nature[df_exp_nature['都道府県'] == selected_pref].copy()
            pop_col = get_population_col(df_overview)
            
            if not df_pref_exp.empty and pop_col:
                avail_years_exp_pref = df_pref_exp['年度'].astype(str).unique()
                comp_year_exp_pop = st.selectbox("比較する年度を選択", avail_years_exp_pref, index=len(avail_years_exp_pref)-1, key="comp_exp_pop_year")
                
                df_comp_exp = df_pref_exp[df_pref_exp['年度'].astype(str) == str(comp_year_exp_pop)].copy()
                df_pref_ov = df_overview[(df_overview['都道府県'] == selected_pref) & (df_overview['年度'].astype(str) == str(comp_year_exp_pop))].copy()
                df_pref_ov['人口_num'] = pd.to_numeric(df_pref_ov[pop_col].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce').fillna(0)
                
                df_comp_exp_pop = df_comp_exp.merge(df_pref_ov[['団体名', '人口_num']], on='団体名', how='left')
                df_comp_exp_pop['人口_num'] = df_comp_exp_pop['人口_num'].fillna(0)
                df_comp_exp_pop = df_comp_exp_pop[df_comp_exp_pop['人口_num'] > 0].copy()
                
                if not df_comp_exp_pop.empty:
                    for c in main_categories:
                        df_comp_exp_pop[c] = pd.to_numeric(df_comp_exp_pop[c].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce').fillna(0)
                        df_comp_exp_pop[c + '_1人当たり'] = (df_comp_exp_pop[c] / df_comp_exp_pop['人口_num']).round(2)
                    
                    df_comp_exp_pop['歳出合計'] = df_comp_exp_pop[main_categories].sum(axis=1)
                    df_comp_exp_pop['1人当たり歳出合計'] = (df_comp_exp_pop['歳出合計'] / df_comp_exp_pop['人口_num']).round(2)
                    
                    df_comp_exp_pop = df_comp_exp_pop.sort_values('1人当たり歳出合計', ascending=False)
                    sorted_cities_exp_pop = df_comp_exp_pop['団体名'].tolist()
                    
                    per_capita_cols_exp = [c + '_1人当たり' for c in main_categories]
                    df_melt_comp_exp_pop = df_comp_exp_pop.melt(
                        id_vars=['団体名', '1人当たり歳出合計', '人口_num'], 
                        value_vars=per_capita_cols_exp, 
                        var_name='項目_raw', 
                        value_name='1人当たり金額'
                    )
                    df_melt_comp_exp_pop['項目名'] = df_melt_comp_exp_pop['項目_raw'].str.replace('_合計', '').str.replace('_1人当たり', '')
                    df_melt_comp_exp_pop['割合(%)'] = (df_melt_comp_exp_pop['1人当たり金額'] / df_melt_comp_exp_pop['1人当たり歳出合計'] * 100).round(1)

                    fig_comp_exp_pop = px.bar(
                        df_melt_comp_exp_pop, x='団体名', y='1人当たり金額', color='項目名',
                        title=f"{selected_pref}（{comp_year_exp_pop}年度）自治体別1人当たり性質別歳出構成比較（大きい順 / 人口参照: {pop_col}）", barmode='stack',
                        category_orders={'団体名': sorted_cities_exp_pop, '項目名': [c.replace('_合計', '') for c in main_categories]},
                        custom_data=['項目名', '割合(%)']
                    )
                    fig_comp_exp_pop.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
                    fig_comp_exp_pop.update_traces(
                        hovertemplate="<b>自治体: %{x}</b><br>項目名: %{customdata[0]}<br>1人当たり金額: %{y:,.2f} 千円/人<br>構成比: %{customdata[1]}%<extra></extra>"
                    )
                    st.plotly_chart(fig_comp_exp_pop, use_container_width=True)
                    
                    st.markdown("#### 1人当たり性質別歳出比較データテーブル")
                    disp_cols_exp_pop = ['団体名', '人口_num', '1人当たり歳出合計'] + per_capita_cols_exp
                    rename_dict_exp = {'人口_num': f'人口({pop_col})', '1人当たり歳出合計': '1人当たり歳出合計(千円)'}
                    for c in per_capita_cols_exp:
                        rename_dict_exp[c] = c.replace('_合計', '').replace('_1人当たり', '') + '(千円/人)'
                    
                    st.dataframe(df_comp_exp_pop[disp_cols_exp_pop].rename(columns=rename_dict_exp), use_container_width=True)
                else:
                    st.warning("該当年度の人口データが見つからないか、全自治体の人口が0です。")
            else:
                st.info("人口データまたは県内性質別歳出データが見つかりません。")

        with tab_exp4:
            st.subheader(f"{selected_pref}内 自治体性質別歳出分析（全期間変化率ランキング）")
            df_pref_exp = df_exp_nature[df_exp_nature['都道府県'] == selected_pref].copy()
            
            if not df_pref_exp.empty:
                all_exp_years = sorted([str(y) for y in df_pref_exp['年度'].unique()])
                min_exp_year, max_exp_year = all_exp_years[0], all_exp_years[-1]
                
                st.caption(f"分析期間: **{min_exp_year}年度** ➔ **{max_exp_year}年度**（データ内全期間）")
                
                exp_options = {'歳出合計': '歳出合計'}
                for c in main_categories:
                    exp_options[c] = c.replace('_合計', '')
                
                selected_exp_target = st.selectbox("分析対象の項目を選択", list(exp_options.keys()), format_func=lambda x: exp_options[x], key="exp_analysis_target")
                
                if selected_exp_target == '歳出合計':
                    for c in main_categories:
                        df_pref_exp[c] = pd.to_numeric(df_pref_exp[c].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce').fillna(0)
                    df_pref_exp['歳出合計'] = df_pref_exp[main_categories].sum(axis=1)
                else:
                    df_pref_exp[selected_exp_target] = pd.to_numeric(df_pref_exp[selected_exp_target].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce').fillna(0)
                
                df_exp_min = df_pref_exp[df_pref_exp['年度'].astype(str) == min_exp_year][['団体名', selected_exp_target]].rename(columns={selected_exp_target: '初期金額'})
                df_exp_max = df_pref_exp[df_pref_exp['年度'].astype(str) == max_exp_year][['団体名', selected_exp_target]].rename(columns={selected_exp_target: '最新金額'})
                
                df_exp_growth = df_exp_min.merge(df_exp_max, on='団体名', how='inner')
                df_exp_growth = df_exp_growth[df_exp_growth['初期金額'] > 0].copy()
                
                df_exp_growth['増加額'] = df_exp_growth['最新金額'] - df_exp_growth['初期金額']
                df_exp_growth['増加率(%)'] = ((df_exp_growth['増加額'] / df_exp_growth['初期金額']) * 100).round(1)
                df_exp_growth = df_exp_growth.sort_values('増加率(%)', ascending=False)
                
                exp_target_name = exp_options[selected_exp_target]
                
                fig_exp_growth = px.bar(
                    df_exp_growth, x='団体名', y='増加率(%)', text='増加率(%)',
                    title=f"{selected_pref}内自治体 {exp_target_name} 増加率ランキング（{min_exp_year}➔{max_exp_year}年度）",
                    color='増加率(%)', color_continuous_scale='RdBu_r'
                )
                fig_exp_growth.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_exp_growth.update_layout(xaxis_title="自治体名", yaxis_title="増加率（%）")
                st.plotly_chart(fig_exp_growth, use_container_width=True)
                
                st.markdown(f"#### {exp_target_name} 全期間変化率データテーブル")
                st.dataframe(
                    df_exp_growth.rename(columns={
                        '初期金額': f'{min_exp_year}年度金額(千円)',
                        '最新金額': f'{max_exp_year}年度金額(千円)',
                        '増加額': '増加額(千円)'
                    }),
                    use_container_width=True
                )
            else:
                st.info("該当する県内データが見つかりません。")
    else:
        st.warning("対象自治体の性質別歳出データが存在しません。")

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
            "📊 同一県内自治体比較（総額）", 
            "👥 同一県内自治体比較（1人当たり）",
            "🔍 歳出分析"
        ])

        with tab_purp1:
            st.subheader("1. 目的別歳出大項目の時系列推移")
            if main_purp_categories:
                df_plot_purp = df_purp_city.copy()
                for c in main_purp_categories:
                    df_plot_purp[c] = pd.to_numeric(df_plot_purp[c].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce').fillna(0)
                
                df_plot_purp['目的別歳出合計'] = df_plot_purp[main_purp_categories].sum(axis=1)
                df_melt_purp = df_plot_purp.melt(id_vars=['年度', '目的別歳出合計'], value_vars=main_purp_categories, var_name='項目_raw', value_name='金額')
                df_melt_purp['項目名'] = df_melt_purp['項目_raw'].str.replace('_合計', '')
                df_melt_purp['割合(%)'] = (df_melt_purp['金額'] / df_melt_purp['目的別歳出合計'] * 100).round(1)

                display_purp_categories = [c.replace('_合計', '') for c in main_purp_categories]

                fig_purp_line = px.bar(
                    df_melt_purp, x='年度', y='金額', color='項目名',
                    title="目的別歳出構成の推移", barmode='stack',
                    category_orders={'項目名': display_purp_categories},
                    custom_data=['項目名', '割合(%)']
                )
                fig_purp_line.update_layout(yaxis_tickformat=",")
                fig_purp_line.update_yaxes(title_text="金額（千円）")
                fig_purp_line.update_traces(
                    hovertemplate="<b>項目名: %{customdata[0]}</b><br>金額: %{y:,.0f} 千円<br>構成比: %{customdata[1]}%<extra></extra>"
                )
                
                for i, row in df_plot_purp.iterrows():
                    if row['目的別歳出合計'] > 0:
                        fig_purp_line.add_annotation(
                            x=row['年度'], y=row['目的別歳出合計'],
                            text=f"{row['目的別歳出合計']:,.0f}", showarrow=False, yshift=10, font=dict(size=10)
                        )
                st.plotly_chart(fig_purp_line, use_container_width=True)

            st.markdown("---")
            st.subheader("2. 項目別 内訳分析")
            
            available_purp_years = df_purp_city['年度'].astype(str).unique()
            selected_year_purp = st.selectbox("確認したい年度を選択", available_purp_years, index=len(available_purp_years)-1, key="purp_year")
            
            purp_category_labels = {c: c.replace('_合計', '') for c in main_purp_categories}
            selected_purp_label = st.selectbox("深掘りする大項目を選択", list(purp_category_labels.values()), key="purp_main_label")
            selected_main_purp = [k for k, v in purp_category_labels.items() if v == selected_purp_label][0]
            
            prefix_purp = selected_main_purp.replace('_合計', '') + '_'
            sub_purp_categories = [c for c in df_purp_city.columns if c.startswith(prefix_purp) and c != selected_main_purp and '小計' not in c]
            
            if sub_purp_categories:
                df_year_purp = df_purp_city[df_purp_city['年度'].astype(str) == str(selected_year_purp)]
                if not df_year_purp.empty:
                    row_data = df_year_purp.iloc[0]
                    sub_purp_data = []
                    for sc in sub_purp_categories:
                        val = pd.to_numeric(str(row_data[sc]).replace(',', '').replace('-', '0'), errors='coerce')
                        if not pd.isna(val) and val > 0:
                            sub_purp_data.append({'内訳': sc.replace(prefix_purp, ''), '金額': val})
                    
                    sub_purp_df = pd.DataFrame(sub_purp_data)
                    if not sub_purp_df.empty:
                        fig_bar_purp = px.bar(
                            sub_purp_df.sort_values('金額', ascending=True), 
                            x='金額', y='内訳', orientation='h', 
                            title=f"{selected_year_purp}年度 {selected_purp_label} の内訳分析"
                        )
                        fig_bar_purp.update_layout(xaxis_tickformat=",")
                        fig_bar_purp.update_xaxes(title_text="金額（千円）")
                        st.plotly_chart(fig_bar_purp, use_container_width=True)
                        st.dataframe(sub_purp_df, use_container_width=True)
                    else:
                        st.info("選択した年度の内訳金額がすべて0円です。")
            else:
                st.info("この項目には主要な内訳データが存在しません。")

        with tab_purp2:
            st.subheader(f"{selected_pref}内 自治体目的別歳出比較（総額）")
            df_pref_purp = df_exp_purpose[df_exp_purpose['都道府県'] == selected_pref].copy()
            
            if not df_pref_purp.empty:
                avail_years_purp_pref = df_pref_purp['年度'].astype(str).unique()
                comp_year_purp = st.selectbox("比較する年度を選択", avail_years_purp_pref, index=len(avail_years_purp_pref)-1, key="comp_purp_year")
                
                df_comp_purp = df_pref_purp[df_pref_purp['年度'].astype(str) == str(comp_year_purp)].copy()
                
                for c in main_purp_categories:
                    df_comp_purp[c] = pd.to_numeric(df_comp_purp[c].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce').fillna(0)
                
                df_comp_purp['目的別歳出合計'] = df_comp_purp[main_purp_categories].sum(axis=1)
                df_comp_purp = df_comp_purp.sort_values('目的別歳出合計', ascending=False)
                sorted_cities_purp = df_comp_purp['団体名'].tolist()
                
                df_melt_comp_purp = df_comp_purp.melt(id_vars=['団体名', '目的別歳出合計'], value_vars=main_purp_categories, var_name='項目_raw', value_name='金額')
                df_melt_comp_purp['項目名'] = df_melt_comp_purp['項目_raw'].str.replace('_合計', '')
                df_melt_comp_purp['割合(%)'] = (df_melt_comp_purp['金額'] / df_melt_comp_purp['目的別歳出合計'] * 100).round(1)

                fig_comp_purp = px.bar(
                    df_melt_comp_purp, x='団体名', y='金額', color='項目名',
                    title=f"{selected_pref}（{comp_year_purp}年度）自治体別目的別歳出構成比較（総額・大きい順）", barmode='stack',
                    category_orders={'団体名': sorted_cities_purp, '項目名': [c.replace('_合計', '') for c in main_purp_categories]},
                    custom_data=['項目名', '割合(%)']
                )
                fig_comp_purp.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
                fig_comp_purp.update_traces(
                    hovertemplate="<b>自治体: %{x}</b><br>項目名: %{customdata[0]}<br>金額: %{y:,.0f} 千円<br>構成比: %{customdata[1]}%<extra></extra>"
                )
                st.plotly_chart(fig_comp_purp, use_container_width=True)
                
                st.markdown("#### 目的別歳出比較データテーブル（総額）")
                st.dataframe(df_comp_purp[['団体名', '目的別歳出合計'] + main_purp_categories], use_container_width=True)
            else:
                st.info("該当する県内データが見つかりません。")

        with tab_purp3:
            st.subheader(f"{selected_pref}内 自治体目的別歳出比較（人口1人当たり）")
            df_pref_purp = df_exp_purpose[df_exp_purpose['都道府県'] == selected_pref].copy()
            pop_col = get_population_col(df_overview)
            
            if not df_pref_purp.empty and pop_col:
                avail_years_purp_pref = df_pref_purp['年度'].astype(str).unique()
                comp_year_purp_pop = st.selectbox("比較する年度を選択", avail_years_purp_pref, index=len(avail_years_purp_pref)-1, key="comp_purp_pop_year")
                
                df_comp_purp = df_pref_purp[df_pref_purp['年度'].astype(str) == str(comp_year_purp_pop)].copy()
                df_pref_ov = df_overview[(df_overview['都道府県'] == selected_pref) & (df_overview['年度'].astype(str) == str(comp_year_purp_pop))].copy()
                df_pref_ov['人口_num'] = pd.to_numeric(df_pref_ov[pop_col].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce').fillna(0)
                
                df_comp_purp_pop = df_comp_purp.merge(df_pref_ov[['団体名', '人口_num']], on='団体名', how='left')
                df_comp_purp_pop['人口_num'] = df_comp_purp_pop['人口_num'].fillna(0)
                df_comp_purp_pop = df_comp_purp_pop[df_comp_purp_pop['人口_num'] > 0].copy()
                
                if not df_comp_purp_pop.empty:
                    for c in main_purp_categories:
                        df_comp_purp_pop[c] = pd.to_numeric(df_comp_purp_pop[c].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce').fillna(0)
                        df_comp_purp_pop[c + '_1人当たり'] = (df_comp_purp_pop[c] / df_comp_purp_pop['人口_num']).round(2)
                    
                    df_comp_purp_pop['目的別歳出合計'] = df_comp_purp_pop[main_purp_categories].sum(axis=1)
                    df_comp_purp_pop['1人当たり目的別歳出合計'] = (df_comp_purp_pop['目的別歳出合計'] / df_comp_purp_pop['人口_num']).round(2)
                    
                    df_comp_purp_pop = df_comp_purp_pop.sort_values('1人当たり目的別歳出合計', ascending=False)
                    sorted_cities_purp_pop = df_comp_purp_pop['団体名'].tolist()
                    
                    per_capita_cols_purp = [c + '_1人当たり' for c in main_purp_categories]
                    df_melt_comp_purp_pop = df_comp_purp_pop.melt(
                        id_vars=['団体名', '1人当たり目的別歳出合計', '人口_num'], 
                        value_vars=per_capita_cols_purp, 
                        var_name='項目_raw', 
                        value_name='1人当たり金額'
                    )
                    df_melt_comp_purp_pop['項目名'] = df_melt_comp_purp_pop['項目_raw'].str.replace('_合計', '').str.replace('_1人当たり', '')
                    df_melt_comp_purp_pop['割合(%)'] = (df_melt_comp_purp_pop['1人当たり金額'] / df_melt_comp_purp_pop['1人当たり目的別歳出合計'] * 100).round(1)

                    fig_comp_purp_pop = px.bar(
                        df_melt_comp_purp_pop, x='団体名', y='1人当たり金額', color='項目名',
                        title=f"{selected_pref}（{comp_year_purp_pop}年度）自治体別1人当たり目的別歳出構成比較（大きい順 / 人口参照: {pop_col}）", barmode='stack',
                        category_orders={'団体名': sorted_cities_purp_pop, '項目名': [c.replace('_合計', '') for c in main_purp_categories]},
                        custom_data=['項目名', '割合(%)']
                    )
                    fig_comp_purp_pop.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
                    fig_comp_purp_pop.update_traces(
                        hovertemplate="<b>自治体: %{x}</b><br>項目名: %{customdata[0]}<br>1人当たり金額: %{y:,.2f} 千円/人<br>構成比: %{customdata[1]}%<extra></extra>"
                    )
                    st.plotly_chart(fig_comp_purp_pop, use_container_width=True)
                    
                    st.markdown("#### 1人当たり目的別歳出比較データテーブル")
                    disp_cols_purp_pop = ['団体名', '人口_num', '1人当たり目的別歳出合計'] + per_capita_cols_purp
                    rename_dict_purp = {'人口_num': f'人口({pop_col})', '1人当たり目的別歳出合計': '1人当たり目的別歳出合計(千円)'}
                    for c in per_capita_cols_purp:
                        rename_dict_purp[c] = c.replace('_合計', '').replace('_1人当たり', '') + '(千円/人)'
                    
                    st.dataframe(df_comp_purp_pop[disp_cols_purp_pop].rename(columns=rename_dict_purp), use_container_width=True)
                else:
                    st.warning("該当年度の人口データが見つからないか、全自治体の人口が0です。")
            else:
                st.info("人口データまたは県内目的別歳出データが見つかりません。")

        with tab_purp4:
            st.subheader(f"{selected_pref}内 自治体目的別歳出分析（全期間変化率ランキング）")
            df_pref_purp = df_exp_purpose[df_exp_purpose['都道府県'] == selected_pref].copy()
            
            if not df_pref_purp.empty:
                all_purp_years = sorted([str(y) for y in df_pref_purp['年度'].unique()])
                min_purp_year, max_purp_year = all_purp_years[0], all_purp_years[-1]
                
                st.caption(f"分析期間: **{min_purp_year}年度** ➔ **{max_purp_year}年度**（データ内全期間）")
                
                purp_options = {'目的別歳出合計': '目的別歳出合計'}
                for c in main_purp_categories:
                    purp_options[c] = c.replace('_合計', '')
                
                selected_purp_target = st.selectbox("分析対象の項目を選択", list(purp_options.keys()), format_func=lambda x: purp_options[x], key="purp_analysis_target")
                
                if selected_purp_target == '目的別歳出合計':
                    for c in main_purp_categories:
                        df_pref_purp[c] = pd.to_numeric(df_pref_purp[c].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce').fillna(0)
                    df_pref_purp['目的別歳出合計'] = df_pref_purp[main_purp_categories].sum(axis=1)
                else:
                    df_pref_purp[selected_purp_target] = pd.to_numeric(df_pref_purp[selected_purp_target].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce').fillna(0)
                
                df_purp_min = df_pref_purp[df_pref_purp['年度'].astype(str) == min_purp_year][['団体名', selected_purp_target]].rename(columns={selected_purp_target: '初期金額'})
                df_purp_max = df_pref_purp[df_pref_purp['年度'].astype(str) == max_purp_year][['団体名', selected_purp_target]].rename(columns={selected_purp_target: '最新金額'})
                
                df_purp_growth = df_purp_min.merge(df_purp_max, on='団体名', how='inner')
                df_purp_growth = df_purp_growth[df_purp_growth['初期金額'] > 0].copy()
                
                df_purp_growth['増加額'] = df_purp_growth['最新金額'] - df_purp_growth['初期金額']
                df_purp_growth['増加率(%)'] = ((df_purp_growth['増加額'] / df_purp_growth['初期金額']) * 100).round(1)
                df_purp_growth = df_purp_growth.sort_values('増加率(%)', ascending=False)
                
                purp_target_name = purp_options[selected_purp_target]
                
                fig_purp_growth = px.bar(
                    df_purp_growth, x='団体名', y='増加率(%)', text='増加率(%)',
                    title=f"{selected_pref}内自治体 {purp_target_name} 増加率ランキング（{min_purp_year}➔{max_purp_year}年度）",
                    color='増加率(%)', color_continuous_scale='RdBu_r'
                )
                fig_purp_growth.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_purp_growth.update_layout(xaxis_title="自治体名", yaxis_title="増加率（%）")
                st.plotly_chart(fig_purp_growth, use_container_width=True)
                
                st.markdown(f"#### {purp_target_name} 全期間変化率データテーブル")
                st.dataframe(
                    df_purp_growth.rename(columns={
                        '初期金額': f'{min_purp_year}年度金額(千円)',
                        '最新金額': f'{max_purp_year}年度金額(千円)',
                        '増加額': '増加額(千円)'
                    }),
                    use_container_width=True
                )
            else:
                st.info("該当する県内データが見つかりません。")
    else:
        st.warning("対象自治体の目的別歳出データが存在しません。")

# ==========================================
# メニュー5: 地方債
# ==========================================
elif menu == "地方債":
    st.markdown("### 地方債・積立金（基金）現在高の推移と分析")
    if not df_bonds_city.empty:
        bonds_main_cats = [
            '地方債現在高_合計', '積立金現在高_合計', '債務負担行為額(翌年度以降支出予定額)_合計',
            '公営企業等に対する繰出金_合計'
        ]
        
        fund_sub_cats = [
            '積立金現在高_財政調整基金', '積立金現在高_減債基金', '積立金現在高_その他特定目的基金'
        ]
        fund_sub_cats = [c for c in fund_sub_cats if c in df_bonds_city.columns]

        pub_sub_cats = [
            '公営企業等に対する繰出金_うち上水道事業会計', 
            '公営企業等に対する繰出金_うち交通事業会計', 
            '公営企業等に対する繰出金_うち病院事業会計', 
            '公営企業等に対する繰出金_うち下水道事業会計'
        ]
        pub_sub_cats = [c for c in pub_sub_cats if c in df_bonds_city.columns]

        tab_bonds1, tab_bonds2, tab_bonds3, tab_bonds4 = st.tabs([
            "📈 自治体単体分析", 
            "📊 同一県内自治体比較（総額）", 
            "👥 同一県内自治体比較（1人当たり）",
            "🔍 地方債・基金分析"
        ])

        # --- Tab 1: 自治体単体分析 ---
        with tab_bonds1:
            st.subheader("1. 地方債・基金・公営企業繰出金の推移")
            subtab1_main, subtab1_fund, subtab1_pub = st.tabs(["🏛️ 地方債・積立金（全体）", "💰 基金（積立金）内訳", "🏥 公営企業等繰出金内訳"])
            
            with subtab1_main:
                df_plot_b = df_bonds_city.copy()
                fig_b = go.Figure()
                
                if '地方債現在高_合計' in df_plot_b.columns:
                    fig_b.add_trace(go.Scatter(
                        x=df_plot_b['年度'], y=df_plot_b['地方債現在高_合計'],
                        mode='lines+markers', name='地方債現在高_合計', line=dict(color='red', width=3)
                    ))
                if '積立金現在高_合計' in df_plot_b.columns:
                    fig_b.add_trace(go.Scatter(
                        x=df_plot_b['年度'], y=df_plot_b['積立金現在高_合計'],
                        mode='lines+markers', name='積立金現在高_合計（基金）', line=dict(color='green', width=3)
                    ))
                if '債務負担行為額(翌年度以降支出予定額)_合計' in df_plot_b.columns:
                    fig_b.add_trace(go.Scatter(
                        x=df_plot_b['年度'], y=df_plot_b['債務負担行為額(翌年度以降支出予定額)_合計'],
                        mode='lines+markers', name='債務負担行為額_合計', line=dict(color='purple', dash='dash')
                    ))
                
                if all(c in df_plot_b.columns for c in ['地方債現在高_合計', '積立金現在高_合計']):
                    df_plot_b['実質将来負担残高_推計'] = df_plot_b['地方債現在高_合計'] + df_plot_b.get('債務負担行為額(翌年度以降支出予定額)_合計', 0) - df_plot_b['積立金現在高_合計']
                    fig_b.add_trace(go.Scatter(
                        x=df_plot_b['年度'], y=df_plot_b['実質将来負担残高_推計'],
                        mode='lines+markers', name='実質将来負担残高（推計）', line=dict(color='blue', dash='dot', width=2)
                    ))

                fig_b.update_layout(
                    title="地方債現在高 vs 積立金現在高（基金）の推移",
                    xaxis_title="年度",
                    yaxis_title="金額（千円）",
                    yaxis_tickformat=",",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig_b, use_container_width=True)
                st.caption("※実質将来負担残高（推計）＝ 地方債現在高 ＋ 債務負担行為額 － 積立金現在高（基金）")

            with subtab1_fund:
                if fund_sub_cats:
                    df_plot_fund = df_bonds_city.copy()
                    df_plot_fund['積立金合計_calc'] = df_plot_fund[fund_sub_cats].sum(axis=1)
                    df_melt_fund = df_plot_fund.melt(id_vars=['年度', '積立金合計_calc'], value_vars=fund_sub_cats, var_name='項目_raw', value_name='金額')
                    df_melt_fund['項目名'] = df_melt_fund['項目_raw'].str.replace('積立金現在高_', '')
                    df_melt_fund['割合(%)'] = (df_melt_fund['金額'] / df_melt_fund['積立金合計_calc'] * 100).fillna(0).round(1)

                    fig_fund = px.bar(
                        df_melt_fund, x='年度', y='金額', color='項目名',
                        title="基金（積立金）内訳推移", barmode='stack',
                        custom_data=['項目名', '割合(%)']
                    )
                    fig_fund.update_layout(yaxis_tickformat=",", yaxis_title="金額（千円）")
                    fig_fund.update_traces(
                        hovertemplate="<b>項目名: %{customdata[0]}</b><br>金額: %{y:,.0f} 千円<br>構成比: %{customdata[1]}%<extra></extra>"
                    )
                    for i, row in df_plot_fund.iterrows():
                        if row['積立金合計_calc'] > 0:
                            fig_fund.add_annotation(
                                x=row['年度'], y=row['積立金合計_calc'],
                                text=f"{row['積立金合計_calc']:,.0f}", showarrow=False, yshift=10, font=dict(size=10)
                            )
                    st.plotly_chart(fig_fund, use_container_width=True)
                else:
                    st.info("基金の内訳データが見つかりません。")

            with subtab1_pub:
                if pub_sub_cats:
                    df_plot_pub = df_bonds_city.copy()
                    df_plot_pub['繰出金合計_calc'] = df_plot_pub[pub_sub_cats].sum(axis=1)
                    df_melt_pub = df_plot_pub.melt(id_vars=['年度', '繰出金合計_calc'], value_vars=pub_sub_cats, var_name='項目_raw', value_name='金額')
                    df_melt_pub['項目名'] = df_melt_pub['項目_raw'].str.replace('公営企業等に対する繰出金_うち', '').str.replace('会計', '')
                    df_melt_pub['割合(%)'] = (df_melt_pub['金額'] / df_melt_pub['繰出金合計_calc'] * 100).fillna(0).round(1)

                    fig_pub = px.bar(
                        df_melt_pub, x='年度', y='金額', color='項目名',
                        title="公営企業等繰出金内訳推移", barmode='stack',
                        custom_data=['項目名', '割合(%)']
                    )
                    fig_pub.update_layout(yaxis_tickformat=",", yaxis_title="金額（千円）")
                    fig_pub.update_traces(
                        hovertemplate="<b>項目名: %{customdata[0]}</b><br>金額: %{y:,.0f} 千円<br>構成比: %{customdata[1]}%<extra></extra>"
                    )
                    for i, row in df_plot_pub.iterrows():
                        if row['繰出金合計_calc'] > 0:
                            fig_pub.add_annotation(
                                x=row['年度'], y=row['繰出金合計_calc'],
                                text=f"{row['繰出金合計_calc']:,.0f}", showarrow=False, yshift=10, font=dict(size=10)
                            )
                    st.plotly_chart(fig_pub, use_container_width=True)
                else:
                    st.info("公営企業繰出金の内訳データが見つかりません。")

            st.markdown("---")
            st.subheader("2. 項目別 内訳分析")
            
            available_bonds_years = df_bonds_city['年度'].astype(str).unique()
            selected_year_bonds = st.selectbox("確認したい年度を選択", available_bonds_years, index=len(available_bonds_years)-1, key="bonds_year")
            
            bonds_cat_option = st.selectbox("深掘りするカテゴリーを選択", ["基金（積立金）内訳", "公営企業等繰出金内訳"], key="bonds_main_label")
            
            df_year_bonds = df_bonds_city[df_bonds_city['年度'].astype(str) == str(selected_year_bonds)]
            if not df_year_bonds.empty:
                row_data_b = df_year_bonds.iloc[0]
                target_sub_cols = fund_sub_cats if bonds_cat_option == "基金（積立金）内訳" else pub_sub_cats
                
                sub_bonds_data = []
                for sc in target_sub_cols:
                    val = pd.to_numeric(str(row_data_b[sc]).replace(',', '').replace('-', '0'), errors='coerce')
                    if not pd.isna(val) and val > 0:
                        clean_label = sc.replace('積立金現在高_', '').replace('公営企業等に対する繰出金_うち', '')
                        sub_bonds_data.append({'内訳': clean_label, '金額': val})
                
                sub_bonds_df = pd.DataFrame(sub_bonds_data)
                if not sub_bonds_df.empty:
                    fig_bar_bonds = px.bar(
                        sub_bonds_df.sort_values('金額', ascending=True), 
                        x='金額', y='内訳', orientation='h', 
                        title=f"{selected_year_bonds}年度 {bonds_cat_option} 内訳"
                    )
                    fig_bar_bonds.update_layout(xaxis_tickformat=",")
                    fig_bar_bonds.update_xaxes(title_text="金額（千円）")
                    st.plotly_chart(fig_bar_bonds, use_container_width=True)
                    st.dataframe(sub_bonds_df, use_container_width=True)
                else:
                    st.info("選択した年度の内訳金額がすべて0円です。")

        # --- Tab 2: 同一県内自治体比較（総額） ---
        with tab_bonds2:
            st.subheader(f"{selected_pref}内 自治体比較（総額）")
            df_pref_bonds = df_bonds[df_bonds['都道府県'] == selected_pref].copy()
            
            if not df_pref_bonds.empty:
                avail_years_bonds_pref = df_pref_bonds['年度'].astype(str).unique()
                comp_year_bonds = st.selectbox("比較する年度を選択", avail_years_bonds_pref, index=len(avail_years_bonds_pref)-1, key="comp_bonds_year")
                
                subtab2_bonds, subtab2_funds, subtab2_pub = st.tabs(["🏛️ 地方債・積立金比較", "💰 基金（積立金）構成比較", "🏥 公営企業繰出金比較"])
                
                df_comp_b = df_pref_bonds[df_pref_bonds['年度'].astype(str) == str(comp_year_bonds)].copy()
                
                with subtab2_bonds:
                    df_comp_b = df_comp_b.sort_values('地方債現在高_合計', ascending=False)
                    sorted_cities_b = df_comp_b['団体名'].tolist()
                    
                    df_melt_b = df_comp_b.melt(
                        id_vars=['団体名'], 
                        value_vars=['地方債現在高_合計', '積立金現在高_合計'], 
                        var_name='項目_raw', value_name='金額'
                    )
                    df_melt_b['項目名'] = df_melt_b['項目_raw'].str.replace('積立金現在高_合計', '積立金現在高（基金）')
                    
                    fig_comp_b = px.bar(
                        df_melt_b, x='団体名', y='金額', color='項目名',
                        title=f"{selected_pref}（{comp_year_bonds}年度）自治体別 地方債 vs 積立金比較（大きい順）",
                        barmode='group',
                        category_orders={'団体名': sorted_cities_b}
                    )
                    fig_comp_b.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
                    st.plotly_chart(fig_comp_b, use_container_width=True)
                    st.dataframe(df_comp_b[['団体名', '地方債現在高_合計', '積立金現在高_合計', '債務負担行為額(翌年度以降支出予定額)_合計']], use_container_width=True)

                with subtab2_funds:
                    if fund_sub_cats:
                        df_comp_b['基金合計_calc'] = df_comp_b[fund_sub_cats].sum(axis=1)
                        df_comp_b_fund = df_comp_b.sort_values('基金合計_calc', ascending=False)
                        sorted_cities_fund = df_comp_b_fund['団体名'].tolist()
                        
                        df_melt_fund_comp = df_comp_b_fund.melt(
                            id_vars=['団体名', '基金合計_calc'], value_vars=fund_sub_cats,
                            var_name='項目_raw', value_name='金額'
                        )
                        df_melt_fund_comp['項目名'] = df_melt_fund_comp['項目_raw'].str.replace('積立金現在高_', '')
                        df_melt_fund_comp['割合(%)'] = (df_melt_fund_comp['金額'] / df_melt_fund_comp['基金合計_calc'] * 100).fillna(0).round(1)

                        fig_comp_f = px.bar(
                            df_melt_fund_comp, x='団体名', y='金額', color='項目名',
                            title=f"{selected_pref}（{comp_year_bonds}年度）自治体別 基金構成比較（大きい順）",
                            barmode='stack',
                            category_orders={'団体名': sorted_cities_fund},
                            custom_data=['項目名', '割合(%)']
                        )
                        fig_comp_f.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
                        fig_comp_f.update_traces(
                            hovertemplate="<b>自治体: %{x}</b><br>項目名: %{customdata[0]}<br>金額: %{y:,.0f} 千円<br>構成比: %{customdata[1]}%<extra></extra>"
                        )
                        st.plotly_chart(fig_comp_f, use_container_width=True)
                        st.dataframe(df_comp_b_fund[['団体名', '基金合計_calc'] + fund_sub_cats], use_container_width=True)

                with subtab2_pub:
                    if pub_sub_cats:
                        df_comp_b['繰出金合計_calc'] = df_comp_b[pub_sub_cats].sum(axis=1)
                        df_comp_b_pub = df_comp_b.sort_values('繰出金合計_calc', ascending=False)
                        sorted_cities_pub = df_comp_b_pub['団体名'].tolist()
                        
                        df_melt_pub_comp = df_comp_b_pub.melt(
                            id_vars=['団体名', '繰出金合計_calc'], value_vars=pub_sub_cats,
                            var_name='項目_raw', value_name='金額'
                        )
                        df_melt_pub_comp['項目名'] = df_melt_pub_comp['項目_raw'].str.replace('公営企業等に対する繰出金_うち', '').str.replace('会計', '')
                        df_melt_pub_comp['割合(%)'] = (df_melt_pub_comp['金額'] / df_melt_pub_comp['繰出金合計_calc'] * 100).fillna(0).round(1)

                        fig_comp_p = px.bar(
                            df_melt_pub_comp, x='団体名', y='金額', color='項目名',
                            title=f"{selected_pref}（{comp_year_bonds}年度）自治体別 公営企業繰出金比較（大きい順）",
                            barmode='stack',
                            category_orders={'団体名': sorted_cities_pub},
                            custom_data=['項目名', '割合(%)']
                        )
                        fig_comp_p.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
                        fig_comp_p.update_traces(
                            hovertemplate="<b>自治体: %{x}</b><br>項目名: %{customdata[0]}<br>金額: %{y:,.0f} 千円<br>構成比: %{customdata[1]}%<extra></extra>"
                        )
                        st.plotly_chart(fig_comp_p, use_container_width=True)
                        st.dataframe(df_comp_b_pub[['団体名', '繰出金合計_calc'] + pub_sub_cats], use_container_width=True)
            else:
                st.info("該当する県内データが見つかりません。")

        # --- Tab 3: 同一県内自治体比較（1人当たり） ---
        with tab_bonds3:
            st.subheader(f"{selected_pref}内 自治体比較（人口1人当たり）")
            df_pref_bonds = df_bonds[df_bonds['都道府県'] == selected_pref].copy()
            df_pref_ov = df_overview[df_overview['都道府県'] == selected_pref].copy()
            pop_col = get_population_col(df_overview)
            
            if not df_pref_bonds.empty and pop_col:
                avail_years_bonds_pref = df_pref_bonds['年度'].astype(str).unique()
                comp_year_bonds_pop = st.selectbox("比較する年度を選択", avail_years_bonds_pref, index=len(avail_years_bonds_pref)-1, key="comp_bonds_pop_year")
                
                df_comp_b = df_pref_bonds[df_pref_bonds['年度'].astype(str) == str(comp_year_bonds_pop)].copy()
                df_ov_year = df_pref_ov[df_pref_ov['年度'].astype(str) == str(comp_year_bonds_pop)].copy()
                df_ov_year['人口_num'] = pd.to_numeric(df_ov_year[pop_col].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce').fillna(0)
                
                df_comp_b_pop = df_comp_b.merge(df_ov_year[['団体名', '人口_num']], on='団体名', how='left')
                df_comp_b_pop['人口_num'] = df_comp_b_pop['人口_num'].fillna(0)
                df_comp_b_pop = df_comp_b_pop[df_comp_b_pop['人口_num'] > 0].copy()
                
                if not df_comp_b_pop.empty:
                    subtab3_bonds, subtab3_funds, subtab3_pub = st.tabs(["🏛️ 1人当たり地方債・積立金", "💰 1人当たり基金（積立金）構成", "🏥 1人当たり公営企業繰出金"])
                    
                    df_comp_b_pop['1人当たり地方債現在高'] = (df_comp_b_pop['地方債現在高_合計'] / df_comp_b_pop['人口_num']).round(2)
                    df_comp_b_pop['1人当たり積立金現在高'] = (df_comp_b_pop['積立金現在高_合計'] / df_comp_b_pop['人口_num']).round(2)
                    
                    for sc in fund_sub_cats:
                        df_comp_b_pop[sc + '_1人当たり'] = (df_comp_b_pop[sc] / df_comp_b_pop['人口_num']).round(2)
                    for sc in pub_sub_cats:
                        df_comp_b_pop[sc + '_1人当たり'] = (df_comp_b_pop[sc] / df_comp_b_pop['人口_num']).round(2)

                    with subtab3_bonds:
                        df_comp_b_pop = df_comp_b_pop.sort_values('1人当たり地方債現在高', ascending=False)
                        sorted_cities_pop_b = df_comp_b_pop['団体名'].tolist()
                        
                        df_melt_b_pop = df_comp_b_pop.melt(
                            id_vars=['団体名', '人口_num'],
                            value_vars=['1人当たり地方債現在高', '1人当たり積立金現在高'],
                            var_name='項目_raw', value_name='1人当たり金額'
                        )
                        
                        fig_pop_b = px.bar(
                            df_melt_b_pop, x='団体名', y='1人当たり金額', color='項目_raw',
                            title=f"{selected_pref}（{comp_year_bonds_pop}年度）自治体別 1人当たり地方債 vs 積立金比較（大きい順 / 人口参照: {pop_col}）",
                            barmode='group',
                            category_orders={'団体名': sorted_cities_pop_b}
                        )
                        fig_pop_b.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
                        st.plotly_chart(fig_pop_b, use_container_width=True)
                        st.dataframe(df_comp_b_pop[['団体名', '人口_num', '1人当たり地方債現在高', '1人当たり積立金現在高']], use_container_width=True)

                    with subtab3_funds:
                        if fund_sub_cats:
                            fund_per_capita_cols = [sc + '_1人当たり' for sc in fund_sub_cats]
                            df_comp_b_pop['1人当たり基金合計'] = df_comp_b_pop[fund_per_capita_cols].sum(axis=1)
                            df_comp_b_pop_f = df_comp_b_pop.sort_values('1人当たり基金合計', ascending=False)
                            sorted_cities_pop_f = df_comp_b_pop_f['団体名'].tolist()
                            
                            df_melt_f_pop = df_comp_b_pop_f.melt(
                                id_vars=['団体名', '1人当たり基金合計'],
                                value_vars=fund_per_capita_cols,
                                var_name='項目_raw', value_name='1人当たり金額'
                            )
                            df_melt_f_pop['項目名'] = df_melt_f_pop['項目_raw'].str.replace('積立金現在高_', '').str.replace('_1人当たり', '')
                            df_melt_f_pop['割合(%)'] = (df_melt_f_pop['1人当たり金額'] / df_melt_f_pop['1人当たり基金合計'] * 100).fillna(0).round(1)

                            fig_pop_f = px.bar(
                                df_melt_f_pop, x='団体名', y='1人当たり金額', color='項目名',
                                title=f"{selected_pref}（{comp_year_bonds_pop}年度）自治体別 1人当たり基金構成比較（大きい順）",
                                barmode='stack',
                                category_orders={'団体名': sorted_cities_pop_f},
                                custom_data=['項目名', '割合(%)']
                            )
                            fig_pop_f.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
                            fig_pop_f.update_traces(
                                hovertemplate="<b>自治体: %{x}</b><br>項目名: %{customdata[0]}<br>1人当たり金額: %{y:,.2f} 千円/人<br>構成比: %{customdata[1]}%<extra></extra>"
                            )
                            st.plotly_chart(fig_pop_f, use_container_width=True)
                            st.dataframe(df_comp_b_pop_f[['団体名', '1人当たり基金合計'] + fund_per_capita_cols], use_container_width=True)

                    with subtab3_pub:
                        if pub_sub_cats:
                            pub_per_capita_cols = [sc + '_1人当たり' for sc in pub_sub_cats]
                            df_comp_b_pop['1人当たり繰出金合計'] = df_comp_b_pop[pub_per_capita_cols].sum(axis=1)
                            df_comp_b_pop_p = df_comp_b_pop.sort_values('1人当たり繰出金合計', ascending=False)
                            sorted_cities_pop_p = df_comp_b_pop_p['団体名'].tolist()
                            
                            df_melt_p_pop = df_comp_b_pop_p.melt(
                                id_vars=['団体名', '1人当たり繰出金合計'],
                                value_vars=pub_per_capita_cols,
                                var_name='項目_raw', value_name='1人当たり金額'
                            )
                            df_melt_p_pop['項目名'] = df_melt_p_pop['項目_raw'].str.replace('公営企業等に対する繰出金_うち', '').str.replace('会計_1人当たり', '')
                            df_melt_p_pop['割合(%)'] = (df_melt_p_pop['1人当たり金額'] / df_melt_p_pop['1人当たり繰出金合計'] * 100).fillna(0).round(1)

                            fig_pop_p = px.bar(
                                df_melt_p_pop, x='団体名', y='1人当たり金額', color='項目名',
                                title=f"{selected_pref}（{comp_year_bonds_pop}年度）自治体別 1人当たり公営企業繰出金比較（大きい順）",
                                barmode='stack',
                                category_orders={'団体名': sorted_cities_pop_p},
                                custom_data=['項目名', '割合(%)']
                            )
                            fig_pop_p.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
                            fig_pop_p.update_traces(
                                hovertemplate="<b>自治体: %{x}</b><br>項目名: %{customdata[0]}<br>1人当たり金額: %{y:,.2f} 千円/人<br>構成比: %{customdata[1]}%<extra></extra>"
                            )
                            st.plotly_chart(fig_pop_p, use_container_width=True)
                            st.dataframe(df_comp_b_pop_p[['団体名', '1人当たり繰出金合計'] + pub_per_capita_cols], use_container_width=True)
                else:
                    st.warning("該当年度の人口データが見つからないか、全自治体の人口が0です。")
            else:
                st.info("人口データまたは県内地方債データが見つかりません。")

        # --- Tab 4: 地方債・基金分析（全期間変化率ランキング） ---
        with tab_bonds4:
            st.subheader(f"{selected_pref}内 自治体地方債・基金分析（全期間変化率ランキング）")
            df_pref_bonds = df_bonds[df_bonds['都道府県'] == selected_pref].copy()
            
            if not df_pref_bonds.empty:
                all_bonds_years = sorted([str(y) for y in df_pref_bonds['年度'].unique()])
                min_bonds_year, max_bonds_year = all_bonds_years[0], all_bonds_years[-1]
                
                st.caption(f"分析期間: **{min_bonds_year}年度** ➔ **{max_bonds_year}年度**（データ内全期間）")
                
                bonds_analysis_options = {
                    '地方債現在高_合計': '地方債現在高_合計',
                    '積立金現在高_合計': '積立金現在高_合計（基金）',
                    '積立金現在高_財政調整基金': '積立金現在高_財政調整基金',
                    '積立金現在高_減債基金': '積立金現在高_減債基金',
                    '積立金現在高_その他特定目的基金': '積立金現在高_その他特定目的基金',
                    '債務負担行為額(翌年度以降支出予定額)_合計': '債務負担行為額_合計',
                    '公営企業等に対する繰出金_合計': '公営企業等に対する繰出金_合計'
                }
                bonds_analysis_options = {k: v for k, v in bonds_analysis_options.items() if k in df_pref_bonds.columns}
                
                selected_bonds_target = st.selectbox("分析対象の項目を選択", list(bonds_analysis_options.keys()), format_func=lambda x: bonds_analysis_options[x], key="bonds_analysis_target")
                
                df_pref_bonds[selected_bonds_target] = pd.to_numeric(
                    df_pref_bonds[selected_bonds_target].astype(str).str.replace(',', '').str.replace('-', '0'), 
                    errors='coerce'
                ).fillna(0)
                
                df_bonds_min = df_pref_bonds[df_pref_bonds['年度'].astype(str) == min_bonds_year][['団体名', selected_bonds_target]].rename(columns={selected_bonds_target: '初期金額'})
                df_bonds_max = df_pref_bonds[df_pref_bonds['年度'].astype(str) == max_bonds_year][['団体名', selected_bonds_target]].rename(columns={selected_bonds_target: '最新金額'})
                
                df_bonds_growth = df_bonds_min.merge(df_bonds_max, on='団体名', how='inner')
                df_bonds_growth = df_bonds_growth[df_bonds_growth['初期金額'] > 0].copy()
                
                df_bonds_growth['増加額'] = df_bonds_growth['最新金額'] - df_bonds_growth['初期金額']
                df_bonds_growth['増加率(%)'] = ((df_bonds_growth['増加額'] / df_bonds_growth['初期金額']) * 100).round(1)
                df_bonds_growth = df_bonds_growth.sort_values('増加率(%)', ascending=False)
                
                bonds_target_name = bonds_analysis_options[selected_bonds_target]
                
                fig_bonds_growth = px.bar(
                    df_bonds_growth, x='団体名', y='増加率(%)', text='増加率(%)',
                    title=f"{selected_pref}内自治体 {bonds_target_name} 増加率ランキング（{min_bonds_year}➔{max_bonds_year}年度）",
                    color='増加率(%)', color_continuous_scale='RdBu_r'
                )
                fig_bonds_growth.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_bonds_growth.update_layout(xaxis_title="自治体名", yaxis_title="増加率（%）")
                st.plotly_chart(fig_bonds_growth, use_container_width=True)
                
                st.markdown(f"#### {bonds_target_name} 全期間変化率データテーブル")
                st.dataframe(
                    df_bonds_growth.rename(columns={
                        '初期金額': f'{min_bonds_year}年度金額(千円)',
                        '最新金額': f'{max_bonds_year}年度金額(千円)',
                        '増加額': '増加額(千円)'
                    }),
                    use_container_width=True
                )
            else:
                st.info("該当する県内データが見つかりません。")
    else:
        st.warning("対象自治体の地方債データが存在しません。")