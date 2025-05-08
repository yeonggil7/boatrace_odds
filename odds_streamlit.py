import streamlit as st
import subprocess
import json
import pandas as pd
import datetime
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import concurrent.futures
import time
import os

st.set_page_config(page_title="ボートレースオッズ分析", page_icon="🚤", layout="wide")

# キャッシュ時間（秒）
CACHE_TTL = 300  # 5分間キャッシュ

# タイムアウト設定（秒）
STADIUM_TIMEOUT = 30  # 開催場情報取得のタイムアウト
CHECK_TIMEOUT = 15    # 開催場確認のタイムアウト
ODDS_TIMEOUT = 30     # オッズ情報取得のタイムアウト
PROGRAM_TIMEOUT = 20  # 出走表情報取得のタイムアウト
PREVIEW_TIMEOUT = 20  # 直前情報取得のタイムアウト

@st.cache_data(ttl=CACHE_TTL)
def get_stadiums(selected_date=None):
    """指定日付のボートレース場情報を取得（キャッシュ機能付き）"""
    if selected_date is None:
        selected_date = datetime.date.today()
    
    date_str = selected_date.strftime('%Y-%m-%d')
    try:
        # 開催場情報を取得（PHPスクリプトを別ファイルとして実行）
        php_script = f"""
        <?php
        require 'vendor/autoload.php';
        $scraper = new BVP\\BoatraceScraper\\ScraperCore();
        echo json_encode($scraper->scrapeStadiums('{date_str}'), JSON_UNESCAPED_UNICODE);
        """
        
        # 一時ファイルにPHPスクリプトを書き込み
        with open('temp_stadium.php', 'w') as f:
            f.write(php_script)
        
        # PHPスクリプトを実行
        result = subprocess.run(
            ["php", "temp_stadium.php"],
            capture_output=True, text=True, timeout=STADIUM_TIMEOUT
        )
        
        # 一時ファイルを削除
        try:
            os.remove('temp_stadium.php')
        except:
            pass
        
        if result.returncode != 0:
            st.error(f"開催場情報の取得に失敗しました: {result.stderr}")
            st.error(f"PHPスクリプトの出力: {result.stdout}")
            return {}
            
        try:
            stadiums = json.loads(result.stdout)
            if not stadiums:
                st.warning(f"{date_str}の開催場情報が空です")
                return {}
                
            # 各会場の有効性を順次チェック
            valid_stadiums = {}
            for stadium_number, stadium_name in stadiums.items():
                try:
                    # チェック用のPHPスクリプトを作成
                    check_script = f"""
                    <?php
                    require 'vendor/autoload.php';
                    $scraper = new BVP\\BoatraceScraper\\ScraperCore();
                    echo json_encode($scraper->scrapePrograms('{date_str}', {stadium_number}, 1), JSON_UNESCAPED_UNICODE);
                    """
                    
                    # 一時ファイルにPHPスクリプトを書き込み
                    with open('temp_check.php', 'w') as f:
                        f.write(check_script)
                    
                    # PHPスクリプトを実行
                    check_result = subprocess.run(
                        ["php", "temp_check.php"],
                        capture_output=True, text=True, timeout=CHECK_TIMEOUT
                    )
                    
                    # 一時ファイルを削除
                    try:
                        os.remove('temp_check.php')
                    except:
                        pass
                    
                    if check_result.returncode != 0:
                        st.error(f"開催場 {stadium_name} の確認に失敗: {check_result.stderr}")
                        continue
                        
                    try:
                        program_data = json.loads(check_result.stdout)
                        if not program_data:
                            continue
                            
                        # プログラムデータが存在し、レース情報が取得できれば有効な開催場
                        if stadium_number in program_data and "1" in program_data[stadium_number]:
                            valid_stadiums[stadium_number] = stadium_name
                    except json.JSONDecodeError as e:
                        st.error(f"開催場 {stadium_name} のデータ解析に失敗: {e}")
                        continue
                except subprocess.TimeoutExpired:
                    st.error(f"開催場 {stadium_name} の確認がタイムアウト（{CHECK_TIMEOUT}秒）")
                    continue
                except Exception as e:
                    st.error(f"開催場 {stadium_name} の確認中にエラー: {e}")
                    continue
            
            if not valid_stadiums:
                st.warning(f"{date_str}の開催場が見つかりませんでした。")
                st.info("PHPスクリプトの出力を確認してください。")
            
            return valid_stadiums
            
        except json.JSONDecodeError as e:
            st.error(f"開催場情報の解析に失敗しました: {e}")
            st.error(f"PHPスクリプトの出力: {result.stdout}")
            return {}
            
    except Exception as e:
        st.error(f"開催場情報の取得に失敗しました: {e}")
        return {}

@st.cache_data(ttl=CACHE_TTL)
def get_race_odds(stadium_number, race_number, date_str=None):
    """指定したレース場・レース番号のオッズ情報を取得（キャッシュ付き）"""
    if date_str is None:
        date_str = datetime.date.today().strftime('%Y-%m-%d')
    
    try:
        # オッズ情報取得用のPHPスクリプトを作成
        odds_script = f"""
        <?php
        require 'vendor/autoload.php';
        $scraper = new BVP\\BoatraceScraper\\ScraperCore();
        echo json_encode($scraper->scrapeOddses('{date_str}', {stadium_number}, {race_number}), JSON_UNESCAPED_UNICODE);
        """
        
        # 一時ファイルにPHPスクリプトを書き込み
        with open('temp_odds.php', 'w') as f:
            f.write(odds_script)
        
        # PHPスクリプトを実行
        result = subprocess.run(
            ["php", "temp_odds.php"],
            capture_output=True, text=True, timeout=ODDS_TIMEOUT
        )
        
        # 一時ファイルを削除
        try:
            os.remove('temp_odds.php')
        except:
            pass
        
        if result.returncode != 0:
            st.error(f"PHPスクリプトの実行に失敗しました: {result.stderr}")
            st.error(f"PHPスクリプトの出力: {result.stdout}")
            return None
            
        try:
            odds_data = json.loads(result.stdout)
            if not odds_data:
                st.error("オッズデータが空です")
                return None
                
            if stadium_number not in odds_data:
                st.error(f"開催場 {stadium_number} のデータが見つかりません")
                return None
                
            if str(race_number) not in odds_data[stadium_number]:
                st.error(f"レース {race_number} のデータが見つかりません")
                return None
                
            return odds_data
        except json.JSONDecodeError as e:
            st.error(f"オッズデータの解析に失敗しました: {e}")
            st.error(f"PHPスクリプトの出力: {result.stdout}")
            return None
            
    except subprocess.TimeoutExpired:
        st.error(f"オッズデータの取得がタイムアウトしました（{ODDS_TIMEOUT}秒）")
        return None
    except Exception as e:
        st.error(f"予期せぬエラーが発生しました: {e}")
        return None

