import subprocess
import json
import os
import pandas as pd
import time
import datetime
import csv
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import logging
import sys

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scrape_data.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# 保存先ディレクトリ
OUTPUT_DIR = "data"

# 各種データの保存先サブディレクトリ
STADIUMS_DIR = os.path.join(OUTPUT_DIR, "stadiums")
RACERS_DIR = os.path.join(OUTPUT_DIR, "racers")
ODDS_DIR = os.path.join(OUTPUT_DIR, "odds")
PROGRAMS_DIR = os.path.join(OUTPUT_DIR, "programs")
RESULTS_DIR = os.path.join(OUTPUT_DIR, "results")

# ディレクトリ作成
for directory in [OUTPUT_DIR, STADIUMS_DIR, RACERS_DIR, ODDS_DIR, PROGRAMS_DIR, RESULTS_DIR]:
    os.makedirs(directory, exist_ok=True)

# タイムアウト設定（秒）
TIMEOUT = 60

def get_stadiums(date_str):
    """指定日付のボートレース場情報を取得"""
    try:
        # 開催場情報を取得（PHPスクリプトを実行）
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
            capture_output=True, text=True, timeout=TIMEOUT
        )
        
        # 一時ファイルを削除
        try:
            os.remove('temp_stadium.php')
        except:
            pass
        
        if result.returncode != 0:
            logging.error(f"開催場情報の取得に失敗しました: {result.stderr}")
            return {}
        
        try:
            stadiums = json.loads(result.stdout)
            if not stadiums:
                logging.warning(f"{date_str}の開催場情報が空です")
                return {}
            
            return stadiums
        except json.JSONDecodeError as e:
            logging.error(f"開催場情報の解析に失敗しました: {e}")
            return {}
    except subprocess.TimeoutExpired:
        logging.error(f"開催場情報の取得がタイムアウトしました（{TIMEOUT}秒）")
        return {}
    except Exception as e:
        logging.error(f"開催場情報の取得中にエラー: {e}")
        return {}

def get_race_odds(stadium_number, race_number, date_str):
    """指定したレース場・レース番号のオッズ情報を取得"""
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
            capture_output=True, text=True, timeout=TIMEOUT
        )
        
        # 一時ファイルを削除
        try:
            os.remove('temp_odds.php')
        except:
            pass
        
        if result.returncode != 0:
            logging.error(f"オッズ情報の取得に失敗しました({date_str} {stadium_number} {race_number}): {result.stderr}")
            return None
        
        try:
            odds_data = json.loads(result.stdout)
            return odds_data
        except json.JSONDecodeError as e:
            logging.error(f"オッズデータの解析に失敗しました({date_str} {stadium_number} {race_number}): {e}")
            return None
    except subprocess.TimeoutExpired:
        logging.error(f"オッズデータの取得がタイムアウトしました({date_str} {stadium_number} {race_number})（{TIMEOUT}秒）")
        return None
    except Exception as e:
        logging.error(f"オッズデータの取得中にエラー({date_str} {stadium_number} {race_number}): {e}")
        return None

def get_race_program(stadium_number, race_number, date_str):
    """指定したレース場・レース番号の出走表情報を取得"""
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
            capture_output=True, text=True, timeout=TIMEOUT
        )
        
        # 一時ファイルを削除
        try:
            os.remove('temp_program.php')
        except:
            pass
        
        try:
            program_data = json.loads(result.stdout)
            return program_data
        except json.JSONDecodeError as e:
            logging.error(f"出走表データの解析に失敗しました({date_str} {stadium_number} {race_number}): {e}")
            return None
    except subprocess.TimeoutExpired:
        logging.error(f"出走表データの取得がタイムアウトしました({date_str} {stadium_number} {race_number})（{TIMEOUT}秒）")
        return None
    except Exception as e:
        logging.error(f"出走表データの取得中にエラー({date_str} {stadium_number} {race_number}): {e}")
        return None

