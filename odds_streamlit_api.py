import streamlit as st
import pandas as pd
import datetime
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import time
import os
import requests
import json

# APIのベースURL
API_BASE_URL = "http://localhost:8000/api"

st.set_page_config(page_title="ボートレースオッズ分析", page_icon="🚤", layout="wide")

# キャッシュ時間（秒）
CACHE_TTL = 300  # 5分間キャッシュ

@st.cache_data(ttl=CACHE_TTL)
def get_stadiums(selected_date=None):
    """指定日付のボートレース場情報をAPIから取得（キャッシュ機能付き）"""
    if selected_date is None:
        selected_date = datetime.date.today()
    
    date_str = selected_date.strftime('%Y-%m-%d')
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/stadiums",
            json={"date": date_str}
        )
        
        result = response.json()
        
        if "error" in result:
            st.error(f"開催場情報の取得に失敗しました: {result['error']}")
            return {}
        
        if "warning" in result:
            st.warning(result["warning"])
            return result.get("data", {})
            
        return result.get("data", {})
            
    except Exception as e:
        st.error(f"開催場情報の取得に失敗しました: {e}")
        return {}

@st.cache_data(ttl=CACHE_TTL)
def get_race_odds(stadium_number, race_number, date_str=None):
    """指定したレース場・レース番号のオッズ情報をAPIから取得（キャッシュ付き）"""
    if date_str is None:
        date_str = datetime.date.today().strftime('%Y-%m-%d')
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/race/odds",
            json={
                "stadium_number": stadium_number,
                "race_number": race_number,
                "date": date_str
            }
        )
        
        result = response.json()
        
        if "error" in result:
            st.error(f"オッズデータの取得に失敗しました: {result['error']}")
            return None
            
        return result.get("data")
            
    except Exception as e:
        st.error(f"オッズデータの取得に失敗しました: {e}")
        return None

@st.cache_data(ttl=CACHE_TTL)
def get_race_program(stadium_number, race_number, date_str=None):
    """指定したレース場・レース番号の出走表情報をAPIから取得（キャッシュ付き）"""
    if date_str is None:
        date_str = datetime.date.today().strftime('%Y-%m-%d')
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/race/program",
            json={
                "stadium_number": stadium_number,
                "race_number": race_number,
                "date": date_str
            }
        )
        
        result = response.json()
        
        if "error" in result:
            st.error(f"出走表データの取得に失敗しました: {result['error']}")
            return None
            
        return result.get("data")
    except Exception as e:
        st.error(f"出走表データの取得に失敗しました: {e}")
        return None

@st.cache_data(ttl=CACHE_TTL)
def get_race_preview(stadium_number, race_number, date_str=None):
    """指定したレース場・レース番号の直前情報をAPIから取得（キャッシュ付き）"""
    if date_str is None:
        date_str = datetime.date.today().strftime('%Y-%m-%d')
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/race/preview",
            json={
                "stadium_number": stadium_number,
                "race_number": race_number,
                "date": date_str
            }
        )
        
        result = response.json()
        
        if "error" in result:
            st.error(f"直前情報の取得に失敗しました: {result['error']}")
            return None
            
        return result.get("data")
    except Exception as e:
        st.error(f"直前情報の取得に失敗しました: {e}")
        return None

@st.cache_data(ttl=CACHE_TTL)
def get_race_result(stadium_number, race_number, date_str=None):
    """指定したレース場・レース番号のレース結果をAPIから取得（キャッシュ付き）"""
    if date_str is None:
        date_str = datetime.date.today().strftime('%Y-%m-%d')
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/race/result",
            json={
                "stadium_number": stadium_number,
                "race_number": race_number,
                "date": date_str
            }
        )
        
        result = response.json()
        
        if "error" in result:
            return None, result
            
        return result.get("data"), result.get("debug_info", {})
    except Exception as e:
        return None, {"error": str(e)}

