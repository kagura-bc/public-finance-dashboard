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

# 1. 都市区分の選択（全国データから抽出）
all_type_list = list(df_overview['都市区分'].dropna().unique()) if not df_overview.empty and '都市区分' in df_overview.columns else []
type_options = ["すべて"] + all_type_list
selected_type = st.sidebar.selectbox("都市区分を選択", type_options)

# 都市区分による一次フィルタリング
df_type_filtered = df_overview.copy() if not df_overview.empty else pd.DataFrame()
if selected_type != "すべて" and not df_type_filtered.empty:
    df_type_filtered = df_type_filtered[df_type_filtered['都市区分'] == selected_type]

# 2. 都道府県の選択（「全国」＋選択した都市区分が存在する都道府県のみ）
pref_list = list(df_type_filtered['都道府県'].dropna().unique()) if not df_type_filtered.empty else []
pref_options = ["全国"] + pref_list
pref_default_idx = pref_options.index('山梨県') if '山梨県' in pref_options else 0
selected_pref = st.sidebar.selectbox("都道府県を選択", pref_options, index=pref_default_idx)

# 都道府県による二次フィルタリング & 比較表示用ラベルの設定
if selected_pref == "全国":
    df_pref_filtered = df_type_filtered.copy()
    scope_label = f"全国（{selected_type}）" if selected_type != "すべて" else "全国"
else:
    df_pref_filtered = df_type_filtered[df_type_filtered['都道府県'] == selected_pref] if not df_type_filtered.empty and isinstance(selected_pref, str) else pd.DataFrame()
    scope_label = f"{selected_pref}（{selected_type}）" if selected_type != "すべて" else selected_pref