@st.cache_data(ttl=CACHE_TTL)
def get_race_program(stadium_number, race_number, date_str=None):
    """指定したレース場・レース番号の出走表情報を取得（キャッシュ付き）"""
    if date_str is None:
        date_str = datetime.date.today().strftime('%Y-%m-%d')
    
    try:
        # 出走表情報取得用のPHPスクリプトを作成
        program_script = f"""
        <?php
        require 'vendor/autoload.php';
        $scraper = new BVP\\BoatraceScraper\\ScraperCore();
        echo json_encode($scraper->scrapePrograms('{date_str}', {stadium_number}, {race_number}), JSON_UNESCAPED_UNICODE);
        """
        
        # 一時ファイルにPHPスクリプトを書き込み
        with open('temp_program.php', 'w') as f:
            f.write(program_script)
        
        # PHPスクリプトを実行
        result = subprocess.run(
            ["php", "temp_program.php"],
            capture_output=True, text=True, timeout=PROGRAM_TIMEOUT
        )
        
        # 一時ファイルを削除
        try:
            os.remove('temp_program.php')
        except:
            pass
        
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        st.error(f"出走表データの取得に失敗しました")
        return None
    except subprocess.TimeoutExpired:
        st.error(f"出走表データの取得がタイムアウトしました（{PROGRAM_TIMEOUT}秒）")
        return None

@st.cache_data(ttl=CACHE_TTL)
def get_race_preview(stadium_number, race_number, date_str=None):
    """指定したレース場・レース番号の直前情報を取得（キャッシュ付き）"""
    if date_str is None:
        date_str = datetime.date.today().strftime('%Y-%m-%d')
    
    try:
        # 直前情報取得用のPHPスクリプトを作成
        preview_script = f"""
        <?php
        require 'vendor/autoload.php';
        $scraper = new BVP\\BoatraceScraper\\ScraperCore();
        echo json_encode($scraper->scrapePreviews('{date_str}', {stadium_number}, {race_number}), JSON_UNESCAPED_UNICODE);
        """
        
        # 一時ファイルにPHPスクリプトを書き込み
        with open('temp_preview.php', 'w') as f:
            f.write(preview_script)
        
        # PHPスクリプトを実行
        result = subprocess.run(
            ["php", "temp_preview.php"],
            capture_output=True, text=True, timeout=PREVIEW_TIMEOUT
        )
        
        # 一時ファイルを削除
        try:
            os.remove('temp_preview.php')
        except:
            pass
        
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        st.error(f"直前情報の取得に失敗しました")
        return None
    except subprocess.TimeoutExpired:
        st.error(f"直前情報の取得がタイムアウトしました（{PREVIEW_TIMEOUT}秒）")
        return None