def get_race_result(stadium_number, race_number, date_str):
    """指定したレース場・レース番号のレース結果を取得"""
    try:
        # 日付フォーマットを変換
        date_ymd = date_str.replace('-', '')
        
        # レース結果取得用のPHPスクリプトを作成
        result_script = f"""
        <?php
        error_reporting(0);
        ini_set('display_errors', 0);
        
        require 'vendor/autoload.php';
        $scraper = new BVP\\BoatraceScraper\\ScraperCore();
        $result = $scraper->scrapeResults('{date_str}', {stadium_number}, {race_number});
        
        if ($result === null) {{
            $result = $scraper->scrapeResults('{date_ymd}', {stadium_number}, {race_number});
        }}
        
        echo json_encode($result, JSON_UNESCAPED_UNICODE);
        """
        
        # 一時ファイルにPHPスクリプトを書き込み
        with open('temp_result.php', 'w') as f:
            f.write(result_script)
        
        # PHPスクリプトを実行
        result = subprocess.run(
            ["php", "temp_result.php"],
            capture_output=True, text=True, timeout=TIMEOUT
        )
        
        # 一時ファイルを削除
        try:
            os.remove('temp_result.php')
        except:
            pass
        
        if result.returncode != 0:
            logging.error(f"レース結果の取得に失敗しました({date_str} {stadium_number} {race_number}): {result.stderr}")
            return None
        
        try:
            result_data = json.loads(result.stdout)
            return result_data
        except json.JSONDecodeError as e:
            logging.error(f"レース結果の解析に失敗しました({date_str} {stadium_number} {race_number}): {e}")
            return None
    except subprocess.TimeoutExpired:
        logging.error(f"レース結果の取得がタイムアウトしました({date_str} {stadium_number} {race_number})（{TIMEOUT}秒）")
        return None
    except Exception as e:
        logging.error(f"レース結果の取得中にエラー({date_str} {stadium_number} {race_number}): {e}")
        return None

def process_date(date_str):
    """指定日付のデータを全て取得して保存"""
    logging.info(f"=== {date_str}のデータ取得を開始 ===")
    
    # 開催場情報を取得
    stadiums = get_stadiums(date_str)
    if not stadiums:
        logging.warning(f"{date_str}の開催場情報が見つかりませんでした。")
        return
    
    # 開催場情報をCSVに保存
    stadiums_file = os.path.join(STADIUMS_DIR, f"stadiums_{date_str}.csv")
    with open(stadiums_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["stadium_number", "stadium_name", "date"])
        for stadium_number, stadium_name in stadiums.items():
            writer.writerow([stadium_number, stadium_name, date_str])
    
    # 各開催場のレースデータを取得
    for stadium_number, stadium_name in stadiums.items():
        logging.info(f"開催場 {stadium_name}({stadium_number}) のデータ取得開始")
        
        # 各レースのデータを取得
        for race_number in range(1, 13):  # 通常は12レースまで
            # 出走表を取得
            program_data = get_race_program(stadium_number, race_number, date_str)
            if not program_data or stadium_number not in program_data or str(race_number) not in program_data[stadium_number]:
                logging.warning(f"{date_str} {stadium_name}({stadium_number}) R{race_number} の出走表データが見つかりませんでした。")
                continue
            
            # オッズを取得
            odds_data = get_race_odds(stadium_number, race_number, date_str)
            
            # レース結果を取得
            result_data = get_race_result(stadium_number, race_number, date_str)
            
            # 各データをCSVに変換・保存
            save_program_data(program_data, stadium_number, race_number, date_str)
            save_odds_data(odds_data, stadium_number, race_number, date_str)
            save_result_data(result_data, stadium_number, race_number, date_str)
            
            # 少し待機（サーバー負荷軽減）
            time.sleep(1)
        
        logging.info(f"開催場 {stadium_name}({stadium_number}) のデータ取得完了")
    
    logging.info(f"=== {date_str}のデータ取得が完了 ===")