# 3. 市町村の選択（都市区分・都道府県の両方で絞り込まれたリストを表示）
city_list = list(df_pref_filtered['団体名'].dropna().unique()) if not df_pref_filtered.empty else []
city_default_idx = city_list.index('甲府市') if '甲府市' in city_list else 0
selected_city = st.sidebar.selectbox("市町村を選択", city_list, index=city_default_idx) if len(city_list) > 0 else st.sidebar.text("市町村データなし")

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
    """選択された都市区分および都道府県の設定に応じた比較対象データフレームを取得"""
    if df.empty:
        return df
    res = df.copy()
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
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "🏆 総合評価・ランキング",
            "⚖️ 財政規模・収支",
            "🚨 財政健全化指標",
            "👥 人口・産業",
            "📋 データ一覧"
        ])
        
        num_cols = df_ov_city.select_dtypes(include=['number']).columns.tolist()
        
        def get_cols_by_keywords(keywords):
            return [col for col in num_cols if any(kw in col for kw in keywords)]

        # --- Tab 1: 総合ポイントランキング & 各スコア比較 ---
        with tab1:
            st.markdown(f"#### 🏆 {scope_label} 財政健全化総合ポイントランキング & 比較分析")
            
            available_ov_years = sorted(df_overview['年度'].astype(str).unique()) if not df_overview.empty else []
            if available_ov_years:
                selected_rank_year = st.selectbox("分析対象年度を選択", available_ov_years, index=len(available_ov_years)-1, key="rank_year_select")
                
                df_ov_comp = get_comparison_df(df_overview)
                df_bonds_comp = get_comparison_df(df_bonds)
                
                df_ov_pref_y = df_ov_comp[df_ov_comp['年度'].astype(str) == str(selected_rank_year)].copy()
                df_bonds_pref_y = df_bonds_comp[df_bonds_comp['年度'].astype(str) == str(selected_rank_year)].copy() if not df_bonds_comp.empty else pd.DataFrame()
                
                if not df_ov_pref_y.empty:
                    if not df_bonds_pref_y.empty:
                        b_cols = ['団体名', '地方債現在高_合計', '積立金現在高_合計', '債務負担行為額(翌年度以降支出予定額)_合計']
                        b_cols_exist = [c for c in b_cols if c in df_bonds_pref_y.columns]
                        df_rank = pd.merge(df_ov_pref_y, df_bonds_pref_y[b_cols_exist], on='団体名', how='left')
                    else:
                        df_rank = df_ov_pref_y.copy()
                    
                    pop_col = get_population_col(df_rank)
                    if pop_col:
                        df_rank['人口_num'] = pd.to_numeric(df_rank[pop_col].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce').fillna(0)
                    else:
                        df_rank['人口_num'] = 0
                    
                    for target_c in ['地方債現在高_合計', '積立金現在高_合計', '債務負担行為額(翌年度以降支出予定額)_合計', '財政力指数', '経常収支比率', '実質公債費比率', '将来負担比率']:
                        if target_c in df_rank.columns:
                            df_rank[target_c] = pd.to_numeric(df_rank[target_c].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce')
                    
                    if '地方債現在高_合計' in df_rank.columns and '積立金現在高_合計' in df_rank.columns:
                        debt_val = df_rank['地方債現在高_合計'].fillna(0)
                        fund_val = df_rank['積立金現在高_合計'].fillna(0)
                        commit_val = df_rank['債務負担行為額(翌年度以降支出予定額)_合計'].fillna(0) if '債務負担行為額(翌年度以降支出予定額)_合計' in df_rank.columns else 0
                        df_rank['実質将来負担残高_推計'] = debt_val + commit_val - fund_val
                    
                    if '人口_num' in df_rank.columns and (df_rank['人口_num'] > 0).any():
                        valid_pop = df_rank['人口_num'].replace(0, pd.NA)
                        if '地方債現在高_合計' in df_rank.columns:
                            df_rank['1人当たり地方債(千円)'] = (df_rank['地方債現在高_合計'] / valid_pop).round(1)
                        if '積立金現在高_合計' in df_rank.columns:
                            df_rank['1人当たり基金(千円)'] = (df_rank['積立金現在高_合計'] / valid_pop).round(1)
                        if '実質将来負担残高_推計' in df_rank.columns:
                            df_rank['1人当たり実質将来負担(千円)'] = (df_rank['実質将来負担残高_推計'] / valid_pop).round(1)

                    def calc_score(series, is_higher_better=True):
                        s = pd.to_numeric(series, errors='coerce')
                        min_v, max_v = s.min(), s.max()
                        if pd.isna(min_v) or pd.isna(max_v) or max_v == min_v:
                            return pd.Series(50.0, index=s.index)
                        if is_higher_better:
                            return ((s - min_v) / (max_v - min_v) * 100).round(1)
                        else:
                            return ((max_v - s) / (max_v - min_v) * 100).round(1)

                    score_item_map = {}
                    if '財政力指数' in df_rank.columns:
                        df_rank['財政力スコア'] = calc_score(df_rank['財政力指数'], is_higher_better=True)
                        score_item_map['財政力スコア'] = ('財政力', '財政力指数')
                    if '経常収支比率' in df_rank.columns:
                        df_rank['経常収支スコア'] = calc_score(df_rank['経常収支比率'], is_higher_better=False)
                        score_item_map['経常収支スコア'] = ('経常収支(弾力性)', '経常収支比率')
                    if '1人当たり基金(千円)' in df_rank.columns:
                        df_rank['基金スコア'] = calc_score(df_rank['1人当たり基金(千円)'], is_higher_better=True)
                        score_item_map['基金スコア'] = ('貯蓄力', '1人当たり基金(千円)')
                    if '1人当たり実質将来負担(千円)' in df_rank.columns:
                        df_rank['将来負担スコア'] = calc_score(df_rank['1人当たり実質将来負担(千円)'], is_higher_better=False)
                        score_item_map['将来負担スコア'] = ('健全性(将来負担)', '1人当たり実質将来負担(千円)')

                    score_cols = list(score_item_map.keys())
                    if score_cols:
                        df_rank['総合ポイント'] = df_rank[score_cols].mean(axis=1).round(1)
                        df_rank['総合順位'] = df_rank['総合ポイント'].rank(ascending=False, method='min').astype(int)

                    total_cities_count = len(df_rank)
                    city_rank_row = df_rank[df_rank['団体名'] == selected_city]
                    
                    if not city_rank_row.empty:
                        c_data = city_rank_row.iloc[0]
                        st.markdown(f"##### 📍 {scope_label}における **{selected_city}** の総合評価・スコア要約（{selected_rank_year}年度 / 全{total_cities_count}自治体）")
                        
                        m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
                        with m_col1:
                            if '総合ポイント' in c_data and not pd.isna(c_data['総合ポイント']):
                                st.metric(label="総合ポイント", value=f"{c_data['総合ポイント']:.1f} pt", delta=f"{scope_label} {int(c_data['総合順位'])}位 / {total_cities_count}", delta_color="normal")
                        with m_col2:
                            if '財政力スコア' in c_data and not pd.isna(c_data['財政力スコア']):
                                st.metric(label="財政力スコア", value=f"{c_data['財政力スコア']:.1f} pt", delta=f"{c_data['財政力指数']:.2f}" if '財政力指数' in c_data else None)
                        with m_col3:
                            if '経常収支スコア' in c_data and not pd.isna(c_data['経常収支スコア']):
                                st.metric(label="経常収支スコア", value=f"{c_data['経常収支スコア']:.1f} pt", delta=f"{c_data['経常収支比率']:.1f}%" if '経常収支比率' in c_data else None)
                        with m_col4:
                            if '基金スコア' in c_data and not pd.isna(c_data['基金スコア']):
                                st.metric(label="貯蓄力スコア", value=f"{c_data['基金スコア']:.1f} pt", delta=f"{c_data['1人当たり基金(千円)']:,.1f}千円" if '1人当たり基金(千円)' in c_data else None)
                        with m_col5:
                            if '将来負担スコア' in c_data and not pd.isna(c_data['将来負担スコア']):
                                st.metric(label="将来負担スコア", value=f"{c_data['将来負担スコア']:.1f} pt", delta=f"{c_data['1人当たり実質将来負担(千円)']:,.1f}千円" if '1人当たり実質将来負担(千円)' in c_data else None)

                        st.markdown("---")

                        subtab_rank1, subtab_rank2 = st.tabs(["🌐 総合ランキング & レーダー", "👥 1人当たり原数値比較"])

                        with subtab_rank1:
                            col_chart_left, col_chart_right = st.columns([3, 2])
                            with col_chart_left:
                                st.markdown(f"##### 📊 {scope_label} 総合ポイントランキング（100pt満点換算）")
                                df_rank_sorted = df_rank.dropna(subset=['総合ポイント']).sort_values('総合ポイント', ascending=True).copy()
                                df_rank_sorted['表示色'] = df_rank_sorted['団体名'].apply(lambda x: '選択中の自治体' if x == selected_city else 'その他自治体')
                                fig_rank = px.bar(
                                    df_rank_sorted, x='総合ポイント', y='団体名', orientation='h', color='表示色', text='総合ポイント',
                                    title=f"{scope_label}（{selected_rank_year}年度）財政健全化 総合ポイントランキング",
                                    color_discrete_map={'選択中の自治体': '#FF4B4B', 'その他自治体': '#1F77B4'},
                                    custom_data=['都道府県']
                                )
                                fig_rank.update_traces(
                                    texttemplate='%{text:.1f} pt', textposition='outside',
                                    hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{y}</b><br>総合ポイント: %{x:.1f} pt<extra></extra>"
                                )
                                fig_rank.update_layout(xaxis_title="総合ポイント (pt)", yaxis_title="自治体名", showlegend=True, height=max(400, len(df_rank_sorted)*25))
                                st.plotly_chart(fig_rank, use_container_width=True)
                            
                            with col_chart_right:
                                st.markdown(f"##### 🕸️ {selected_city} 財政バランス（スコアレーダー）")
                                radar_labels = [score_item_map[sc][0] for sc in score_cols]
                                radar_vals = [c_data[sc] for sc in score_cols]
                                if radar_vals:
                                    fig_radar = go.Figure()
                                    fig_radar.add_trace(go.Scatterpolar(r=radar_vals + [radar_vals[0]], theta=radar_labels + [radar_labels[0]], fill='toself', name=selected_city, line_color='#FF4B4B'))
                                    fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), showlegend=False, title=f"{selected_city} 各分野スコアバランス")
                                    st.plotly_chart(fig_radar, use_container_width=True)

                            st.markdown(f"##### 📋 {scope_label} 財政健全化ポイント＆主要指標比較テーブル")
                            disp_cols = ['総合順位', '都道府県', '団体名', '総合ポイント', '財政力指数', '経常収支比率', '1人当たり基金(千円)', '1人当たり実質将来負担(千円)']
                            disp_cols = [c for c in disp_cols if c in df_rank.columns]
                            st.dataframe(df_rank.sort_values('総合順位')[disp_cols], use_container_width=True)

                            # 下部に特定スコア項目の詳細ランキング比較を配置
                            st.markdown("---")
                            st.markdown("##### 🔍 特定スコア項目の詳細ランキング比較")
                            selected_score_col = st.selectbox("比較したいスコア項目を選択", score_cols, format_func=lambda x: f"{score_item_map[x][0]}スコア（参照元: {score_item_map[x][1]}）", key="single_score_select")
                            df_score_single = df_rank.dropna(subset=[selected_score_col]).sort_values(selected_score_col, ascending=False).copy()
                            df_score_single['表示色'] = df_score_single['団体名'].apply(lambda x: '選択中の自治体' if x == selected_city else 'その他自治体')
                            score_label_name = score_item_map[selected_score_col][0]
                            fig_single_score = px.bar(
                                df_score_single, x='団体名', y=selected_score_col, color='表示色', text=selected_score_col,
                                title=f"{scope_label}（{selected_rank_year}年度）{score_label_name}スコア ランキング",
                                color_discrete_map={'選択中の自治体': '#FF4B4B', 'その他自治体': '#1F77B4'},
                                custom_data=['都道府県']
                            )
                            fig_single_score.update_traces(
                                texttemplate='%{text:.1f} pt', textposition='outside',
                                hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>スコア: %{y:.1f} pt<extra></extra>"
                            )
                            fig_single_score.update_layout(xaxis_title="自治体名", yaxis_title="スコア (pt)", yaxis_range=[0, 110])
                            st.plotly_chart(fig_single_score, use_container_width=True)

                        with subtab_rank2:
                            st.markdown(f"##### 👥 {scope_label} 全自治体 人口1人当たり指標 原数値比較（実数値）")
                            per_capita_options = {
                                '1人当たり基金(千円)': '1人当たり基金残高（貯金額 / 千円）',
                                '1人当たり実質将来負担(千円)': '1人当たり実質将来負担残高（債務推計 / 千円）',
                                '1人当たり地方債(千円)': '1人当たり地方債残高（借金 / 千円）'
                            }
                            per_capita_options = {k: v for k, v in per_capita_options.items() if k in df_rank.columns}
                            if per_capita_options:
                                selected_pc_col = st.selectbox("比較したい1人当たり指標を選択", list(per_capita_options.keys()), format_func=lambda x: per_capita_options[x], key="pc_col_select")
                                df_pc_sorted = df_rank.dropna(subset=[selected_pc_col]).sort_values(selected_pc_col, ascending=False).copy()
                                df_pc_sorted['表示色'] = df_pc_sorted['団体名'].apply(lambda x: '選択中の自治体' if x == selected_city else 'その他自治体')
                                fig_pc = px.bar(
                                    df_pc_sorted, x='団体名', y=selected_pc_col, color='表示色', text=selected_pc_col,
                                    title=f"{scope_label}（{selected_rank_year}年度）{per_capita_options[selected_pc_col]} 比較",
                                    color_discrete_map={'選択中の自治体': '#FF4B4B', 'その他自治体': '#1F77B4'},
                                    custom_data=['都道府県']
                                )
                                fig_pc.update_traces(
                                    texttemplate='%{text:,.1f} 千円', textposition='outside',
                                    hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>金額: %{y:,.1f} 千円/人<extra></extra>"
                                )
                                fig_pc.update_layout(xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
                                st.plotly_chart(fig_pc, use_container_width=True)
                                st.markdown("##### 📋 人口1人当たり原数値 データテーブル")
                                pc_disp_cols = ['総合順位', '都道府県', '団体名', '人口_num'] + list(per_capita_options.keys())
                                pc_disp_cols = [c for c in pc_disp_cols if c in df_rank.columns]
                                st.dataframe(df_rank.sort_values('総合順位')[pc_disp_cols], use_container_width=True)

        # --- Tab 2: 財政規模・収支 ---
        with tab2:
            subtab_scale1, subtab_scale2, subtab_scale3 = st.tabs([
                "⚖️ 基準財政・財政力・標準規模", 
                "💰 財政規模・収支バランス", 
                "📊 経常収支比率"
            ])
            
            with subtab_scale1:
                st.markdown("#### 標準財政規模・基準財政需要額・収入額および財政力指数の推移")
                cols_dem_inc = get_cols_by_keywords(['基準財政需要額', '基準財政収入額', '標準財政規模'])
                cols_pow = get_cols_by_keywords(['財政力指数'])
                if cols_dem_inc or cols_pow:
                    fig_d = make_subplots(specs=[[{"secondary_y": True}]])
                    for col in cols_dem_inc:
                        fig_d.add_trace(go.Scatter(x=df_ov_city['年度'], y=df_ov_city[col], mode='lines+markers', name=col), secondary_y=False)
                    for col in cols_pow:
                        fig_d.add_trace(go.Scatter(x=df_ov_city['年度'], y=df_ov_city[col], mode='lines+markers', name=col, line=dict(dash='dash', color='orange')), secondary_y=True)
                    
                    # 財政力指数 1.0 に破線（基準線）を追加
                    fig_d.add_hline(
                        y=1.0, line_dash="dash", line_color="red", secondary_y=True,
                        annotation_text="自立判定ライン (1.0)", annotation_position="bottom right"
                    )

                    fig_d.update_layout(title="標準財政規模・需要額・収入額 vs 財政力指数", xaxis_title="年度", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                    fig_d.update_yaxes(title_text="金額（千円）", secondary_y=False, tickformat=",")
                    fig_d.update_yaxes(title_text="財政力指数", secondary_y=True, tickformat=".2f")
                    st.plotly_chart(fig_d, use_container_width=True)

                    with st.expander("📖 財政規模・交付税関連指標のガイド（解説）", expanded=True):
                        st.markdown("""
                        ##### 📌 各指標の概要
                        * **標準財政規模**
                          自治体が1年間で自由に使える**「標準的なお金（一般財源）の総額」**。地方税（100%分）＋普通交付税＋地方特例交付金などで構成されます。
                        * **基準財政需要額**
                          普通交付税の算定上、自治体が標準的な行政サービスを行うために**「必要と算定された経費」**。
                        * **基準財政収入額**
                          普通交付税の算定上、自治体に入る**「標準的な見込み税収」**。減税・増税の意欲阻害を防ぐため、実際の税収の**75%分**のみを計上します。
                        * **財政力指数**
                          $\text{基準財政収入額} \div \text{基準財政需要額}$ の3か年平均。**1.0を超えると自主財源で需要を賄える財政力があり、普通交付税が交付されない「不交付団体」**となります。

                        ---
                        ##### 💡 「標準財政規模」と「基準財政収入額」の違い
                        | 比較項目 | 基準財政収入額 | 標準財政規模 |
                        | :--- | :--- | :--- |
                        | **役割** | **地方交付税額の計算用**（需要額との差額を算出） | **年間で自由に使える総額**（財政指標の分母） |
                        | **税収のカウント** | 見込み税収の**75%**のみ | 税収**100%** ＋ 普通交付税 ＋ 交付金等 |
                        | **規模感** | 小さい（標準財政規模の一部） | 大きい（実際の財政スケール全体） |
                        """)
                else:
                    st.info("該当するデータが見つかりません。")

            with subtab_scale2:
                st.markdown("#### 財政バランス（収支関連）の推移")
                cols_scale = get_cols_by_keywords(['実質収支', '単年度収支', '実質単年度収支']) or num_cols[:3]
                fig1 = px.line(df_ov_city, x='年度', y=cols_scale, markers=True, title="収支関連指標の推移")
                
                # 収支均衡ライン (0千円) に破線（基準線）を追加
                fig1.add_hline(
                    y=0, line_dash="dash", line_color="gray",
                    annotation_text="収支均衡ライン (0千円)", annotation_position="bottom right"
                )

                fig1.update_layout(yaxis_tickformat=",", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                fig1.update_yaxes(title_text="金額（千円）")
                st.plotly_chart(fig1, use_container_width=True)

                with st.expander("📖 収支関連指標（黒字・赤字指標）のガイド（解説）", expanded=True):
                    st.markdown("""
                    ##### 📌 3つの「収支」の違いと見方
                    * **実質収支（累積の純収支）**
                      歳入総額から歳出総額を差し引いた額（形式収支）から、翌年度へ繰り越すべき財源（事故繰越し等）を控除した純収支。
                      > **見方**：基本として**0以上（黒字）**を維持することが健全性の条件です。
                    * **単年度収支（その年の単体損益）**
                      当該年度単体での実質収支の変動分（*当年度実質収支 － 前年度実質収支*）。
                      > **見方**：その1年間だけで黒字を生み出したか（**0以上**）、赤字だったかを示します。
                    * **実質単年度収支（真の稼ぎ力）**
                      単年度収支に「積立金（貯金）」や「繰上償還（借金前倒し返済）」を加え、「基金取り崩し」を引いた指標。
                      > **見方**：一時的な貯金の取り崩し等を除いた、自治体の**「構造的な稼ぎ力」**を表します。
                    """)

            # 経常収支比率を Tab 2 に配置
            with subtab_scale3:
                st.markdown("#### 経常収支比率の推移（財政構造の弾力性）")
                cols_keijo = get_cols_by_keywords(['経常収支比率'])
                if cols_keijo:
                    fig_k = px.line(df_ov_city, x='年度', y=cols_keijo, markers=True, title="経常収支比率の推移")
                    fig_k.add_hline(y=80.0, line_dash="dash", line_color="green", annotation_text="適正水準目安 (80%)", annotation_position="bottom right")
                    fig_k.add_hline(y=90.0, line_dash="dash", line_color="red", annotation_text="硬直化警戒水準 (90%)", annotation_position="top right")
                    fig_k.update_layout(yaxis_tickformat=".1f", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                    fig_k.update_yaxes(title_text="比率（%）")
                    st.plotly_chart(fig_k, use_container_width=True)
                    st.caption("※経常収支比率が高くなるほど人件費や扶助費などの義務的経費に財源が奪われ、新たな政策課題への対応能力（財政の弾力性）が低下していることを意味します。")
                else:
                    st.info("経常収支比率のデータが見つかりません。")

        # --- Tab 3: 財政健全化指標 ---
        with tab3:
            st.markdown("### 🚨 地方財政健全化法に基づく健全化判断比率")
            
            cols_kenzen = get_cols_by_keywords(['実質赤字比率', '連結実質赤字比率', '実質公債費比率', '将来負担比率'])
            if cols_kenzen:
                cols_small = [c for c in cols_kenzen if '将来負担比率' not in c]
                cols_large = [c for c in cols_kenzen if '将来負担比率' in c]
                col_left, col_right = st.columns(2)
                
                with col_left:
                    if cols_small:
                        df_s_plot = df_ov_city[['年度'] + cols_small].copy()
                        rename_dict_s = {c: c.replace('健全化判断比率_', '').replace('_パーセント', '').replace('_割合', '') for c in cols_small}
                        df_s_plot = df_s_plot.rename(columns=rename_dict_s)
                        clean_cols_s = list(rename_dict_s.values())

                        for c in clean_cols_s:
                            df_s_plot[c] = pd.to_numeric(df_s_plot[c].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce')

                        fig_s = px.line(df_s_plot, x='年度', y=clean_cols_s, markers=True, title="実質赤字・連結赤字・実質公債費比率")
                        fig_s.add_hline(y=10.0, line_dash="dash", line_color="green", annotation_text="健全水準目安 (10%)", annotation_position="bottom right")
                        fig_s.add_hline(y=18.0, line_dash="dash", line_color="orange", annotation_text="許可制移行・起債制限 (18%)", annotation_position="top right")
                        fig_s.add_hline(y=25.0, line_dash="dash", line_color="red", annotation_text="早期健全化基準 (25%)", annotation_position="top left")
                        fig_s.add_hline(y=35.0, line_dash="dash", line_color="darkred", annotation_text="財政再生基準 (35%)", annotation_position="top left")
                        
                        fig_s.update_layout(
                            yaxis_tickformat=".1f",
                            legend_title_text="",
                            legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5),
                            margin=dict(t=50, b=80)
                        )
                        fig_s.update_yaxes(title_text="比率（%）")
                        st.plotly_chart(fig_s, use_container_width=True)

                with col_right:
                    if cols_large:
                        df_l_plot = df_ov_city[['年度'] + cols_large].copy()
                        rename_dict_l = {c: c.replace('健全化判断比率_', '').replace('_パーセント', '').replace('_割合', '') for c in cols_large}
                        df_l_plot = df_l_plot.rename(columns=rename_dict_l)
                        clean_cols_l = list(rename_dict_l.values())

                        for c in clean_cols_l:
                            df_l_plot[c] = pd.to_numeric(df_l_plot[c].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce')

                        fig_l = px.line(df_l_plot, x='年度', y=clean_cols_l, markers=True, title="将来負担比率")
                        fig_l.add_hline(y=100.0, line_dash="dash", line_color="green", annotation_text="健全水準目安 (100%)", annotation_position="bottom right")
                        fig_l.add_hline(y=350.0, line_dash="dash", line_color="orange", annotation_text="早期健全化基準:市町村 (350%)", annotation_position="top left")
                        fig_l.add_hline(y=400.0, line_dash="dash", line_color="red", annotation_text="早期健全化基準:都道府県 (400%)", annotation_position="top right")
                        
                        fig_l.update_layout(
                            yaxis_tickformat=".1f",
                            legend_title_text="",
                            legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5),
                            margin=dict(t=50, b=80)
                        )
                        fig_l.update_yaxes(title_text="比率（%）")
                        st.plotly_chart(fig_l, use_container_width=True)

                # 解説ガイド
                with st.expander("📖 実質公債費比率・将来負担比率の解説ガイド", expanded=False):
                    st.markdown("""
                    ##### 🏛️ 実質公債費比率（フロー面：年間の資金繰り・返済負担度）
                    自治体の標準的な年間収入（標準財政規模）に対して、**公債費（借金の元利償還金）やそれに準ずる返済額（准公債費）がどの程度を占めているか**を示す指標です（直近3か年の平均値で評価）。
                    
                    ##### 📈 将来負担比率（ストック面：累積負債の過重度）
                    自治体の年間標準収入に対して、**将来的に支払わなければならない負債の残高（実質的な将来負担額）がどの程度蓄積しているか**を示す指標です。
                    """)

            st.markdown("---")

            # 下段に公債費負担比率（参考指標）を配置
            st.markdown("### 🏛️ 公債費負担比率・起債制限比率（参考指標）")
            cols_kosai = get_cols_by_keywords(['公債費負担比率', '公債費比率', '起債制限比率'])
            if cols_kosai:
                fig_kosai = px.line(df_ov_city, x='年度', y=cols_kosai, markers=True, title="公債費負担比率等の推移")
                fig_kosai.add_hline(y=15.0, line_dash="dash", line_color="orange", annotation_text="警戒基準 (15%)", annotation_position="bottom right")
                fig_kosai.add_hline(y=20.0, line_dash="dash", line_color="red", annotation_text="危険基準・起債制限 (20%)", annotation_position="top right")
                fig_kosai.update_layout(yaxis_tickformat=".1f", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                fig_kosai.update_yaxes(title_text="比率（%）")
                st.plotly_chart(fig_kosai, use_container_width=True)
                st.caption("※一般財源のうち過去の借金返済（公債費）に投入された割合を示します。15%を超えると警戒水準、20%を超えると地方債の発行が制限されます。")
            else:
                st.info("公債費負担比率のデータが見つかりません。")

        # --- Tab 4: 人口・産業 ---
        with tab4:
            subtab_prof1, subtab_prof2 = st.tabs(["👥 人口・職員数", "🏗️ 産業割合"])
            
            with subtab_prof1:
                st.markdown("#### 1. 人口および職員数の時系列推移")
                
                pop_cols = [c for c in df_ov_city.columns if '人口' in c and not any(kw in c for kw in ['千円', 'パーセント', '%', '割合', '比率'])]
                emp_cols = []
                if not df_exp_city.empty:
                    emp_cols = [c for c in df_exp_city.columns if '職員数' in c and not any(kw in c for kw in ['千円', 'パーセント', '%', '割合', '比率', '手当'])]
                
                col_pop, col_emp = st.columns(2)
                
                with col_pop:
                    st.markdown("##### 👥 人口の推移")
                    if pop_cols:
                        df_pop_plot = df_ov_city.copy()
                        for c in pop_cols:
                            df_pop_plot[c] = pd.to_numeric(df_pop_plot[c].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce')
                        
                        fig_pop = px.line(df_pop_plot, x='年度', y=pop_cols, markers=True, title="人口推移")
                        fig_pop.update_layout(yaxis_tickformat=",", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                        fig_pop.update_yaxes(title_text="人口（人）")
                        st.plotly_chart(fig_pop, use_container_width=True)
                    else:
                        st.info("概要データ内に人口データが見つかりません。")
                
                with col_emp:
                    st.markdown("##### 🏛️ 職員数の推移")
                    if emp_cols and not df_exp_city.empty:
                        df_emp_plot = df_exp_city.copy()
                        for c in emp_cols:
                            df_emp_plot[c] = pd.to_numeric(df_emp_plot[c].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce')
                        
                        fig_emp = px.line(df_emp_plot, x='年度', y=emp_cols, markers=True, title="職員数推移")
                        fig_emp.update_layout(yaxis_tickformat=",", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                        fig_emp.update_yaxes(title_text="職員数（人）")
                        st.plotly_chart(fig_emp, use_container_width=True)
                    else:
                        st.info("性質別歳出データ内に職員数の列が見つかりません。")

                st.markdown("---")
                st.markdown(f"#### 2. 財政規模・人口に対する職員数・適正度分析（{scope_label} 比較）")
                
                avail_prof_years = sorted(df_overview['年度'].astype(str).unique()) if not df_overview.empty else []
                if avail_prof_years:
                    selected_prof_year = st.selectbox("比較分析対象年度を選択", avail_prof_years, index=len(avail_prof_years)-1, key="prof_year_select")
                    
                    df_ov_comp = get_comparison_df(df_overview)
                    df_exp_comp = get_comparison_df(df_exp_nature)
                    
                    df_ov_pref_p = df_ov_comp[df_ov_comp['年度'].astype(str) == str(selected_prof_year)].copy()
                    df_exp_pref_p = df_exp_comp[df_exp_comp['年度'].astype(str) == str(selected_prof_year)].copy() if not df_exp_comp.empty else pd.DataFrame()
                    
                    if not df_ov_pref_p.empty and not df_exp_pref_p.empty and emp_cols:
                        target_emp_col = emp_cols[0]
                        
                        df_emp_eval = pd.merge(
                            df_ov_pref_p, 
                            df_exp_pref_p[['団体名', target_emp_col]], 
                            on='団体名', 
                            how='inner'
                        )
                        
                        pop_col = get_population_col(df_emp_eval)
                        scale_col = [c for c in df_emp_eval.columns if '標準財政規模' in c]
                        
                        if pop_col and scale_col:
                            scale_col_name = scale_col[0]
                            
                            df_emp_eval['人口_num'] = pd.to_numeric(df_emp_eval[pop_col].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce').fillna(0)
                            df_emp_eval['標準財政規模_千円'] = pd.to_numeric(df_emp_eval[scale_col_name].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce').fillna(0)
                            df_emp_eval['職員数_num'] = pd.to_numeric(df_emp_eval[target_emp_col].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce').fillna(0)
                            
                            df_emp_eval['10億円当たり職員数'] = (df_emp_eval['職員数_num'] / (df_emp_eval['標準財政規模_千円'] / 1000000)).round(1)
                            df_emp_eval['1000人当たり職員数'] = (df_emp_eval['職員数_num'] / (df_emp_eval['人口_num'] / 1000)).round(1)
                            
                            col_eval_l, col_eval_r = st.columns(2)
                            
                            with col_eval_l:
                                st.markdown("##### 📊 標準財政規模 10億円当たり職員数")
                                df_eval_sorted = df_emp_eval.dropna(subset=['10億円当たり職員数']).sort_values('10億円当たり職員数', ascending=True).copy()
                                df_eval_sorted['表示色'] = df_eval_sorted['団体名'].apply(lambda x: '選択中の自治体' if x == selected_city else 'その他自治体')
                                
                                avg_10b = df_eval_sorted['10億円当たり職員数'].mean()
                                
                                fig_10b = px.bar(
                                    df_eval_sorted, x='10億円当たり職員数', y='団体名', orientation='h', color='表示色',
                                    text='10億円当たり職員数',
                                    title=f"{scope_label}（{selected_prof_year}年度）財政規模10億円当たり職員数（人/10億円）",
                                    color_discrete_map={'選択中の自治体': '#FF4B4B', 'その他自治体': '#1F77B4'},
                                    custom_data=['都道府県']
                                )
                                fig_10b.add_vline(x=avg_10b, line_dash="dash", line_color="green", annotation_text=f"平均 ({avg_10b:.1f}人)", annotation_position="top right")
                                fig_10b.update_traces(
                                    texttemplate='%{text:.1f}人', textposition='outside',
                                    hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{y}</b><br>10億円当たり職員数: %{x:.1f}人<extra></extra>"
                                )
                                fig_10b.update_layout(xaxis_title="職員数（人 / 標準財政規模10億円）", yaxis_title="自治体名", showlegend=True, height=max(400, len(df_eval_sorted)*25))
                                st.plotly_chart(fig_10b, use_container_width=True)
                            
                            with col_eval_r:
                                st.markdown("##### 📈 財政規模 vs 職員数（相関・適正分布 / 対数スケール）")
                                df_emp_eval['標準財政規模_億円'] = (df_emp_eval['標準財政規模_千円'] / 100000).round(1)
                                df_emp_eval['表示色'] = df_emp_eval['団体名'].apply(lambda x: '選択中の自治体' if x == selected_city else 'その他自治体')
                                
                                fig_scatter = px.scatter(
                                    df_emp_eval, x='標準財政規模_億円', y='職員数_num', color='表示色', text='団体名',
                                    trendline="ols",
                                    log_x=True, log_y=True,
                                    title=f"{scope_label}（{selected_prof_year}年度）標準財政規模 vs 職員数（対数表示）",
                                    color_discrete_map={'選択中の自治体': '#FF4B4B', 'その他自治体': '#1F77B4'},
                                    labels={'標準財政規模_億円': '標準財政規模 (億円 - ログ)', '職員数_num': '職員数 (人 - ログ)'},
                                    custom_data=['都道府県']
                                )
                                fig_scatter.update_traces(
                                    textposition='top center', marker=dict(size=12),
                                    hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{text}</b><br>標準財政規模: %{x:,.1f} 億円<br>職員数: %{y:,.0f} 人<extra></extra>"
                                )
                                st.plotly_chart(fig_scatter, use_container_width=True)
                                st.caption("※対数スケールにより、規模が大きく離れた自治体も傾向（トレンド）と比較しやすくなります。")

                            st.markdown(f"##### 📋 {scope_label} 自治体 職員数適正度指標一覧データテーブル")
                            disp_eval_cols = ['都道府県', '団体名', '人口_num', '標準財政規模_千円', '職員数_num', '10億円当たり職員数', '1000人当たり職員数']
                            rename_eval_dict = {
                                '人口_num': '人口(人)',
                                '標準財政規模_千円': '標準財政規模(千円)',
                                '職員数_num': '職員数(人)',
                                '10億円当たり職員数': '10億円当たり職員数(人)',
                                '1000人当たり職員数': '1,000人当たり職員数(人)'
                            }
                            st.dataframe(df_emp_eval[disp_eval_cols].sort_values('10億円当たり職員数').rename(columns=rename_eval_dict), use_container_width=True)
                        else:
                            st.info("適正度の算定に必要な標準財政規模または人口の列が見つかりません。")
                    else:
                        st.info("該当年度の比較用性質別歳出データ（職員数）が存在しません。")

            with subtab_prof2:
                st.markdown("#### 🏗️ 産業別就業者数・構成割合の推移")
                
                ind_cols = [c for c in df_ov_city.columns if any(kw in c for kw in ['第1次', '第2次', '第3次', '一次', '二次', '三次', '1次', '2次', '3次', '産業'])]
                
                if ind_cols and not df_ov_city.empty:
                    df_ind_plot = df_ov_city.copy()
                    for c in ind_cols:
                        df_ind_plot[c] = pd.to_numeric(df_ind_plot[c].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce').fillna(0)
                    
                    fig_ind = px.bar(
                        df_ind_plot, x='年度', y=ind_cols,
                        title=f"{selected_city} 産業構造の推移",
                        barmode='stack'
                    )
                    fig_ind.update_layout(
                        yaxis_tickformat=",", 
                        xaxis_title="年度", 
                        yaxis_title="数値 / 割合",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    st.plotly_chart(fig_ind, use_container_width=True)
                    
                    st.markdown("##### 📋 産業別データテーブル")
                    st.dataframe(df_ind_plot[['年度'] + ind_cols], use_container_width=True)
                else:
                    st.info("概要データ内に産業別就業者数または産業割合の該当データが見つかりません。")

        # --- Tab 5: データ一覧 ---
        with tab5:
            st.markdown("#### 概要データテーブル一覧")
            st.dataframe(df_ov_city, use_container_width=True)
    else:
        st.warning("対象自治体の概要データが存在しません。")

# ==========================================
# メニュー2: 歳入
# ==========================================
elif menu == "歳入":
    st.markdown("### 歳入の推移と分析")
    
    with st.expander("📖 一般財源と特定財源の違い・歳入用語ガイド", expanded=False):
        st.markdown("""
        ##### 📌 一般財源と特定財源の違い
        * **一般財源（使い道が自由なお金）**
          使い道（使途）が特定されておらず、自治体がどのような事業にも自由に割り振ることができる財源です。
          - **地方税**: 市民税や固定資産税など、自治体が独自に徴収する税金。
          - **地方交付税**: 全国どこでも一定の行政サービスが受けられるよう、国から配分される資金（使途は自由）。
          - **地方譲与税・地方特例交付金**: 国税の一部を地方に譲与・補填するもの。
        * **特定財源（使い道が限定されているお金）**
          使い道（使途）があらかじめ特定の事業や目的に限定されている財源です。
          - **国庫支出金・都道府県支出金**: 国や県から特定の事業（道路整備、福祉給付など）に対して出される補助金・負担金。
          - **地方債（借金）**: 特定の大型建設事業などの財源として発行する借入金。
          - **使用料・手数料**: 公共施設の使用料や証明書発行手数料など。
          - **寄附金**: ふるさと納税など、特定の使途に指定されることが多い資金。

        ---
        ##### 💡 財政の自立度を測る視点
        一般財源のうち、自主的に稼いだ税金（地方税）の割合が高いほど**「自主財源比率」**が高くなり、国や県の意向に左右されにくい自立した財政運営が可能となります。
        """)

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
            "📊 自治体間比較（総額）", 
            "👥 自治体間比較（1人当たり）",
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
                id_vars=['都道府県', '団体名', total_col_name], 
                value_vars=target_cols, 
                var_name='項目_raw', 
                value_name='金額'
            )
            df_melt['項目名'] = df_melt['項目_raw'].str.replace('_合計', '')
            df_melt['割合(%)'] = (df_melt['金額'] / df_melt[total_col_name] * 100).fillna(0).round(1)

            fig = px.bar(
                df_melt, x='団体名', y='金額', color='項目名',
                title=f"{scope_label}（{comp_year}年度）自治体別{title_suffix}構成比較（総額・大きい順）", barmode='stack',
                category_orders={
                    '団体名': sorted_cities, 
                    '項目名': [c.replace('_合計', '') for c in target_cols]
                },
                custom_data=['都道府県', '項目名', '割合(%)']
            )
            fig.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
            fig.update_traces(
                hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>項目名: %{customdata[1]}<br>金額: %{y:,.0f} 千円<br>構成比: %{customdata[2]}%<extra></extra>"
            )
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown(f"#### {title_suffix}比較データテーブル（総額）")
            st.dataframe(df_comp[['都道府県', '団体名', total_col_name] + target_cols], use_container_width=True)

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
                id_vars=['都道府県', '団体名', per_capita_total, '人口_num'], 
                value_vars=per_capita_cols, 
                var_name='項目_raw', 
                value_name='1人当たり金額'
            )
            df_melt['項目名'] = df_melt['項目_raw'].str.replace('_合計', '').str.replace('_1人当たり', '')
            df_melt['割合(%)'] = (df_melt['1人当たり金額'] / df_melt[per_capita_total] * 100).fillna(0).round(1)

            fig = px.bar(
                df_melt, x='団体名', y='1人当たり金額', color='項目名',
                title=f"{scope_label}（{comp_year}年度）自治体別1人当たり{title_suffix}構成比較（大きい順 / 人口参照: {pop_col}）", barmode='stack',
                category_orders={
                    '団体名': sorted_cities, 
                    '項目名': [c.replace('_合計', '') for c in target_cols]
                },
                custom_data=['都道府県', '項目名', '割合(%)']
            )
            fig.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
            fig.update_traces(
                hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>項目名: %{customdata[1]}<br>1人当たり金額: %{y:,.2f} 千円/人<br>構成比: %{customdata[2]}%<extra></extra>"
            )
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown(f"#### 1人当たり{title_suffix}比較データテーブル")
            disp_cols = ['都道府県', '団体名', '人口_num', per_capita_total] + per_capita_cols
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
            st.subheader(f"{scope_label} 自治体歳入比較（総額）")
            df_pref_rev = get_comparison_df(df_revenue)
            
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
                st.info("該当する比較対象データが見つかりません。")

        with tab_rev3:
            st.subheader(f"{scope_label} 自治体歳入比較（人口1人当たり）")
            df_pref_rev = get_comparison_df(df_revenue)
            df_pref_ov = get_comparison_df(df_overview)
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
                st.info("人口データまたは比較対象歳入データが見つかりません。")

        with tab_rev4:
            st.subheader(f"{scope_label} 自治体歳入分析（全期間変化率ランキング）")
            df_pref_rev = get_comparison_df(df_revenue)
            
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
                
                df_min = df_pref_rev[df_pref_rev['年度'].astype(str) == min_year][['都道府県', '団体名', selected_target_col]].rename(columns={selected_target_col: '初期金額'})
                df_max = df_pref_rev[df_pref_rev['年度'].astype(str) == max_year][['団体名', selected_target_col]].rename(columns={selected_target_col: '最新金額'})
                
                df_growth = df_min.merge(df_max, on='団体名', how='inner')
                df_growth = df_growth[df_growth['初期金額'] > 0].copy()
                
                df_growth['増加額'] = df_growth['最新金額'] - df_growth['初期金額']
                df_growth['増加率(%)'] = ((df_growth['増加額'] / df_growth['初期金額']) * 100).round(1)
                df_growth = df_growth.sort_values('増加率(%)', ascending=False)
                
                target_name = rev_options[selected_target_col]
                
                fig_growth = px.bar(
                    df_growth, x='団体名', y='増加率(%)', text='増加率(%)',
                    title=f"{scope_label} 自治体 {target_name} 増加率ランキング（{min_year}➔{max_year}年度）",
                    color='増加率(%)', color_continuous_scale='RdBu_r',
                    custom_data=['都道府県']
                )
                fig_growth.update_traces(
                    texttemplate='%{text:.1f}%', textposition='outside',
                    hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>増加率: %{y:.1f}%<extra></extra>"
                )
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
                st.info("該当する比較対象データが見つかりません。")

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
            "📊 自治体間比較（総額）", 
            "👥 自治体間比較（1人当たり）",
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
            st.subheader(f"{scope_label} 自治体性質別歳出比較（総額）")
            df_pref_exp = get_comparison_df(df_exp_nature)
            
            if not df_pref_exp.empty:
                avail_years_exp_pref = df_pref_exp['年度'].astype(str).unique()
                comp_year_exp = st.selectbox("比較する年度を選択", avail_years_exp_pref, index=len(avail_years_exp_pref)-1, key="comp_exp_year")
                
                df_comp_exp = df_pref_exp[df_pref_exp['年度'].astype(str) == str(comp_year_exp)].copy()
                
                for c in main_categories:
                    df_comp_exp[c] = pd.to_numeric(df_comp_exp[c].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce').fillna(0)
                
                df_comp_exp['歳出合計'] = df_comp_exp[main_categories].sum(axis=1)
                df_comp_exp = df_comp_exp.sort_values('歳出合計', ascending=False)
                sorted_cities_exp = df_comp_exp['団体名'].tolist()
                
                df_melt_comp_exp = df_comp_exp.melt(id_vars=['都道府県', '団体名', '歳出合計'], value_vars=main_categories, var_name='項目_raw', value_name='金額')
                df_melt_comp_exp['項目名'] = df_melt_comp_exp['項目_raw'].str.replace('_合計', '')
                df_melt_comp_exp['割合(%)'] = (df_melt_comp_exp['金額'] / df_melt_comp_exp['歳出合計'] * 100).round(1)

                fig_comp_exp = px.bar(
                    df_melt_comp_exp, x='団体名', y='金額', color='項目名',
                    title=f"{scope_label}（{comp_year_exp}年度）自治体別性質別歳出構成比較（総額・大きい順）", barmode='stack',
                    category_orders={'団体名': sorted_cities_exp, '項目名': [c.replace('_合計', '') for c in main_categories]},
                    custom_data=['都道府県', '項目名', '割合(%)']
                )
                fig_comp_exp.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
                fig_comp_exp.update_traces(
                    hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>項目名: %{customdata[1]}<br>金額: %{y:,.0f} 千円<br>構成比: %{customdata[2]}%<extra></extra>"
                )
                st.plotly_chart(fig_comp_exp, use_container_width=True)
                
                st.markdown("#### 性質別歳出比較データテーブル（総額）")
                st.dataframe(df_comp_exp[['都道府県', '団体名', '歳出合計'] + main_categories], use_container_width=True)
            else:
                st.info("該当する比較対象データが見つかりません。")

        with tab_exp3:
            st.subheader(f"{scope_label} 自治体性質別歳出比較（人口1人当たり）")
            df_pref_exp = get_comparison_df(df_exp_nature)
            df_pref_ov = get_comparison_df(df_overview)
            pop_col = get_population_col(df_overview)
            
            if not df_pref_exp.empty and pop_col:
                avail_years_exp_pref = df_pref_exp['年度'].astype(str).unique()
                comp_year_exp_pop = st.selectbox("比較する年度を選択", avail_years_exp_pref, index=len(avail_years_exp_pref)-1, key="comp_exp_pop_year")
                
                df_comp_exp = df_pref_exp[df_pref_exp['年度'].astype(str) == str(comp_year_exp_pop)].copy()
                df_pref_ov_year = df_pref_ov[df_pref_ov['年度'].astype(str) == str(comp_year_exp_pop)].copy()
                df_pref_ov_year['人口_num'] = pd.to_numeric(df_pref_ov_year[pop_col].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce').fillna(0)
                
                df_comp_exp_pop = df_comp_exp.merge(df_pref_ov_year[['団体名', '人口_num']], on='団体名', how='left')
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
                        id_vars=['都道府県', '団体名', '1人当たり歳出合計', '人口_num'], 
                        value_vars=per_capita_cols_exp, 
                        var_name='項目_raw', 
                        value_name='1人当たり金額'
                    )
                    df_melt_comp_exp_pop['項目名'] = df_melt_comp_exp_pop['項目_raw'].str.replace('_合計', '').str.replace('_1人当たり', '')
                    df_melt_comp_exp_pop['割合(%)'] = (df_melt_comp_exp_pop['1人当たり金額'] / df_melt_comp_exp_pop['1人当たり歳出合計'] * 100).round(1)

                    fig_comp_exp_pop = px.bar(
                        df_melt_comp_exp_pop, x='団体名', y='1人当たり金額', color='項目名',
                        title=f"{scope_label}（{comp_year_exp_pop}年度）自治体別1人当たり性質別歳出構成比較（大きい順 / 人口参照: {pop_col}）", barmode='stack',
                        category_orders={'団体名': sorted_cities_exp_pop, '項目名': [c.replace('_合計', '') for c in main_categories]},
                        custom_data=['都道府県', '項目名', '割合(%)']
                    )
                    fig_comp_exp_pop.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
                    fig_comp_exp_pop.update_traces(
                        hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>項目名: %{customdata[1]}<br>1人当たり金額: %{y:,.2f} 千円/人<br>構成比: %{customdata[2]}%<extra></extra>"
                    )
                    st.plotly_chart(fig_comp_exp_pop, use_container_width=True)
                    
                    st.markdown("#### 1人当たり性質別歳出比較データテーブル")
                    disp_cols_exp_pop = ['都道府県', '団体名', '人口_num', '1人当たり歳出合計'] + per_capita_cols_exp
                    rename_dict_exp = {'人口_num': f'人口({pop_col})', '1人当たり歳出合計': '1人当たり歳出合計(千円)'}
                    for c in per_capita_cols_exp:
                        rename_dict_exp[c] = c.replace('_合計', '').replace('_1人当たり', '') + '(千円/人)'
                    
                    st.dataframe(df_comp_exp_pop[disp_cols_exp_pop].rename(columns=rename_dict_exp), use_container_width=True)
                else:
                    st.warning("該当年度の人口データが見つからないか、全自治体の人口が0です。")
            else:
                st.info("人口データまたは比較対象性質別歳出データが見つかりません。")

        with tab_exp4:
            st.subheader(f"{scope_label} 自治体性質別歳出分析（全期間変化率ランキング）")
            df_pref_exp = get_comparison_df(df_exp_nature)
            
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
                
                df_exp_min = df_pref_exp[df_pref_exp['年度'].astype(str) == min_exp_year][['都道府県', '団体名', selected_exp_target]].rename(columns={selected_exp_target: '初期金額'})
                df_exp_max = df_pref_exp[df_pref_exp['年度'].astype(str) == max_exp_year][['団体名', selected_exp_target]].rename(columns={selected_exp_target: '最新金額'})
                
                df_exp_growth = df_exp_min.merge(df_exp_max, on='団体名', how='inner')
                df_exp_growth = df_exp_growth[df_exp_growth['初期金額'] > 0].copy()
                
                df_exp_growth['増加額'] = df_exp_growth['最新金額'] - df_exp_growth['初期金額']
                df_exp_growth['増加率(%)'] = ((df_exp_growth['増加額'] / df_exp_growth['初期金額']) * 100).round(1)
                df_exp_growth = df_exp_growth.sort_values('増加率(%)', ascending=False)
                
                exp_target_name = exp_options[selected_exp_target]
                
                fig_exp_growth = px.bar(
                    df_exp_growth, x='団体名', y='増加率(%)', text='増加率(%)',
                    title=f"{scope_label} 自治体 {exp_target_name} 増加率ランキング（{min_exp_year}➔{max_exp_year}年度）",
                    color='増加率(%)', color_continuous_scale='RdBu_r',
                    custom_data=['都道府県']
                )
                fig_exp_growth.update_traces(
                    texttemplate='%{text:.1f}%', textposition='outside',
                    hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>増加率: %{y:.1f}%<extra></extra>"
                )
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
                st.info("該当する比較対象データが見つかりません。")
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
            "📊 自治体間比較（総額）", 
            "👥 自治体間比較（1人当たり）",
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
            st.subheader(f"{scope_label} 自治体目的別歳出比較（総額）")
            df_pref_purp = get_comparison_df(df_exp_purpose)
            
            if not df_pref_purp.empty:
                avail_years_purp_pref = df_pref_purp['年度'].astype(str).unique()
                comp_year_purp = st.selectbox("比較する年度を選択", avail_years_purp_pref, index=len(avail_years_purp_pref)-1, key="comp_purp_year")
                
                df_comp_purp = df_pref_purp[df_pref_purp['年度'].astype(str) == str(comp_year_purp)].copy()
                
                for c in main_purp_categories:
                    df_comp_purp[c] = pd.to_numeric(df_comp_purp[c].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce').fillna(0)
                
                df_comp_purp['目的別歳出合計'] = df_comp_purp[main_purp_categories].sum(axis=1)
                df_comp_purp = df_comp_purp.sort_values('目的別歳出合計', ascending=False)
                sorted_cities_purp = df_comp_purp['団体名'].tolist()
                
                df_melt_comp_purp = df_comp_purp.melt(id_vars=['都道府県', '団体名', '目的別歳出合計'], value_vars=main_purp_categories, var_name='項目_raw', value_name='金額')
                df_melt_comp_purp['項目名'] = df_melt_comp_purp['項目_raw'].str.replace('_合計', '')
                df_melt_comp_purp['割合(%)'] = (df_melt_comp_purp['金額'] / df_melt_comp_purp['目的別歳出合計'] * 100).round(1)

                fig_comp_purp = px.bar(
                    df_melt_comp_purp, x='団体名', y='金額', color='項目名',
                    title=f"{scope_label}（{comp_year_purp}年度）自治体別目的別歳出構成比較（総額・大きい順）", barmode='stack',
                    category_orders={'団体名': sorted_cities_purp, '項目名': [c.replace('_合計', '') for c in main_purp_categories]},
                    custom_data=['都道府県', '項目名', '割合(%)']
                )
                fig_comp_purp.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
                fig_comp_purp.update_traces(
                    hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>項目名: %{customdata[1]}<br>金額: %{y:,.0f} 千円<br>構成比: %{customdata[2]}%<extra></extra>"
                )
                st.plotly_chart(fig_comp_purp, use_container_width=True)
                
                st.markdown("#### 目的別歳出比較データテーブル（総額）")
                st.dataframe(df_comp_purp[['都道府県', '団体名', '目的別歳出合計'] + main_purp_categories], use_container_width=True)
            else:
                st.info("該当する比較対象データが見つかりません。")

        with tab_purp3:
            st.subheader(f"{scope_label} 自治体目的別歳出比較（人口1人当たり）")
            df_pref_purp = get_comparison_df(df_exp_purpose)
            df_pref_ov = get_comparison_df(df_overview)
            pop_col = get_population_col(df_overview)
            
            if not df_pref_purp.empty and pop_col:
                avail_years_purp_pref = df_pref_purp['年度'].astype(str).unique()
                comp_year_purp_pop = st.selectbox("比較する年度を選択", avail_years_purp_pref, index=len(avail_years_purp_pref)-1, key="comp_purp_pop_year")
                
                df_comp_purp = df_pref_purp[df_pref_purp['年度'].astype(str) == str(comp_year_purp_pop)].copy()
                df_pref_ov_year = df_pref_ov[df_pref_ov['年度'].astype(str) == str(comp_year_purp_pop)].copy()
                df_pref_ov_year['人口_num'] = pd.to_numeric(df_pref_ov_year[pop_col].astype(str).str.replace(',', '').str.replace('-', '0'), errors='coerce').fillna(0)
                
                df_comp_purp_pop = df_comp_purp.merge(df_pref_ov_year[['団体名', '人口_num']], on='団体名', how='left')
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
                        id_vars=['都道府県', '団体名', '1人当たり目的別歳出合計', '人口_num'], 
                        value_vars=per_capita_cols_purp, 
                        var_name='項目_raw', 
                        value_name='1人当たり金額'
                    )
                    df_melt_comp_purp_pop['項目名'] = df_melt_comp_purp_pop['項目_raw'].str.replace('_合計', '').str.replace('_1人当たり', '')
                    df_melt_comp_purp_pop['割合(%)'] = (df_melt_comp_purp_pop['1人当たり金額'] / df_melt_comp_purp_pop['1人当たり目的別歳出合計'] * 100).round(1)

                    fig_comp_purp_pop = px.bar(
                        df_melt_comp_purp_pop, x='団体名', y='1人当たり金額', color='項目名',
                        title=f"{scope_label}（{comp_year_purp_pop}年度）自治体別1人当たり目的別歳出構成比較（大きい順 / 人口参照: {pop_col}）", barmode='stack',
                        category_orders={'団体名': sorted_cities_purp_pop, '項目名': [c.replace('_合計', '') for c in main_purp_categories]},
                        custom_data=['都道府県', '項目名', '割合(%)']
                    )
                    fig_comp_purp_pop.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
                    fig_comp_purp_pop.update_traces(
                        hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>項目名: %{customdata[1]}<br>1人当たり金額: %{y:,.2f} 千円/人<br>構成比: %{customdata[2]}%<extra></extra>"
                    )
                    st.plotly_chart(fig_comp_purp_pop, use_container_width=True)
                    
                    st.markdown("#### 1人当たり目的別歳出比較データテーブル")
                    disp_cols_purp_pop = ['都道府県', '団体名', '人口_num', '1人当たり目的別歳出合計'] + per_capita_cols_purp
                    rename_dict_purp = {'人口_num': f'人口({pop_col})', '1人当たり目的別歳出合計': '1人当たり目的別歳出合計(千円)'}
                    for c in per_capita_cols_purp:
                        rename_dict_purp[c] = c.replace('_合計', '').replace('_1人当たり', '') + '(千円/人)'
                    
                    st.dataframe(df_comp_purp_pop[disp_cols_purp_pop].rename(columns=rename_dict_purp), use_container_width=True)
                else:
                    st.warning("該当年度の人口データが見つからないか、全自治体の人口が0です。")
            else:
                st.info("人口データまたは比較対象目的別歳出データが見つかりません。")

        with tab_purp4:
            st.subheader(f"{scope_label} 自治体目的別歳出分析（全期間変化率ランキング）")
            df_pref_purp = get_comparison_df(df_exp_purpose)
            
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
                
                df_purp_min = df_pref_purp[df_pref_purp['年度'].astype(str) == min_purp_year][['都道府県', '団体名', selected_purp_target]].rename(columns={selected_purp_target: '初期金額'})
                df_purp_max = df_pref_purp[df_pref_purp['年度'].astype(str) == max_purp_year][['団体名', selected_purp_target]].rename(columns={selected_purp_target: '最新金額'})
                
                df_purp_growth = df_purp_min.merge(df_purp_max, on='団体名', how='inner')
                df_purp_growth = df_purp_growth[df_purp_growth['初期金額'] > 0].copy()
                
                df_purp_growth['増加額'] = df_purp_growth['最新金額'] - df_purp_growth['初期金額']
                df_purp_growth['増加率(%)'] = ((df_purp_growth['増加額'] / df_purp_growth['初期金額']) * 100).round(1)
                df_purp_growth = df_purp_growth.sort_values('増加率(%)', ascending=False)
                
                purp_target_name = purp_options[selected_purp_target]
                
                fig_purp_growth = px.bar(
                    df_purp_growth, x='団体名', y='増加率(%)', text='増加率(%)',
                    title=f"{scope_label} 自治体 {purp_target_name} 増加率ランキング（{min_purp_year}➔{max_purp_year}年度）",
                    color='増加率(%)', color_continuous_scale='RdBu_r',
                    custom_data=['都道府県']
                )
                fig_purp_growth.update_traces(
                    texttemplate='%{text:.1f}%', textposition='outside',
                    hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>増加率: %{y:.1f}%<extra></extra>"
                )
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
                st.info("該当する比較対象データが見つかりません。")
    else:
        st.warning("対象自治体の目的別歳出データが存在しません。")

# ==========================================
# メニュー5: 地方債・基金
# ==========================================
elif menu == "地方債・基金":
    st.markdown("### 地方債・積立金（基金）現在高の推移と分析")
    
    with st.expander("📖 地方債・基金・将来負担用語ガイド", expanded=False):
        st.markdown("""
        ##### 📌 主要指標の解説
        * **地方債（借金）**
          インフラ整備や大型建設事業など、将来世代も利用する施設の財源を調達するために自治体が長期で借り入れる資金。
        * **積立金 / 基金（貯金）**
          特定の目的や将来の非常事態に備えて積み立てている資金。
          - **財政調整基金**: 景気変動による税収減や災害等による急な支出増に備える「自治体の普通預金」。
          - **減債基金**: 将来の地方債（借金）の一括償還や返済負担軽減のために積み立てる基金。
          - **特定目的基金**: 公共施設整備や福祉基金など、指定した目的のために設置する基金。
        * **債務負担行為**
          数カ年にわたる事業など、翌年度以降に支出することを前もって約束・契約する行為（将来の支払い義務）。
        * **実質将来負担残高（推計）**
          $\text{地方債現在高} + \text{債務負担行為額} - \text{積立金現在高（基金）}$ 
          現時点での借金と将来の支払い約束から、貯金を差し引いた「実質的な将来の負担純額」です。
        * **公営企業等繰出金**
          水道・下水道・病院・交通などの公営企業会計（独立会計）の赤字補填や建設費支援のため、一般会計から繰り出す資金。
        """)

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
            "📊 自治体間比較（総額）", 
            "👥 自治体間比較（1人当たり）",
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

        # --- Tab 2: 自治体間比較（総額） ---
        with tab_bonds2:
            st.subheader(f"{scope_label} 自治体比較（総額）")
            df_pref_bonds = get_comparison_df(df_bonds)
            
            if not df_pref_bonds.empty:
                avail_years_bonds_pref = df_pref_bonds['年度'].astype(str).unique()
                comp_year_bonds = st.selectbox("比較する年度を選択", avail_years_bonds_pref, index=len(avail_years_bonds_pref)-1, key="comp_bonds_year")
                
                subtab2_bonds, subtab2_funds, subtab2_pub = st.tabs(["🏛️ 地方債・積立金比較", "💰 基金（積立金）構成比較", "🏥 公営企業繰出金比較"])
                
                df_comp_b = df_pref_bonds[df_pref_bonds['年度'].astype(str) == str(comp_year_bonds)].copy()
                
                with subtab2_bonds:
                    df_comp_b = df_comp_b.sort_values('地方債現在高_合計', ascending=False)
                    sorted_cities_b = df_comp_b['団体名'].tolist()
                    
                    df_melt_b = df_comp_b.melt(
                        id_vars=['都道府県', '団体名'], 
                        value_vars=['地方債現在高_合計', '積立金現在高_合計'], 
                        var_name='項目_raw', value_name='金額'
                    )
                    df_melt_b['項目名'] = df_melt_b['項目_raw'].str.replace('積立金現在高_合計', '積立金現在高（基金）')
                    
                    fig_comp_b = px.bar(
                        df_melt_b, x='団体名', y='金額', color='項目名',
                        title=f"{scope_label}（{comp_year_bonds}年度）自治体別 地方債 vs 積立金比較（大きい順）",
                        barmode='group',
                        category_orders={'団体名': sorted_cities_b},
                        custom_data=['都道府県', '項目名']
                    )
                    fig_comp_b.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
                    fig_comp_b.update_traces(
                        hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>項目名: %{customdata[1]}<br>金額: %{y:,.0f} 千円<extra></extra>"
                    )
                    st.plotly_chart(fig_comp_b, use_container_width=True)
                    st.dataframe(df_comp_b[['都道府県', '団体名', '地方債現在高_合計', '積立金現在高_合計', '債務負担行為額(翌年度以降支出予定額)_合計']], use_container_width=True)

                with subtab2_funds:
                    if fund_sub_cats:
                        df_comp_b['基金合計_calc'] = df_comp_b[fund_sub_cats].sum(axis=1)
                        df_comp_b_fund = df_comp_b.sort_values('基金合計_calc', ascending=False)
                        sorted_cities_fund = df_comp_b_fund['団体名'].tolist()
                        
                        df_melt_fund_comp = df_comp_b_fund.melt(
                            id_vars=['都道府県', '団体名', '基金合計_calc'], value_vars=fund_sub_cats,
                            var_name='項目_raw', value_name='金額'
                        )
                        df_melt_fund_comp['項目名'] = df_melt_fund_comp['項目_raw'].str.replace('積立金現在高_', '')
                        df_melt_fund_comp['割合(%)'] = (df_melt_fund_comp['金額'] / df_melt_fund_comp['基金合計_calc'] * 100).fillna(0).round(1)

                        fig_comp_f = px.bar(
                            df_melt_fund_comp, x='団体名', y='金額', color='項目名',
                            title=f"{scope_label}（{comp_year_bonds}年度）自治体別 基金構成比較（大きい順）",
                            barmode='stack',
                            category_orders={'団体名': sorted_cities_fund},
                            custom_data=['都道府県', '項目名', '割合(%)']
                        )
                        fig_comp_f.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
                        fig_comp_f.update_traces(
                            hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>項目名: %{customdata[1]}<br>金額: %{y:,.0f} 千円<br>構成比: %{customdata[2]}%<extra></extra>"
                        )
                        st.plotly_chart(fig_comp_f, use_container_width=True)
                        st.dataframe(df_comp_b_fund[['都道府県', '団体名', '基金合計_calc'] + fund_sub_cats], use_container_width=True)

                with subtab2_pub:
                    if pub_sub_cats:
                        df_comp_b['繰出金合計_calc'] = df_comp_b[pub_sub_cats].sum(axis=1)
                        df_comp_b_pub = df_comp_b.sort_values('繰出金合計_calc', ascending=False)
                        sorted_cities_pub = df_comp_b_pub['団体名'].tolist()
                        
                        df_melt_pub_comp = df_comp_b_pub.melt(
                            id_vars=['都道府県', '団体名', '繰出金合計_calc'], value_vars=pub_sub_cats,
                            var_name='項目_raw', value_name='金額'
                        )
                        df_melt_pub_comp['項目名'] = df_melt_pub_comp['項目_raw'].str.replace('公営企業等に対する繰出金_うち', '').str.replace('会計', '')
                        df_melt_pub_comp['割合(%)'] = (df_melt_pub_comp['金額'] / df_melt_pub_comp['繰出金合計_calc'] * 100).fillna(0).round(1)

                        fig_comp_p = px.bar(
                            df_melt_pub_comp, x='団体名', y='金額', color='項目名',
                            title=f"{scope_label}（{comp_year_bonds}年度）自治体別 公営企業繰出金比較（大きい順）",
                            barmode='stack',
                            category_orders={'団体名': sorted_cities_pub},
                            custom_data=['都道府県', '項目名', '割合(%)']
                        )
                        fig_comp_p.update_layout(yaxis_tickformat=",", xaxis_title="自治体名", yaxis_title="金額（千円）")
                        fig_comp_p.update_traces(
                            hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>項目名: %{customdata[1]}<br>金額: %{y:,.0f} 千円<br>構成比: %{customdata[2]}%<extra></extra>"
                        )
                        st.plotly_chart(fig_comp_p, use_container_width=True)
                        st.dataframe(df_comp_b_pub[['都道府県', '団体名', '繰出金合計_calc'] + pub_sub_cats], use_container_width=True)
            else:
                st.info("該当する比較対象データが見つかりません。")

        # --- Tab 3: 自治体間比較（1人当たり） ---
        with tab_bonds3:
            st.subheader(f"{scope_label} 自治体比較（人口1人当たり）")
            df_pref_bonds = get_comparison_df(df_bonds)
            df_pref_ov = get_comparison_df(df_overview)
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
                            id_vars=['都道府県', '団体名', '人口_num'],
                            value_vars=['1人当たり地方債現在高', '1人当たり積立金現在高'],
                            var_name='項目_raw', value_name='1人当たり金額'
                        )
                        
                        fig_pop_b = px.bar(
                            df_melt_b_pop, x='団体名', y='1人当たり金額', color='項目_raw',
                            title=f"{scope_label}（{comp_year_bonds_pop}年度）自治体別 1人当たり地方債 vs 積立金比較（大きい順 / 人口参照: {pop_col}）",
                            barmode='group',
                            category_orders={'団体名': sorted_cities_pop_b},
                            custom_data=['都道府県', '項目_raw']
                        )
                        fig_pop_b.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
                        fig_pop_b.update_traces(
                            hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>項目名: %{customdata[1]}<br>1人当たり金額: %{y:,.2f} 千円/人<extra></extra>"
                        )
                        st.plotly_chart(fig_pop_b, use_container_width=True)
                        st.dataframe(df_comp_b_pop[['都道府県', '団体名', '人口_num', '1人当たり地方債現在高', '1人当たり積立金現在高']], use_container_width=True)

                    with subtab3_funds:
                        if fund_sub_cats:
                            fund_per_capita_cols = [sc + '_1人当たり' for sc in fund_sub_cats]
                            df_comp_b_pop['1人当たり基金合計'] = df_comp_b_pop[fund_per_capita_cols].sum(axis=1)
                            df_comp_b_pop_f = df_comp_b_pop.sort_values('1人当たり基金合計', ascending=False)
                            sorted_cities_pop_f = df_comp_b_pop_f['団体名'].tolist()
                            
                            df_melt_f_pop = df_comp_b_pop_f.melt(
                                id_vars=['都道府県', '団体名', '1人当たり基金合計'],
                                value_vars=fund_per_capita_cols,
                                var_name='項目_raw', value_name='1人当たり金額'
                            )
                            df_melt_f_pop['項目名'] = df_melt_f_pop['項目_raw'].str.replace('積立金現在高_', '').str.replace('_1人当たり', '')
                            df_melt_f_pop['割合(%)'] = (df_melt_f_pop['1人当たり金額'] / df_melt_f_pop['1人当たり基金合計'] * 100).fillna(0).round(1)

                            fig_pop_f = px.bar(
                                df_melt_f_pop, x='団体名', y='1人当たり金額', color='項目名',
                                title=f"{scope_label}（{comp_year_bonds_pop}年度）自治体別 1人当たり基金構成比較（大きい順）",
                                barmode='stack',
                                category_orders={'団体名': sorted_cities_pop_f},
                                custom_data=['都道府県', '項目名', '割合(%)']
                            )
                            fig_pop_f.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
                            fig_pop_f.update_traces(
                                hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>項目名: %{customdata[1]}<br>1人当たり金額: %{y:,.2f} 千円/人<br>構成比: %{customdata[2]}%<extra></extra>"
                            )
                            st.plotly_chart(fig_pop_f, use_container_width=True)
                            st.dataframe(df_comp_b_pop_f[['都道府県', '団体名', '1人当たり基金合計'] + fund_per_capita_cols], use_container_width=True)

                    with subtab3_pub:
                        if pub_sub_cats:
                            pub_per_capita_cols = [sc + '_1人当たり' for sc in pub_sub_cats]
                            df_comp_b_pop['1人当たり繰出金合計'] = df_comp_b_pop[pub_per_capita_cols].sum(axis=1)
                            df_comp_b_pop_p = df_comp_b_pop.sort_values('1人当たり繰出金合計', ascending=False)
                            sorted_cities_pop_p = df_comp_b_pop_p['団体名'].tolist()
                            
                            df_melt_p_pop = df_comp_b_pop_p.melt(
                                id_vars=['都道府県', '団体名', '1人当たり繰出金合計'],
                                value_vars=pub_per_capita_cols,
                                var_name='項目_raw', value_name='1人当たり金額'
                            )
                            df_melt_p_pop['項目名'] = df_melt_p_pop['項目_raw'].str.replace('公営企業等に対する繰出金_うち', '').str.replace('会計_1人当たり', '')
                            df_melt_p_pop['割合(%)'] = (df_melt_p_pop['1人当たり金額'] / df_melt_p_pop['1人当たり繰出金合計'] * 100).fillna(0).round(1)

                            fig_pop_p = px.bar(
                                df_melt_p_pop, x='団体名', y='1人当たり金額', color='項目名',
                                title=f"{scope_label}（{comp_year_bonds_pop}年度）自治体別 1人当たり公営企業繰出金比較（大きい順）",
                                barmode='stack',
                                category_orders={'団体名': sorted_cities_pop_p},
                                custom_data=['都道府県', '項目名', '割合(%)']
                            )
                            fig_pop_p.update_layout(yaxis_tickformat=",.1f", xaxis_title="自治体名", yaxis_title="1人当たり金額（千円/人）")
                            fig_pop_p.update_traces(
                                hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>項目名: %{customdata[1]}<br>1人当たり金額: %{y:,.2f} 千円/人<br>構成比: %{customdata[2]}%<extra></extra>"
                            )
                            st.plotly_chart(fig_pop_p, use_container_width=True)
                            st.dataframe(df_comp_b_pop_p[['都道府県', '団体名', '1人当たり繰出金合計'] + pub_per_capita_cols], use_container_width=True)
                else:
                    st.warning("該当年度の人口データが見つからないか、全自治体の人口が0です。")
            else:
                st.info("人口データまたは比較対象地方債データが見つかりません。")

        # --- Tab 4: 地方債・基金分析（全期間変化率ランキング） ---
        with tab_bonds4:
            st.subheader(f"{scope_label} 自治体地方債・基金分析（全期間変化率ランキング）")
            df_pref_bonds = get_comparison_df(df_bonds)
            
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
                
                df_bonds_min = df_pref_bonds[df_pref_bonds['年度'].astype(str) == min_bonds_year][['都道府県', '団体名', selected_bonds_target]].rename(columns={selected_bonds_target: '初期金額'})
                df_bonds_max = df_pref_bonds[df_pref_bonds['年度'].astype(str) == max_bonds_year][['団体名', selected_bonds_target]].rename(columns={selected_bonds_target: '最新金額'})
                
                df_bonds_growth = df_bonds_min.merge(df_bonds_max, on='団体名', how='inner')
                df_bonds_growth = df_bonds_growth[df_bonds_growth['初期金額'] > 0].copy()
                
                df_bonds_growth['増加額'] = df_bonds_growth['最新金額'] - df_bonds_growth['初期金額']
                df_bonds_growth['増加率(%)'] = ((df_bonds_growth['増加額'] / df_bonds_growth['初期金額']) * 100).round(1)
                df_bonds_growth = df_bonds_growth.sort_values('増加率(%)', ascending=False)
                
                bonds_target_name = bonds_analysis_options[selected_bonds_target]
                
                fig_bonds_growth = px.bar(
                    df_bonds_growth, x='団体名', y='増加率(%)', text='増加率(%)',
                    title=f"{scope_label} 自治体 {bonds_target_name} 増加率ランキング（{min_bonds_year}➔{max_bonds_year}年度）",
                    color='増加率(%)', color_continuous_scale='RdBu_r',
                    custom_data=['都道府県']
                )
                fig_bonds_growth.update_traces(
                    texttemplate='%{text:.1f}%', textposition='outside',
                    hovertemplate="都道府県: %{customdata[0]}<br><b>自治体: %{x}</b><br>増加率: %{y:.1f}%<extra></extra>"
                )
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
                st.info("該当する比較対象データが見つかりません。")
    else:
        st.warning("対象自治体の地方債データが存在しません。")