@st.cache_data(ttl=CACHE_TTL)
def get_race_result(stadium_number, race_number, date_str=None):
    """指定したレース場・レース番号のレース結果を取得（キャッシュ付き）"""
    if date_str is None:
        date_str = datetime.date.today().strftime('%Y-%m-%d')
    
    # 日付形式の変換
    if isinstance(date_str, datetime.date):
        date_str = date_str.strftime('%Y-%m-%d')
    
    # ボートレース結果URL情報（デバッグ用）
    date_ymd = date_str.replace('-', '')
    debug_info = {
        "date": date_str,
        "date_ymd": date_ymd,
        "stadium": stadium_number,
        "race": race_number,
        "url": f"https://www.boatrace.jp/owpc/pc/race/raceresult?rno={race_number}&jcd={stadium_number}&hd={date_ymd}"
    }
    
    try:
        # レース結果取得用のPHPスクリプトを作成
        result_script = f"""
        <?php
        // エラー表示を無効化（JSON解析に影響するため）
        error_reporting(0);
        ini_set('display_errors', 0);
        
        require 'vendor/autoload.php';
        $scraper = new BVP\\BoatraceScraper\\ScraperCore();
        
        // 日付フォーマットを変換
        $date_ymd = str_replace('-', '', '{date_str}');
        
        // 直接実行
        try {{
            echo "DEBUG:試行-{date_str}\\n";
            $result = $scraper->scrapeResults('{date_str}', {stadium_number}, {race_number});
            
            if ($result === null) {{
                echo "DEBUG:試行-{date_str}-失敗\\n";
                echo "DEBUG:試行-$date_ymd\\n";
                $result = $scraper->scrapeResults($date_ymd, {stadium_number}, {race_number});
                
                if ($result === null) {{
                    echo "DEBUG:試行-$date_ymd-失敗\\n";
                    echo "DEBUG:URLチェック-https://www.boatrace.jp/owpc/pc/race/raceresult?rno={race_number}&jcd={stadium_number}&hd=$date_ymd\\n";
                    
                    // 本日のレース結果かどうかを確認
                    $today = date('Y-m-d');
                    $is_today = ('{date_str}' === $today);
                    
                    if ($is_today) {{
                        echo json_encode(['error' => '本日のレース結果はまだ公開されていません。']);
                    }} else {{
                        echo json_encode(['error' => '{date_str}のレース結果は公開されていないか、データが存在しません。']);
                    }}
                    exit(1);
                }} else {{
                    echo "DEBUG:試行-$date_ymd-成功\\n";
                }}
            }} else {{
                echo "DEBUG:試行-{date_str}-成功\\n";
            }}
            
            // データ構造をデバッグ出力
            echo "DEBUG:データ構造-" . gettype($result) . "\\n";
            
            if (is_array($result)) {{
                echo "DEBUG:キー-" . implode(',', array_keys($result)) . "\\n";
                
                if (isset($result['{stadium_number}']) && isset($result['{stadium_number}']['{race_number}'])) {{
                    $race_data = $result['{stadium_number}']['{race_number}'];
                    echo "DEBUG:レースデータキー-" . implode(',', array_keys($race_data)) . "\\n";
                    
                    if (isset($race_data['boats'])) {{
                        echo "DEBUG:ボート数-" . count($race_data['boats']) . "\\n";
                        foreach ($race_data['boats'] as $boat_number => $boat_data) {{
                            echo "DEBUG:ボート$boat_number-" . json_encode($boat_data, JSON_UNESCAPED_UNICODE) . "\\n";
                        }}
                    }}
                    
                    if (isset($race_data['payouts'])) {{
                        echo "DEBUG:払戻情報あり\\n";
                    }} else {{
                        echo "DEBUG:払戻情報なし\\n";
                    }}
                }}
            }}
            
            echo json_encode($result, JSON_UNESCAPED_UNICODE);
        }} catch (Exception $e) {{
            echo "DEBUG:例外発生-" . $e->getMessage() . "\\n";
            echo json_encode(['error' => $e->getMessage()]);
            exit(1);
        }}
        """
        
        # 一時ファイルにPHPスクリプトを書き込み
        with open('temp_result.php', 'w') as f:
            f.write(result_script)
        
        # PHPスクリプトを実行
        result = subprocess.run(
            ["php", "temp_result.php"],
            capture_output=True, text=True, timeout=PROGRAM_TIMEOUT
        )
        
        # 一時ファイルを削除
        try:
            os.remove('temp_result.php')
        except:
            pass
        
        if result.returncode != 0:
            debug_info["error"] = f"レース結果の取得に失敗しました: {result.stderr}"
            debug_info["stdout"] = result.stdout
            return None, debug_info
            
        try:
            # デバッグ情報の抽出
            debug_lines = []
            output = result.stdout
            output_lines = output.split('\n')
            clean_output = []
            
            for line in output_lines:
                if line.startswith('DEBUG:'):
                    debug_lines.append(line)
                else:
                    clean_output.append(line)
            
            # デバッグ情報の保存
            debug_info["debug_lines"] = debug_lines
            
            # JSONデータのみ抽出
            output = '\n'.join(clean_output)
            
            # 最初の { から始まるJSONデータのみを抽出
            json_start = output.find('{')
            if json_start >= 0:
                output = output[json_start:]
            
            # JSONデータのパース
            try:
                result_data = json.loads(output)
                debug_info["parsed"] = "JSONパース成功"
            except json.JSONDecodeError as e:
                debug_info["error"] = f"JSON解析エラー: {e}"
                debug_info["raw_output"] = output
                return None, debug_info
            
            if isinstance(result_data, dict) and 'error' in result_data:
                debug_info["error"] = result_data['error']
                return None, debug_info
            
            # 生のJSONデータを保持
            debug_info["raw_data"] = result_data
            
            # データ構造の変換
            if isinstance(result_data, dict):
                # 新しい構造のデータかチェック
                if str(stadium_number) in result_data and str(race_number) in result_data[str(stadium_number)]:
                    debug_info["data_format"] = "標準フォーマット"
                    race_data = result_data[str(stadium_number)][str(race_number)]
                    
                    # 着順情報の取得
                    boats = race_data.get('boats', {})
                    
                    # 艇番と選手名のデータを整理
                    boat_numbers = {}
                    racer_names = {}
                    start_times = {}
                    place_numbers = {}
                    
                    for boat_number, boat_info in boats.items():
                        boat_numbers[boat_number] = boat_info.get('racer_boat_number')
                        racer_names[boat_number] = boat_info.get('racer_name')
                        start_times[boat_number] = boat_info.get('racer_start_timing')
                        place_numbers[boat_number] = boat_info.get('racer_place_number')
                    
                    # すべての艇番と選手名が「不明」の場合はデータなしと判断
                    all_unknown = True
                    for boat_number in boat_numbers.values():
                        if boat_number and boat_number != '不明':
                            all_unknown = False
                            break
                    
                    if all_unknown:
                        for name in racer_names.values():
                            if name and name != '不明':
                                all_unknown = False
                                break
                    
                    if all_unknown:
                        debug_info["error"] = f"{date_str}のレース結果データが不完全です。"
                        debug_info["boats"] = boats
                        return None, debug_info
                    
                    # 払い戻し情報の整理
                    payoffs = {}
                    if 'payouts' in race_data:
                        payoffs = race_data['payouts']
                        
                        # 単勝
                        if 'win' in payoffs:
                            if isinstance(payoffs['win'], list):
                                for win in payoffs['win']:
                                    payoffs['win'] = win['payout']
                                    payoffs['win_combination'] = win['combination']
                            elif payoffs.get('win') and payoffs.get('win_combination'):
                                payoffs['win'] = payoffs['win']
                                payoffs['win_combination'] = payoffs['win_combination']
                        
                        # 複勝
                        if 'place' in payoffs:
                            if isinstance(payoffs['place'], list):
                                for place in payoffs['place']:
                                    payoffs['place'] = place['payout']
                                    payoffs['place_combination'] = place['combination']
                            elif payoffs.get('place') and payoffs.get('place_combination'):
                                payoffs['place'] = payoffs['place']
                                payoffs['place_combination'] = payoffs['place_combination']
                        
                        # 3連単
                        if 'trifecta' in payoffs:
                            if isinstance(payoffs['trifecta'], list):
                                for trifecta in payoffs['trifecta']:
                                    payoffs['trifecta'] = trifecta['payout']
                                    payoffs['trifecta_combination'] = trifecta['combination']
                            elif isinstance(payoffs['trifecta'], (int, float)) and payoffs.get('trifecta_combination'):
                                payoffs['trifecta'] = payoffs['trifecta']
                                payoffs['trifecta_combination'] = payoffs['trifecta_combination']
                    
                    # 整理したデータを新しい構造に変換
                    processed_data = {
                        'boat_numbers': boat_numbers,
                        'racer_names': racer_names,
                        'start_times': start_times,
                        'place_numbers': place_numbers,
                        'determination': race_data.get('race_technique_number'),
                        'payoffs': payoffs,
                        'boats': boats,  # boats情報を追加
                        'race_data': race_data  # 生のレースデータも追加
                    }
                    
                    debug_info["success"] = True
                    return processed_data, debug_info
                else:
                    # キーが見つからない場合
                    available_keys = list(result_data.keys())
                    debug_info["error"] = f"必要なデータキーが見つかりません。利用可能なキー: {available_keys}"
                    return None, debug_info
            
            debug_info["error"] = "レースデータの構造が不正です"
            debug_info["data_type"] = str(type(result_data))
            return None, debug_info
            
        except json.JSONDecodeError as e:
            debug_info["error"] = f"レース結果の解析に失敗しました: {e}"
            debug_info["raw_output"] = result.stdout
            return None, debug_info
            
    except subprocess.TimeoutExpired:
        debug_info["error"] = f"レース結果の取得がタイムアウトしました（{PROGRAM_TIMEOUT}秒）"
        return None, debug_info
    except Exception as e:
        debug_info["error"] = f"予期せぬエラーが発生しました: {e}"
        debug_info["exception_type"] = str(type(e))
        return None, debug_info

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
        result_data_tuple = get_race_result(stadium_number, race_number, date_str)
        
        # タプルから展開
        if isinstance(result_data_tuple, tuple) and len(result_data_tuple) == 2:
            result_data, debug_info = result_data_tuple
            
            # 生データをresult_dataにマージ
            if debug_info and "raw_data" in debug_info and str(stadium_number) in debug_info["raw_data"]:
                raw_race_data = debug_info["raw_data"]
                # result_dataがNoneでもdebug_infoに情報があれば利用
                if result_data is None:
                    result_data = raw_race_data  # 生データをそのまま使用
        else:
            # 古い形式の場合や戻り値が異常な場合の対応
            result_data = result_data_tuple
            debug_info = {"error": "デバッグ情報が取得できませんでした"}
        
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

