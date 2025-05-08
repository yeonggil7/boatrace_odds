import subprocess
import json
import os
import pandas as pd
import time
import datetime
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import logging
import sys
import random
import argparse

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("fast_scrape.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# 保存先ディレクトリ
OUTPUT_DIR = "fast_data"

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
TIMEOUT = 30

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
        temp_file = f'temp_stadium_{random.randint(1000, 9999)}.php'
        with open(temp_file, 'w') as f:
            f.write(php_script)
        
        # PHPスクリプトを実行
        result = subprocess.run(
            ["php", temp_file],
            capture_output=True, text=True, timeout=TIMEOUT
        )
        
        # 一時ファイルを削除
        try:
            os.remove(temp_file)
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

def get_race_data(date_str, stadium_number, race_number):
    """指定したレース場・レース番号の全データを並列で取得"""
    try:
        results = {}
        
        # PHPスクリプトを並列実行するための関数
        def run_php_script(script_type, script_content):
            temp_file = f'temp_{script_type}_{random.randint(1000, 9999)}.php'
            try:
                with open(temp_file, 'w') as f:
                    f.write(script_content)
                
                result = subprocess.run(
                    ["php", temp_file],
                    capture_output=True, text=True, timeout=TIMEOUT
                )
                
                try:
                    os.remove(temp_file)
                except:
                    pass
                
                if result.returncode != 0:
                    logging.error(f"{script_type}の取得に失敗しました: {result.stderr}")
                    return None
                
                try:
                    return json.loads(result.stdout)
                except json.JSONDecodeError as e:
                    logging.error(f"{script_type}の解析に失敗しました: {e}")
                    return None
            except Exception as e:
                logging.error(f"{script_type}の実行中にエラー: {e}")
                try:
                    os.remove(temp_file)
                except:
                    pass
                return None
        
        # 出走表スクリプト
        program_script = f"""
        <?php
        require 'vendor/autoload.php';
        $scraper = new BVP\\BoatraceScraper\\ScraperCore();
        echo json_encode($scraper->scrapePrograms('{date_str}', {stadium_number}, {race_number}), JSON_UNESCAPED_UNICODE);
        """
        
        # オッズスクリプト
        odds_script = f"""
        <?php
        require 'vendor/autoload.php';
        $scraper = new BVP\\BoatraceScraper\\ScraperCore();
        echo json_encode($scraper->scrapeOddses('{date_str}', {stadium_number}, {race_number}), JSON_UNESCAPED_UNICODE);
        """
        
        # レース結果スクリプト
        result_script = f"""
        <?php
        error_reporting(0);
        ini_set('display_errors', 0);
        
        require 'vendor/autoload.php';
        $scraper = new BVP\\BoatraceScraper\\ScraperCore();
        $date_ymd = str_replace('-', '', '{date_str}');
        $result = $scraper->scrapeResults('{date_str}', {stadium_number}, {race_number});
        
        if ($result === null) {{
            $result = $scraper->scrapeResults($date_ymd, {stadium_number}, {race_number});
        }}
        
        echo json_encode($result, JSON_UNESCAPED_UNICODE);
        """
        
        # 並列実行
        with ThreadPoolExecutor(max_workers=3) as executor:
            # 各スクリプトを同時に実行
            future_program = executor.submit(run_php_script, "program", program_script)
            future_odds = executor.submit(run_php_script, "odds", odds_script)
            future_result = executor.submit(run_php_script, "result", result_script)
            
            # 結果を取得
            program_data = future_program.result()
            odds_data = future_odds.result()
            result_data = future_result.result()
        
        # データが存在するかチェック
        if program_data and str(stadium_number) in program_data and str(race_number) in program_data[str(stadium_number)]:
            save_program_data(program_data, stadium_number, race_number, date_str)
            results["program"] = True
        else:
            results["program"] = False
        
        if odds_data and str(stadium_number) in odds_data and str(race_number) in odds_data[str(stadium_number)]:
            save_odds_data(odds_data, stadium_number, race_number, date_str)
            results["odds"] = True
        else:
            results["odds"] = False
        
        if result_data and str(stadium_number) in result_data and str(race_number) in result_data[str(stadium_number)]:
            save_result_data(result_data, stadium_number, race_number, date_str)
            results["result"] = True
        else:
            results["result"] = False
        
        return results
        
    except Exception as e:
        logging.error(f"レースデータの取得中にエラー({date_str} {stadium_number} {race_number}): {e}")
        return {"program": False, "odds": False, "result": False}

def save_program_data(program_data, stadium_number, race_number, date_str):
    """出走表データをCSVに保存"""
    if not program_data or str(stadium_number) not in program_data or str(race_number) not in program_data[str(stadium_number)]:
        return
    
    race_data = program_data[str(stadium_number)][str(race_number)]
    
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
            "racer_number", "racer_weight", "racer_class_code", "motor_number", "boat_number_2"
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
                boat_info.get("boat_number", "")
            ])

def save_odds_data(odds_data, stadium_number, race_number, date_str):
    """オッズデータをCSVに保存（単勝・複勝のみ）"""
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