def save_program_data(program_data, stadium_number, race_number, date_str):
    """出走表データをCSVに保存"""
    if not program_data or stadium_number not in program_data or str(race_number) not in program_data[stadium_number]:
        return
    
    race_data = program_data[stadium_number][str(race_number)]
    
    # 出走表を保存
    program_file = os.path.join(PROGRAMS_DIR, f"program_{date_str}_{stadium_number}_{race_number}.csv")
    
    with open(program_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # レース情報のヘッダー行
        writer.writerow([
            "date", "stadium_number", "race_number", "race_title", "race_distance", 
            "race_closed_at", "race_started_at"
        ])
        
        # レース情報
        writer.writerow([
            date_str, stadium_number, race_number,
            race_data.get("race_title", ""),
            race_data.get("race_distance", ""),
            race_data.get("race_closed_at", ""),
            race_data.get("race_started_at", "")
        ])
    
    # 選手情報を保存
    racers_file = os.path.join(RACERS_DIR, f"racers_{date_str}_{stadium_number}_{race_number}.csv")
    
    with open(racers_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # 選手情報のヘッダー行
        writer.writerow([
            "date", "stadium_number", "race_number", "boat_number", "racer_name",
            "racer_number", "racer_weight", "racer_class_code", "motor_number", "boat_number_2",
            "racer_age", "branch_number", "birthplace_number", "racer_flying_count",
            "racer_late_count", "racer_average_start_timing"
        ])
        
        # 各艇の選手情報
        for boat_number, boat_info in race_data.get("boats", {}).items():
            writer.writerow([
                date_str, stadium_number, race_number, boat_number, 
                boat_info.get("racer_name", ""),
                boat_info.get("racer_number", ""),
                boat_info.get("racer_weight", ""),
                boat_info.get("racer_class_code", ""),
                boat_info.get("motor_number", ""),
                boat_info.get("boat_number", ""),
                boat_info.get("racer_age", ""),
                boat_info.get("racer_branch_number", ""),
                boat_info.get("racer_birthplace_number", ""),
                boat_info.get("racer_flying_count", ""),
                boat_info.get("racer_late_count", ""),
                boat_info.get("racer_average_start_timing", "")
            ])

def save_odds_data(odds_data, stadium_number, race_number, date_str):
    """オッズデータをCSVに保存"""
    if not odds_data or str(stadium_number) not in odds_data or str(race_number) not in odds_data[str(stadium_number)]:
        return
    
    race_odds = odds_data[str(stadium_number)][str(race_number)]
    
    # 単勝・複勝オッズを保存
    win_place_file = os.path.join(ODDS_DIR, f"win_place_{date_str}_{stadium_number}_{race_number}.csv")
    
    with open(win_place_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["date", "stadium_number", "race_number", "boat_number", "win_odds", "place_odds_min", "place_odds_max"])
        
        for boat_number in range(1, 7):
            boat_num_str = str(boat_number)
            win_odds = race_odds.get("win_oddses", {}).get(boat_num_str, "")
            place_odds = race_odds.get("place_oddses", {}).get(boat_num_str, "")
            
            place_min = place_max = ""
            if isinstance(place_odds, list) and len(place_odds) == 2:
                place_min = place_odds[0]
                place_max = place_odds[1]
                
            writer.writerow([date_str, stadium_number, race_number, boat_number, win_odds, place_min, place_max])
    
    # 2連単オッズを保存
    exacta_file = os.path.join(ODDS_DIR, f"exacta_{date_str}_{stadium_number}_{race_number}.csv")
    
    with open(exacta_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["date", "stadium_number", "race_number", "first", "second", "odds"])
        
        for first in range(1, 7):
            for second in range(1, 7):
                if first != second:
                    odds = race_odds.get("exacta_oddses", {}).get(str(first), {}).get(str(second), "")
                    writer.writerow([date_str, stadium_number, race_number, first, second, odds])
    
    # 2連複オッズを保存
    quinella_file = os.path.join(ODDS_DIR, f"quinella_{date_str}_{stadium_number}_{race_number}.csv")
    
    with open(quinella_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["date", "stadium_number", "race_number", "first", "second", "odds"])
        
        for first in range(1, 7):
            for second in range(first + 1, 7):
                odds = race_odds.get("quinella_oddses", {}).get(str(first), {}).get(str(second), "")
                writer.writerow([date_str, stadium_number, race_number, first, second, odds])
    
    # 3連単オッズを保存
    trifecta_file = os.path.join(ODDS_DIR, f"trifecta_{date_str}_{stadium_number}_{race_number}.csv")
    
    with open(trifecta_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["date", "stadium_number", "race_number", "first", "second", "third", "odds"])
        
        for first in range(1, 7):
            for second in range(1, 7):
                if first == second:
                    continue
                for third in range(1, 7):
                    if third == first or third == second:
                        continue
                    odds = race_odds.get("trifecta_oddses", {}).get(str(first), {}).get(str(second), {}).get(str(third), "")
                    writer.writerow([date_str, stadium_number, race_number, first, second, third, odds])
    
    # 3連複オッズを保存
    trio_file = os.path.join(ODDS_DIR, f"trio_{date_str}_{stadium_number}_{race_number}.csv")
    
    with open(trio_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["date", "stadium_number", "race_number", "first", "second", "third", "odds"])
        
        for first in range(1, 7):
            for second in range(first + 1, 7):
                for third in range(second + 1, 7):
                    odds = race_odds.get("trio_oddses", {}).get(str(first), {}).get(str(second), {}).get(str(third), "")
                    writer.writerow([date_str, stadium_number, race_number, first, second, third, odds])

def save_result_data(result_data, stadium_number, race_number, date_str):
    """レース結果データをCSVに保存"""
    if not result_data or str(stadium_number) not in result_data or str(race_number) not in result_data[str(stadium_number)]:
        return
    
    race_result = result_data[str(stadium_number)][str(race_number)]
    
    # レース情報と成績を保存
    result_file = os.path.join(RESULTS_DIR, f"result_{date_str}_{stadium_number}_{race_number}.csv")
    
    with open(result_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # レース情報のヘッダー
        writer.writerow([
            "date", "stadium_number", "race_number", "race_weather_number", "race_temperature",
            "race_wind_direction_number", "race_wind", "race_wave", "race_water_temperature",
            "race_technique_number"
        ])
        
        # レース情報
        writer.writerow([
            date_str, stadium_number, race_number,
            race_result.get("race_weather_number", ""),
            race_result.get("race_temperature", ""),
            race_result.get("race_wind_direction_number", ""),
            race_result.get("race_wind", ""),
            race_result.get("race_wave", ""),
            race_result.get("race_water_temperature", ""),
            race_result.get("race_technique_number", "")
        ])
    
    # 選手成績を保存
    racer_results_file = os.path.join(RESULTS_DIR, f"racer_results_{date_str}_{stadium_number}_{race_number}.csv")
    
    with open(racer_results_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # 選手成績のヘッダー
        writer.writerow([
            "date", "stadium_number", "race_number", "boat_number", "racer_name", "racer_number",
            "racer_course_number", "racer_start_timing", "racer_place_number"
        ])
        
        # 選手成績を保存
        for boat_number, boat_info in race_result.get("boats", {}).items():
            writer.writerow([
                date_str, stadium_number, race_number, boat_number,
                boat_info.get("racer_name", ""),
                boat_info.get("racer_number", ""),
                boat_info.get("racer_course_number", ""),
                boat_info.get("racer_start_timing", ""),
                boat_info.get("racer_place_number", "")
            ])
    
    # 払戻情報を保存
    if "payouts" in race_result:
        payouts_file = os.path.join(RESULTS_DIR, f"payouts_{date_str}_{stadium_number}_{race_number}.csv")
        
        with open(payouts_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["date", "stadium_number", "race_number", "bet_type", "combination", "payout"])
            
            payouts = race_result["payouts"]
            
            # 単勝
            if "win" in payouts:
                if isinstance(payouts["win"], list):
                    for win in payouts["win"]:
                        writer.writerow([
                            date_str, stadium_number, race_number, "win",
                            win.get("combination", ""),
                            win.get("payout", "")
                        ])
                elif "win_combination" in payouts:
                    writer.writerow([
                        date_str, stadium_number, race_number, "win",
                        payouts.get("win_combination", ""),
                        payouts.get("win", "")
                    ])
            
            # 複勝
            if "place" in payouts:
                if isinstance(payouts["place"], list):
                    for place in payouts["place"]:
                        writer.writerow([
                            date_str, stadium_number, race_number, "place",
                            place.get("combination", ""),
                            place.get("payout", "")
                        ])
                elif "place_combination" in payouts:
                    writer.writerow([
                        date_str, stadium_number, race_number, "place",
                        payouts.get("place_combination", ""),
                        payouts.get("place", "")
                    ])
            
            # 2連単
            if "exacta" in payouts:
                if isinstance(payouts["exacta"], list):
                    for exacta in payouts["exacta"]:
                        writer.writerow([
                            date_str, stadium_number, race_number, "exacta",
                            exacta.get("combination", ""),
                            exacta.get("payout", "")
                        ])
            
            # 2連複
            if "quinella" in payouts:
                if isinstance(payouts["quinella"], list):
                    for quinella in payouts["quinella"]:
                        writer.writerow([
                            date_str, stadium_number, race_number, "quinella",
                            quinella.get("combination", ""),
                            quinella.get("payout", "")
                        ])
            
            # 3連単
            if "trifecta" in payouts:
                if isinstance(payouts["trifecta"], list):
                    for trifecta in payouts["trifecta"]:
                        writer.writerow([
                            date_str, stadium_number, race_number, "trifecta",
                            trifecta.get("combination", ""),
                            trifecta.get("payout", "")
                        ])
                elif "trifecta_combination" in payouts:
                    writer.writerow([
                        date_str, stadium_number, race_number, "trifecta",
                        payouts.get("trifecta_combination", ""),
                        payouts.get("trifecta", "")
                    ])
            
            # 3連複
            if "trio" in payouts:
                if isinstance(payouts["trio"], list):
                    for trio in payouts["trio"]:
                        writer.writerow([
                            date_str, stadium_number, race_number, "trio",
                            trio.get("combination", ""),
                            trio.get("payout", "")
                        ])

def generate_date_range(start_date, end_date):
    """開始日から終了日までの日付リストを生成"""
    start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
    date_range = []
    
    current = start
    while current <= end:
        date_range.append(current.strftime("%Y-%m-%d"))
        current += datetime.timedelta(days=1)
    
    return date_range

def main():
    """メイン処理"""
    # 開始と終了の日付
    start_date = "2018-01-01"
    end_date = "2024-04-30"  # 2024年の4月まで
    
    # 過去の日付を準備（新しい日付から順に処理）
    date_range = generate_date_range(start_date, end_date)
    date_range.reverse()  # 新しい日付から古い日付へ
    
    logging.info(f"データ取得を開始します。期間: {start_date} から {end_date} まで")
    logging.info(f"合計 {len(date_range)} 日分のデータを取得します")
    
    # 並列処理でデータを取得（日付ごとに処理）
    with ThreadPoolExecutor(max_workers=1) as executor:  # サーバー負荷を考慮して1つずつ処理
        list(tqdm(executor.map(process_date, date_range), total=len(date_range), desc="全体の進捗"))
    
    logging.info("すべてのデータ取得が完了しました！")

if __name__ == "__main__":
    main() 