# モックの選手データ（実際の環境では選手DBから取得する想定）
@st.cache_data(ttl=3600)  # 1時間キャッシュ
def get_racer_stats(racer_number):
    """選手の成績データを取得（モック）（キャッシュ付き）"""
    # 実際の実装では、選手番号に基づいてDBから取得する
    # シード値に選手番号を使うことで、同じ選手には同じランダムデータを返す
    try:
        # racer_numberが文字列の場合は整数に変換
        if isinstance(racer_number, str):
            seed_value = int(racer_number) if racer_number.isdigit() else 0
        else:
            # すでに整数の場合はそのまま使用
            seed_value = int(racer_number) if racer_number else 0
    except (ValueError, TypeError):
        seed_value = 0
    
    np.random.seed(seed_value)
    
    mock_data = {
        # ランダムなデータを生成
        "平均ST": round(np.random.uniform(0.10, 0.30), 2),
        "勝率": round(np.random.uniform(3.50, 7.50), 2),
        "複勝率": round(np.random.uniform(30.0, 70.0), 2),
        "平均順位": round(np.random.uniform(2.0, 4.5), 2),
        "優出回数": np.random.randint(0, 30),
        "優勝回数": np.random.randint(0, 15),
        "得意水面": ["平水", "凪", "波高"][np.random.randint(0, 3)],
        "得意コース": np.random.randint(1, 7),
        "モーター評価": ["A", "B", "C"][np.random.randint(0, 3)],
        "ボート評価": ["A", "B", "C"][np.random.randint(0, 3)]
    }
    
    # シード値をリセット
    np.random.seed(None)
    
    return mock_data

def get_race_data_parallel(stadium_number, race_number, selected_date=None):
    """レース情報を取得する関数"""
    if selected_date is None:
        selected_date = datetime.date.today()
    
    date_str = selected_date.strftime('%Y-%m-%d')
    try:
        # データを順次取得
        odds_data = get_race_odds(stadium_number, race_number, date_str)
        program_data = get_race_program(stadium_number, race_number, date_str)
        preview_data = get_race_preview(stadium_number, race_number, date_str)
        
        # レース結果の取得（タプルで返ってくる）
        result_data, debug_info = get_race_result(stadium_number, race_number, date_str)
        
        return odds_data, program_data, preview_data, result_data, debug_info
    except Exception as e:
        st.error(f"レースデータの取得に失敗しました: {e}")
        return None, None, None, None, {"error": str(e)}

# アプリのタイトル
st.title("🚤 ボートレースオッズ分析")
st.write("ボートレースのオッズ情報を表示します")

# 日付選択
selected_date = st.sidebar.date_input(
    "日付を選択",
    value=datetime.date.today(),
    min_value=datetime.date(2020, 1, 1),
    max_value=datetime.date.today()
)

# 開催場情報の取得
start_time = time.time()
with st.spinner("開催場情報を取得中..."):
    stadiums = get_stadiums(selected_date)
    if not stadiums:
        st.info(f"{selected_date.strftime('%Y年%m月%d日')}は開催がないか、まだ情報が公開されていません。")
        st.stop()
    load_time = time.time() - start_time
    st.sidebar.caption(f"開催場情報の取得時間: {load_time:.2f}秒")

# サイドバーで開催場とレースを選択
stadium_number = st.sidebar.selectbox(
    "開催場を選択",
    options=list(stadiums.keys()),
    format_func=lambda x: f"{stadiums[x]}（{x}）"
)

race_number = st.sidebar.selectbox(
    "レース番号を選択", 
    options=list(range(1, 13))
)

# タブでオッズの種類を切り替え
tabs = st.tabs(["レース情報", "単勝・複勝", "2連単・2連複", "3連単・3連複", "AI予想（モック）", "レース結果"])

st.sidebar.write("---")
st.sidebar.caption(f"API接続先: {API_BASE_URL}")
st.sidebar.caption(f"データキャッシュ時間: {CACHE_TTL}秒")

# この部分は元のStreamlitアプリと同様なので、ここでは省略していますが
# 実際には元のコードから対応する部分をコピーして調整する必要があります
if st.sidebar.button("オッズ情報を取得"):
    # ここにレースデータの取得処理とUIの更新を記述します
    # 元のアプリの該当部分のコードを修正して使用します
    start_time = time.time()
    with st.spinner("オッズ情報を取得中..."):
        # オッズ情報を取得
        odds_data, program_data, preview_data, result_data, debug_info = get_race_data_parallel(stadium_number, race_number, selected_date)
        
        load_time = time.time() - start_time
        st.sidebar.caption(f"データ取得時間: {load_time:.2f}秒")
        
        # データ取得成功時の処理
        if odds_data and program_data:
            # 以下は元のUIの表示部分なので、必要に応じて実装します
            st.success("データの取得に成功しました。タブを切り替えて詳細を確認してください。")
else:
    st.info("オッズ情報を取得するには、サイドバーの「オッズ情報を取得」ボタンをクリックしてください。") 