def save_result_data(result_data, stadium_number, race_number, date_str):
    """レース結果データをCSVに保存（基本情報のみ）"""
    if not result_data or str(stadium_number) not in result_data or str(race_number) not in result_data[str(stadium_number)]:
        return
    
    race_result = result_data[str(stadium_number)][str(race_number)]
    
    # 選手成績を保存
    racer_results_file = os.path.join(RESULTS_DIR, f"racer_results_{date_str}_{stadium_number}_{race_number}.csv")
    
    with open(racer_results_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # 選手成績のヘッダー
        writer.writerow([
            "date", "stadium_number", "race_number", "boat_number", "racer_name", 
            "racer_course_number", "racer_start_timing", "racer_place_number"
        ])
        
        # 選手成績を保存
        for boat_number, boat_info in race_result.get("boats", {}).items():
            writer.writerow([
                date_str, stadium_number, race_number, boat_number,
                boat_info.get("racer_name", ""),
                boat_info.get("racer_course_number", ""),
                boat_info.get("racer_start_timing", ""),
                boat_info.get("racer_place_number", "")
            ])

def process_stadium_races(date_str, stadium_number, stadium_name):
    """指定した開催場の全レースを並列処理"""
    logging.info(f"開催場 {stadium_name}({stadium_number}) のデータ取得開始")
    
    # 各レースを並列処理
    race_tasks = []
    for race_number in range(1, 13):  # 通常は12レースまで
        race_tasks.append((date_str, stadium_number, race_number))
    
    # 進捗バー付きで並列処理
    results = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_race = {executor.submit(get_race_data, date, stadium, race): (date, stadium, race) 
                          for date, stadium, race in race_tasks}
        
        for future in tqdm(as_completed(future_to_race), 
                           total=len(race_tasks), 
                           desc=f"{date_str} {stadium_name}({stadium_number})"):
            date, stadium, race = future_to_race[future]
            try:
                result = future.result()
                results[(date, stadium, race)] = result
            except Exception as e:
                logging.error(f"レース取得中にエラー({date} {stadium} {race}): {e}")
                results[(date, stadium, race)] = {"program": False, "odds": False, "result": False}
    
    # 成功したレース数をカウント
    success_count = sum(1 for res in results.values() if res.get("program", False))
    
    logging.info(f"開催場 {stadium_name}({stadium_number}) の処理完了 - 成功レース数: {success_count}/12")
    return success_count

def process_date_parallel(date_str):
    """指定日付のデータを並列で取得"""
    logging.info(f"=== {date_str}のデータ取得を開始 ===")
    
    # 開催場情報を取得
    stadiums = get_stadiums(date_str)
    if not stadiums:
        logging.warning(f"{date_str}の開催場情報が見つかりませんでした。")
        return 0
    
    # 開催場情報をCSVに保存
    stadiums_file = os.path.join(STADIUMS_DIR, f"stadiums_{date_str}.csv")
    with open(stadiums_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["stadium_number", "stadium_name", "date"])
        for stadium_number, stadium_name in stadiums.items():
            writer.writerow([stadium_number, stadium_name, date_str])
    
    # 各開催場を並列処理
    stadium_tasks = []
    for stadium_number, stadium_name in stadiums.items():
        stadium_tasks.append((date_str, stadium_number, stadium_name))
    
    # 進捗バー付きで並列処理
    total_success = 0
    with ThreadPoolExecutor(max_workers=len(stadium_tasks)) as executor:
        future_to_stadium = {executor.submit(process_stadium_races, date, stadium, name): (date, stadium, name) 
                             for date, stadium, name in stadium_tasks}
        
        for future in as_completed(future_to_stadium):
            date, stadium, name = future_to_stadium[future]
            try:
                success_count = future.result()
                total_success += success_count
            except Exception as e:
                logging.error(f"開催場処理中にエラー({date} {stadium} {name}): {e}")
    
    logging.info(f"=== {date_str}のデータ取得が完了 - 成功レース数: {total_success} ===")
    return total_success

def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(description='ボートレースデータ高速スクレイピング')
    parser.add_argument('--start', type=str, help='開始日 (YYYY-MM-DD形式)', default='2024-03-01')
    parser.add_argument('--end', type=str, help='終了日 (YYYY-MM-DD形式)', default='2024-04-30')
    parser.add_argument('--workers', type=int, help='並列処理数', default=4)
    
    args = parser.parse_args()
    
    # 開始と終了の日付
    start_date = args.start
    end_date = args.end
    max_workers = args.workers
    
    # 日付リストを生成
    start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
    date_range = []
    
    current = start
    while current <= end:
        date_range.append(current.strftime("%Y-%m-%d"))
        current += datetime.timedelta(days=1)
    
    logging.info(f"高速スクレイピングを開始します。期間: {start_date} から {end_date}")
    logging.info(f"合計 {len(date_range)} 日分のデータを取得します")
    logging.info(f"並列処理数: {max_workers}")
    
    # 開始時間を記録
    start_time = time.time()
    
    # 日付ごとに並列処理
    total_races = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_date = {executor.submit(process_date_parallel, date): date for date in date_range}
        
        for future in tqdm(as_completed(future_to_date), total=len(date_range), desc="全体の進捗"):
            date = future_to_date[future]
            try:
                success_count = future.result()
                total_races += success_count
            except Exception as e:
                logging.error(f"日付処理中にエラー({date}): {e}")
    
    # 終了時間と処理時間を計算
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    # 結果を表示
    logging.info(f"スクレイピングが完了しました！")
    logging.info(f"処理時間: {elapsed_time:.2f}秒 ({elapsed_time/60:.2f}分)")
    logging.info(f"処理日数: {len(date_range)}日")
    logging.info(f"取得レース数: {total_races}レース")
    if total_races > 0:
        logging.info(f"1レースあたりの平均処理時間: {elapsed_time/total_races:.2f}秒")
    
if __name__ == "__main__":
    main() 