if st.sidebar.button("オッズ情報を取得"):
    start_time = time.time()
    with st.spinner("オッズ情報を取得中..."):
        # オッズ情報を取得（日付パラメータを追加）
        odds_data, program_data, preview_data, result_data, debug_info = get_race_data_parallel(stadium_number, race_number, selected_date)
        
        load_time = time.time() - start_time
        st.sidebar.caption(f"データ取得時間: {load_time:.2f}秒")
        
        if odds_data and program_data:
            # データの整形
            odds = odds_data[stadium_number][str(race_number)]
            program = program_data[stadium_number][str(race_number)]
            preview = None
            if preview_data and stadium_number in preview_data and str(race_number) in preview_data[stadium_number]:
                preview = preview_data[stadium_number][str(race_number)]
            
            result = None
            if result_data and stadium_number in result_data and str(race_number) in result_data[stadium_number]:
                result = result_data[stadium_number][str(race_number)]
            
            # レース情報の表示
            st.subheader(f"{stadiums[stadium_number]} 第{race_number}レース")
            if program.get('race_title'):
                st.write(f"**{program['race_title']}**")
            
            # レース結果がある場合は表示
            if result:
                st.success("🏆 レース結果")
                result_cols = st.columns(6)
                for i in range(6):
                    with result_cols[i]:
                        boat_number = result.get('boat_numbers', {}).get(str(i+1), '不明')
                        racer_name = result.get('racer_names', {}).get(str(i+1), '不明')
                        st.metric(f"{i+1}着", f"{boat_number}号艇: {racer_name}")
                
                # 決まり手の表示
                if result.get('determination'):
                    st.info(f"決まり手: {result['determination']}")
                
                # 払い戻し情報の表示
                if result.get('payoffs'):
                    st.subheader("💰 払い戻し")
                    payoff_cols = st.columns(3)
                    with payoff_cols[0]:
                        st.metric("単勝", f"{result['payoffs'].get('win', '不明')}円")
                    with payoff_cols[1]:
                        st.metric("複勝", f"{result['payoffs'].get('place', '不明')}円")
                    with payoff_cols[2]:
                        st.metric("3連単", f"{result['payoffs'].get('trifecta', '不明')}円")
            
            # レース条件の表示
            race_info_cols = st.columns(4)
            with race_info_cols[0]:
                st.metric("距離", f"{program.get('race_distance', '不明')}m")
            with race_info_cols[1]:
                st.metric("締切時刻", program.get('race_closed_at', '不明'))
            with race_info_cols[2]:
                if preview:
                    st.metric("風向き", preview.get('race_wind_direction_number', '不明'))
                    st.metric("風速", f"{preview.get('race_wind', '不明')}m")
            with race_info_cols[3]:
                if preview:
                    st.metric("波高", f"{preview.get('race_wave', '不明')}cm")
                    st.metric("水温", f"{preview.get('race_water_temperature', '不明')}℃")
            
            # 選手情報とオッズをまとめたデータフレームを作成
            race_data = []
            for boat_number in range(1, 7):
                boat_info = program['boats'][str(boat_number)]
                racer_name = boat_info.get('racer_name', '不明')
                racer_number = boat_info.get('racer_number', '不明')
                racer_weight = boat_info.get('racer_weight', '不明')
                racer_class = boat_info.get('racer_class_code', '不明')
                
                win_odds = odds.get('win_oddses', {}).get(str(boat_number), None)
                place_odds = odds.get('place_oddses', {}).get(str(boat_number), None)
                
                # 展示タイムの取得（プレビューデータから）
                exhibition_time = None
                if preview and 'boats' in preview and str(boat_number) in preview['boats']:
                    exhibition_time = preview['boats'][str(boat_number)].get('racer_exhibition_time', None)
                
                # 複勝オッズが範囲で表示される場合の処理
                place_odds_display = place_odds
                if isinstance(place_odds, list) and len(place_odds) == 2:
                    place_odds_display = f"{place_odds[0]}～{place_odds[1]}"
                
                # 選手のモックデータ取得
                racer_stats = get_racer_stats(racer_number)
                
                race_data.append({
                    "艇番": boat_number,
                    "選手名": racer_name,
                    "登録番号": racer_number,
                    "級別": racer_class,
                    "体重": racer_weight,
                    "展示タイム": exhibition_time,
                    "単勝オッズ": win_odds,
                    "複勝オッズ": place_odds_display,
                    "平均ST": racer_stats["平均ST"],
                    "勝率": racer_stats["勝率"],
                    "複勝率": racer_stats["複勝率"],
                    "得意水面": racer_stats["得意水面"],
                    "モーター評価": racer_stats["モーター評価"],
                    "ボート評価": racer_stats["ボート評価"]
                })
            
            race_df = pd.DataFrame(race_data)
            
            # タブ1: レース情報
            with tabs[0]:
                st.subheader("出走表")
                
                # 選手データを表示
                st.dataframe(
                    race_df[["艇番", "選手名", "級別", "体重", "展示タイム", "平均ST", "勝率", "得意水面", "モーター評価", "ボート評価"]], 
                    use_container_width=True
                )
                
                # 展示タイムのグラフ
                if preview:
                    st.subheader("展示タイム比較")
                    exhibition_data = race_df[["艇番", "選手名", "展示タイム"]].copy()
                    exhibition_data = exhibition_data[exhibition_data["展示タイム"].notna()]
                    
                    if not exhibition_data.empty:
                        fig, ax = plt.subplots(figsize=(10, 6))
                        bar_colors = ['blue', 'white', 'red', 'green', 'yellow', 'pink']
                        bars = ax.bar(
                            exhibition_data["艇番"], 
                            exhibition_data["展示タイム"], 
                            color=[bar_colors[int(i)-1] for i in exhibition_data["艇番"]]
                        )
                        
                        for bar in bars:
                            height = bar.get_height()
                            if height:
                                ax.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                                        f'{height:.2f}', ha='center', va='bottom')
                        
                        ax.set_xlabel('艇番')
                        ax.set_ylabel('展示タイム (秒)')
                        ax.set_xticks(exhibition_data["艇番"])
                        st.pyplot(fig)
                    else:
                        st.info("展示タイムデータが取得できていません。")
            
            # タブ2: 単勝・複勝オッズ
            with tabs[1]:
                st.subheader("単勝・複勝オッズ")
                odds_df = race_df[["艇番", "選手名", "単勝オッズ", "複勝オッズ", "展示タイム"]].copy()
                st.dataframe(odds_df, use_container_width=True)
                
                # 単勝オッズの可視化
                st.subheader("単勝オッズ分布")
                fig, ax = plt.subplots(figsize=(10, 6))
                bar_colors = ['blue', 'white', 'red', 'green', 'yellow', 'pink']
                bars = ax.bar(
                    race_df['艇番'], 
                    race_df['単勝オッズ'], 
                    color=[bar_colors[int(i)-1] for i in race_df["艇番"]]
                )
                
                for bar in bars:
                    height = bar.get_height()
                    if height is not None:
                        ax.text(bar.get_x() + bar.get_width()/2., height + 0.1,
                                f'{height:.1f}', ha='center', va='bottom')
                
                ax.set_xlabel('艇番')
                ax.set_ylabel('単勝オッズ')
                ax.set_xticks(race_df['艇番'])
                st.pyplot(fig)
            
            # タブ3: 2連単・2連複オッズ
            with tabs[2]:
                # 2連単オッズの表示
                st.subheader("2連単オッズ（人気順）")
                exacta_data = []
                for first in range(1, 7):
                    for second in range(1, 7):
                        if first != second:
                            exacta_odds = odds.get('exacta_oddses', {}).get(str(first), {}).get(str(second), None)
                            if exacta_odds:
                                first_racer = race_df[race_df["艇番"] == first]["選手名"].values[0]
                                second_racer = race_df[race_df["艇番"] == second]["選手名"].values[0]
                                exacta_data.append({
                                    "1着艇番": first,
                                    "1着選手": first_racer,
                                    "2着艇番": second,
                                    "2着選手": second_racer,
                                    "組合せ": f"{first}-{second}",
                                    "オッズ": exacta_odds
                                })
                
                exacta_df = pd.DataFrame(exacta_data)
                # オッズでソート
                if not exacta_df.empty:
                    exacta_df_sorted = exacta_df.sort_values('オッズ')
                    st.dataframe(exacta_df_sorted, use_container_width=True)
                    
                    # 人気の組み合わせを視覚化
                    st.subheader("2連単 人気組み合わせTop5")
                    top5_exacta = exacta_df_sorted.head(5)
                    fig, ax = plt.subplots(figsize=(10, 6))
                    ax.bar(top5_exacta["組合せ"], top5_exacta["オッズ"], color="skyblue")
                    ax.set_xlabel("組合せ (1着-2着)")
                    ax.set_ylabel("オッズ")
                    for i, (_, row) in enumerate(top5_exacta.iterrows()):
                        ax.text(i, row["オッズ"] + 0.3, f'{row["オッズ"]:.1f}', ha='center')
                    st.pyplot(fig)
                
                # 2連複オッズの表示
                st.subheader("2連複オッズ（人気順）")
                quinella_data = []
                for first in range(1, 7):
                    for second in range(first+1, 7):
                        quinella_odds = odds.get('quinella_oddses', {}).get(str(first), {}).get(str(second), None)
                        if quinella_odds:
                            first_racer = race_df[race_df["艇番"] == first]["選手名"].values[0]
                            second_racer = race_df[race_df["艇番"] == second]["選手名"].values[0]
                            quinella_data.append({
                                "艇番組合せ": f"{first}-{second}",
                                "選手組合せ": f"{first_racer}-{second_racer}",
                                "オッズ": quinella_odds
                            })
                
                quinella_df = pd.DataFrame(quinella_data)
                # オッズでソート
                if not quinella_df.empty:
                    quinella_df_sorted = quinella_df.sort_values('オッズ')
                    st.dataframe(quinella_df_sorted, use_container_width=True)
                
            # タブ4: 3連単・3連複オッズ
            with tabs[3]:
                # 3連単オッズの表示（上位10件）
                st.subheader("3連単オッズ（人気順上位10件）")
                trifecta_data = []
                for first in range(1, 7):
                    for second in range(1, 7):
                        for third in range(1, 7):
                            if first != second and first != third and second != third:
                                trifecta_odds = odds.get('trifecta_oddses', {}).get(str(first), {}).get(str(second), {}).get(str(third), None)
                                if trifecta_odds:
                                    first_racer = race_df[race_df["艇番"] == first]["選手名"].values[0]
                                    second_racer = race_df[race_df["艇番"] == second]["選手名"].values[0]
                                    third_racer = race_df[race_df["艇番"] == third]["選手名"].values[0]
                                    trifecta_data.append({
                                        "1着艇番": first,
                                        "1着選手": first_racer,
                                        "2着艇番": second,
                                        "2着選手": second_racer,
                                        "3着艇番": third,
                                        "3着選手": third_racer,
                                        "組合せ": f"{first}-{second}-{third}",
                                        "オッズ": trifecta_odds
                                    })
                
                trifecta_df = pd.DataFrame(trifecta_data)
                # オッズでソート
                if not trifecta_df.empty:
                    trifecta_df_sorted = trifecta_df.sort_values('オッズ')
                    st.dataframe(trifecta_df_sorted.head(10)[["組合せ", "1着選手", "2着選手", "3着選手", "オッズ"]], use_container_width=True)
                    
                    # 人気の組み合わせを視覚化
                    st.subheader("3連単 人気組み合わせTop5")
                    top5_trifecta = trifecta_df_sorted.head(5)
                    fig, ax = plt.subplots(figsize=(10, 6))
                    ax.bar(top5_trifecta["組合せ"], top5_trifecta["オッズ"], color="skyblue")
                    ax.set_xlabel("組合せ (1着-2着-3着)")
                    ax.set_ylabel("オッズ")
                    ax.tick_params(axis='x', rotation=45)
                    for i, (_, row) in enumerate(top5_trifecta.iterrows()):
                        ax.text(i, row["オッズ"] + 0.5, f'{row["オッズ"]:.1f}', ha='center')
                    st.pyplot(fig)
                
                # 3連複オッズの表示（上位10件）
                st.subheader("3連複オッズ（人気順上位10件）")
                trio_data = []
                for first in range(1, 7):
                    for second in range(first+1, 7):
                        for third in range(second+1, 7):
                            trio_odds = odds.get('trio_oddses', {}).get(str(first), {}).get(str(second), {}).get(str(third), None)
                            if trio_odds:
                                first_racer = race_df[race_df["艇番"] == first]["選手名"].values[0]
                                second_racer = race_df[race_df["艇番"] == second]["選手名"].values[0]
                                third_racer = race_df[race_df["艇番"] == third]["選手名"].values[0]
                                trio_data.append({
                                    "艇番組合せ": f"{first}-{second}-{third}",
                                    "選手組合せ": f"{first_racer},{second_racer},{third_racer}",
                                    "オッズ": trio_odds
                                })
                
                trio_df = pd.DataFrame(trio_data)
                # オッズでソート
                if not trio_df.empty:
                    trio_df_sorted = trio_df.sort_values('オッズ')
                    st.dataframe(trio_df_sorted.head(10), use_container_width=True)
            
            # タブ5: AI予想（モック）
            with tabs[4]:
                st.subheader("AIによる予想 (モックデータ)")
                st.info("このデータはデモのためのモックデータです。実際のAI予想ではありません。")
                
                # モックのAI予想を生成
                ai_predictions = []
                
                # 単勝予想
                st.subheader("単勝勝率予測")
                win_probs = []
                for i, row in race_df.iterrows():
                    # 単勝オッズから確率を計算（モック）
                    if row["単勝オッズ"]:
                        win_prob = 100 / row["単勝オッズ"]
                        # ランダム要素を加える
                        win_prob = min(win_prob * (1 + np.random.uniform(-0.2, 0.2)), 100)
                        win_probs.append({
                            "艇番": row["艇番"],
                            "選手名": row["選手名"],
                            "勝率予測": round(win_prob, 2)
                        })
                
                win_prob_df = pd.DataFrame(win_probs).sort_values("勝率予測", ascending=False)
                st.dataframe(win_prob_df, use_container_width=True)
                
                # 勝率予測のグラフ
                fig, ax = plt.subplots(figsize=(10, 6))
                boat_colors = ['blue', 'white', 'red', 'green', 'yellow', 'pink']
                boats = win_prob_df["艇番"].values
                probs = win_prob_df["勝率予測"].values
                
                ax.bar(
                    boats, 
                    probs, 
                    color=[boat_colors[int(boat)-1] for boat in boats]
                )
                ax.set_xlabel("艇番")
                ax.set_ylabel("勝率予測 (%)")
                ax.set_ylim(0, 100)
                for i, prob in enumerate(probs):
                    ax.text(i, prob + 1, f'{prob:.1f}%', ha='center')
                st.pyplot(fig)
                
                # 3連単予想
                st.subheader("3連単予想（上位5点）")
                
                # ランダムに予想を生成（実際はAIモデルの出力）
                trifecta_predictions = []
                # trifecta_dfからデータを利用
                if not trifecta_df.empty:
                    # 上位20件のデータからランダムに5件を選ぶ
                    selected_rows = trifecta_df_sorted.head(20).sample(5)
                    
                    for _, row in selected_rows.iterrows():
                        # 信頼度をランダムに生成
                        confidence = round(np.random.uniform(60, 95), 1)
                        trifecta_predictions.append({
                            "組合せ": row["組合せ"],
                            "1着": f"{row['1着艇番']}:{row['1着選手']}",
                            "2着": f"{row['2着艇番']}:{row['2着選手']}",
                            "3着": f"{row['3着艇番']}:{row['3着選手']}",
                            "予測信頼度": f"{confidence}%",
                            "オッズ": row["オッズ"]
                        })
                    
                    trifecta_pred_df = pd.DataFrame(trifecta_predictions)
                    st.dataframe(trifecta_pred_df, use_container_width=True)
                else:
                    st.info("3連単予想に必要なデータが取得できていません。")
                
                # 買い目推奨
                st.subheader("🔥 おすすめ買い目")
                
                recommended_cols = st.columns(3)
                with recommended_cols[0]:
                    st.metric("1着軸", f"{win_prob_df.iloc[0]['艇番']}号艇: {win_prob_df.iloc[0]['選手名']}")
                    if len(win_prob_df) > 1:
                        st.metric("2着軸候補", f"{win_prob_df.iloc[1]['艇番']}号艇: {win_prob_df.iloc[1]['選手名']}")
                
                with recommended_cols[1]:
                    st.write("**単勝推奨**")
                    st.success(f"{win_prob_df.iloc[0]['艇番']}号艇")
                    
                    st.write("**2連単推奨**")
                    if not exacta_df.empty:
                        top_exacta = exacta_df_sorted.iloc[0]
                        st.success(f"{top_exacta['組合せ']} ({top_exacta['オッズ']}倍)")
                
                with recommended_cols[2]:
                    st.write("**3連単推奨**")
                    if not trifecta_df.empty:
                        for i in range(min(3, len(trifecta_df_sorted))):
                            top = trifecta_df_sorted.iloc[i]
                            st.success(f"{top['組合せ']} ({top['オッズ']}倍)")
            
            # タブ6: レース結果
            with tabs[5]:
                # ボートレース結果URL
                boatrace_url = f"https://www.boatrace.jp/owpc/pc/race/raceresult?rno={race_number}&jcd={stadium_number}&hd={selected_date.strftime('%Y%m%d')}"
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"試行日付: {selected_date.strftime('%Y-%m-%d')}")
                with col2:
                    if st.button("公式サイトで確認"):
                        st.write(f"[公式サイトでレース結果を確認]({boatrace_url})")
                
                # デバッグ情報の表示
                if debug_info and "debug_lines" in debug_info:
                    with st.expander("デバッグ情報"):
                        st.info('\n'.join(debug_info["debug_lines"]))
                
                # 生データの整形表示
                if result_data is not None:
                    st.subheader("🏆 レース結果詳細")
                    
                    try:
                        if debug_info and "raw_data" in debug_info and str(stadium_number) in debug_info["raw_data"]:
                            race_data = debug_info["raw_data"][str(stadium_number)][str(race_number)]
                            
                            # レース状況の表示
                            race_info_col1, race_info_col2, race_info_col3 = st.columns(3)
                            with race_info_col1:
                                st.metric("天気", race_data.get('race_weather_number', '不明'))
                                st.metric("気温", f"{race_data.get('race_temperature', '不明')}℃")
                            
                            with race_info_col2:
                                st.metric("風向き", race_data.get('race_wind_direction_number', '不明'))
                                st.metric("風速", f"{race_data.get('race_wind', '不明')}m")
                            
                            with race_info_col3:
                                st.metric("波高", f"{race_data.get('race_wave', '不明')}cm")
                                st.metric("水温", f"{race_data.get('race_water_temperature', '不明')}℃")
                            
                            # 着順のデータを作成
                            boats = race_data.get('boats', {})
                            if boats:
                                result_data_list = []
                                for boat_number, boat_info in boats.items():
                                    place_num = boat_info.get('racer_place_number', 99)
                                    # 失格やF等も考慮
                                    if isinstance(place_num, str) and not place_num.isdigit():
                                        place_str = place_num  # F、L等の表示をそのまま使用
                                    else:
                                        place_str = int(place_num) if place_num else 99
                                        
                                    result_data_list.append({
                                        "着順": place_str,
                                        "艇番": int(boat_number),
                                        "選手番号": boat_info.get('racer_number', '不明'),
                                        "選手名": boat_info.get('racer_name', '不明'),
                                        "スタートタイム": f"{boat_info.get('racer_start_timing', '不明')}秒",
                                        "進入コース": boat_info.get('racer_course_number', '不明')
                                    })
                                
                                # 着順でソート（文字列の場合は後ろに）
                                def custom_sort(item):
                                    if isinstance(item["着順"], int):
                                        return (0, item["着順"])
                                    else:
                                        return (1, 99)  # 文字列は後ろに
                                        
                                result_data_list.sort(key=custom_sort)
                                result_df = pd.DataFrame(result_data_list)
                                st.dataframe(result_df, use_container_width=True)
                                
                                # 決まり手の表示
                                technique = race_data.get('race_technique_number', '不明')
                                st.markdown(f"**決まり手:** {technique}")
                                
                                # 払い戻し情報の詳細表示
                                if 'payouts' in race_data:
                                    st.subheader("💰 払い戻し詳細")
                                    payoffs = race_data['payouts']
                                    payoff_data = []
                                    
                                    # 単勝
                                    if 'win' in payoffs:
                                        if isinstance(payoffs['win'], list) and len(payoffs['win']) > 0:
                                            for win in payoffs['win']:
                                                payoff_data.append({
                                                    "種別": "単勝",
                                                    "組合せ": f"{win.get('combination', '不明')}号艇",
                                                    "払い戻し": f"{win.get('payout', '不明')}円"
                                                })
                                        elif isinstance(payoffs['win'], (int, float)) and payoffs.get('win_combination'):
                                            payoff_data.append({
                                                "種別": "単勝",
                                                "組合せ": f"{payoffs.get('win_combination', '不明')}号艇",
                                                "払い戻し": f"{payoffs.get('win', '不明')}円"
                                            })
                                    
                                    # 複勝
                                    if 'place' in payoffs:
                                        if isinstance(payoffs['place'], list) and len(payoffs['place']) > 0:
                                            for place in payoffs['place']:
                                                payoff_data.append({
                                                    "種別": "複勝",
                                                    "組合せ": f"{place.get('combination', '不明')}号艇",
                                                    "払い戻し": f"{place.get('payout', '不明')}円"
                                                })
                                        elif isinstance(payoffs['place'], (int, float)) and payoffs.get('place_combination'):
                                            payoff_data.append({
                                                "種別": "複勝",
                                                "組合せ": f"{payoffs.get('place_combination', '不明')}号艇",
                                                "払い戻し": f"{payoffs.get('place', '不明')}円"
                                            })
                                    
                                    # 複勝（複数艇券）
                                    if 'quinella_place' in payoffs:
                                        if isinstance(payoffs['quinella_place'], list):
                                            for qplace in payoffs['quinella_place']:
                                                payoff_data.append({
                                                    "種別": "2連複（複勝）",
                                                    "組合せ": f"{qplace.get('combination', '不明')}",
                                                    "払い戻し": f"{qplace.get('payout', '不明')}円"
                                                })
                                    
                                    # 2連単
                                    if 'exacta' in payoffs:
                                        if isinstance(payoffs['exacta'], list):
                                            for exacta in payoffs['exacta']:
                                                payoff_data.append({
                                                    "種別": "2連単",
                                                    "組合せ": f"{exacta.get('combination', '不明')}",
                                                    "払い戻し": f"{exacta.get('payout', '不明')}円"
                                                })
                                    
                                    # 2連複
                                    if 'quinella' in payoffs:
                                        if isinstance(payoffs['quinella'], list):
                                            for quinella in payoffs['quinella']:
                                                payoff_data.append({
                                                    "種別": "2連複",
                                                    "組合せ": f"{quinella.get('combination', '不明')}",
                                                    "払い戻し": f"{quinella.get('payout', '不明')}円"
                                                })
                                    
                                    # 3連単
                                    if 'trifecta' in payoffs:
                                        if isinstance(payoffs['trifecta'], list) and len(payoffs['trifecta']) > 0:
                                            for trifecta in payoffs['trifecta']:
                                                payoff_data.append({
                                                    "種別": "3連単",
                                                    "組合せ": f"{trifecta.get('combination', '不明')}",
                                                    "払い戻し": f"{trifecta.get('payout', '不明')}円"
                                                })
                                        elif isinstance(payoffs['trifecta'], (int, float)) and payoffs.get('trifecta_combination'):
                                            payoff_data.append({
                                                "種別": "3連単",
                                                "組合せ": f"{payoffs.get('trifecta_combination', '不明')}",
                                                "払い戻し": f"{payoffs.get('trifecta', '不明')}円"
                                            })
                                    
                                    # 3連複
                                    if 'trio' in payoffs:
                                        if isinstance(payoffs['trio'], list):
                                            for trio in payoffs['trio']:
                                                payoff_data.append({
                                                    "種別": "3連複",
                                                    "組合せ": f"{trio.get('combination', '不明')}",
                                                    "払い戻し": f"{trio.get('payout', '不明')}円"
                                                })
                                    
                                    if payoff_data:
                                        # 表形式で一覧表示
                                        payoff_df = pd.DataFrame(payoff_data)
                                        st.dataframe(payoff_df, use_container_width=True)
                                        
                                        # 払い戻し情報をカテゴリごとに視覚化
                                        payoff_categories = {
                                            "単勝・複勝": ["単勝", "複勝", "2連複（複勝）"],
                                            "2連勝式": ["2連単", "2連複"],
                                            "3連勝式": ["3連単", "3連複"]
                                        }
                                        
                                        st.subheader("💰 払い戻し詳細（カテゴリ別）")
                                        tabs_payoff = st.tabs(list(payoff_categories.keys()))
                                        
                                        for i, (category, types) in enumerate(payoff_categories.items()):
                                            with tabs_payoff[i]:
                                                filtered_data = payoff_df[payoff_df["種別"].isin(types)]
                                                if not filtered_data.empty:
                                                    st.dataframe(filtered_data, use_container_width=True)
                                                    
                                                    # 重要な払い戻し情報を強調表示
                                                    if category == "単勝・複勝":
                                                        for _, row in filtered_data.iterrows():
                                                            if row["種別"] == "単勝":
                                                                st.metric("単勝的中", f"{row['組合せ']} ({row['払い戻し']})")
                                                    
                                                    elif category == "3連勝式":
                                                        trifecta_rows = filtered_data[filtered_data["種別"] == "3連単"]
                                                        if not trifecta_rows.empty:
                                                            row = trifecta_rows.iloc[0]
                                                            st.metric("3連単的中", f"{row['組合せ']} ({row['払い戻し']})")
                                                else:
                                                    st.info(f"{category}の払い戻し情報はありません。")
                                    else:
                                        st.info("払い戻し情報はありません。")
                            else:
                                st.warning("着順データがありません。")
                        else:
                            st.warning("レース結果データが正しく整形できませんでした。")
                    except Exception as e:
                        st.error(f"レース結果の表示中にエラーが発生しました: {e}")
                        st.exception(e)
                else:
                    if debug_info and "error" in debug_info:
                        st.warning(debug_info["error"])
                    else:
                        st.info(f"{selected_date.strftime('%Y年%m月%d日')}のレース結果は公開されていません。")
                    
                    # 直接URLで確認
                    st.markdown(f"[ボートレース公式サイトで確認する]({boatrace_url})")
                    
                    # データ取得失敗時のデモ機能
                    if st.button("デモデータを表示"):
                        st.write("※これはサンプルデータです。実際のレース結果ではありません。")
                        
                        # デモ用の着順データ作成
                        mock_result_data = [
                            {"着順": 1, "艇番": 3, "選手名": "競艇太郎", "スタート": "0.12秒", "決まり手": "逃げ"},
                            {"着順": 2, "艇番": 1, "選手名": "ボート次郎", "スタート": "0.15秒", "決まり手": "差し"},
                            {"着順": 3, "艇番": 5, "選手名": "レース三郎", "スタート": "0.18秒", "決まり手": "まくり"},
                            {"着順": 4, "艇番": 2, "選手名": "水上四郎", "スタート": "0.14秒", "決まり手": "まくり差し"},
                            {"着順": 5, "艇番": 6, "選手名": "競走五郎", "スタート": "0.22秒", "決まり手": "抜き"},
                            {"着順": 6, "艇番": 4, "選手名": "選手六郎", "スタート": "0.19秒", "決まり手": "まくられ"}
                        ]
                        
                        # 着順データを表示
                        mock_df = pd.DataFrame(mock_result_data)
                        st.dataframe(mock_df, use_container_width=True)
                        
                        # デモ用の払い戻しデータ作成
                        mock_payoff_data = [
                            {"種別": "単勝", "組合せ": "3号艇", "払い戻し": "450円"},
                            {"種別": "複勝", "組合せ": "3号艇", "払い戻し": "230円"},
                            {"種別": "複勝", "組合せ": "1号艇", "払い戻し": "190円"},
                            {"種別": "2連単", "組合せ": "3-1", "払い戻し": "1,890円"},
                            {"種別": "2連複", "組合せ": "1=3", "払い戻し": "670円"},
                            {"種別": "3連単", "組合せ": "3-1-5", "払い戻し": "5,230円"},
                            {"種別": "3連複", "組合せ": "1=3=5", "払い戻し": "1,240円"}
                        ]
                        
                        # 払い戻しデータを表示
                        st.subheader("💰 払い戻し詳細（サンプル）")
                        mock_payoff_df = pd.DataFrame(mock_payoff_data)
                        st.dataframe(mock_payoff_df, use_container_width=True)
        else:
            st.error("オッズデータの取得に失敗しました。")
else:
    st.info("オッズ情報を取得するには、サイドバーの「オッズ情報を取得」ボタンをクリックしてください。")

# 最後の更新時刻と情報
st.sidebar.write("---")
st.sidebar.write(f"最終更新: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
st.sidebar.caption(f"データキャッシュ時間: {CACHE_TTL}秒") 