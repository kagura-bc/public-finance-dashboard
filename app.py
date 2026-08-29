import streamlit as st

# ページ全体の設定（アプリ名とアイコンをアップデート）
st.set_page_config(
    page_title="パブリックファイナンスダッシュボード", 
    page_icon="📊", 
    layout="wide"
)

# 各ページの定義
page_national = st.Page("pages/01_national.py", title="国 (準備中)", icon="🇯🇵")
page_pref = st.Page("pages/02_pref.py", title="都道府県 (準備中)", icon="🏢")
page_city = st.Page("pages/03_city.py", title="市町村", icon="🏘️", default=True) # デフォルト表示

# サイドバーのナビゲーションメニューを作成
pg = st.navigation(
    {"財政分析対象レベル": [page_national, page_pref, page_city]}
)

# 選択されたページを実行
pg.run()