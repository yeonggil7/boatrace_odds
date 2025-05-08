import subprocess
import json
import os
import time
import datetime
import logging
import sys
import random

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("quick_test.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

# タイムアウト設定（秒）
TIMEOUT = 15

def run_php_script(script_content):
    """PHPスクリプトを実行して結果を取得"""
    # ランダムな一時ファイル名を生成
    temp_file = f'temp_script_{random.randint(1000, 9999)}.php'
    
    try:
        # 一時ファイルにPHPスクリプトを書き込み
        with open(temp_file, 'w') as f:
            f.write(script_content)
        
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
            logging.error(f"PHPスクリプト実行エラー: {result.stderr}")
            return None
        
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            logging.error(f"JSON解析エラー: {e}")
            logging.error(f"出力: {result.stdout[:500]}")  # 最初の500文字だけ表示
            return None
    except Exception as e:
        logging.error(f"スクリプト実行中にエラー: {e}")
        try:
            os.remove(temp_file)
        except:
            pass
        return None

def get_and_print_one_race():
    """1つのレースデータを取得して表示（テスト用）"""
    # 取得する日付、開催場、レース番号を指定
    date_str = "2024-05-06"  # 今日の日付や過去の確実に開催があった日付を指定
    stadium_number = 1  # 桐生競艇場
    race_number = 1     # 第1レース
    
    logging.info(f"{date_str} 開催場{stadium_number} 第{race_number}レースのデータを取得します")
    
    # 1. 出走表を取得
    program_script = f"""
    <?php
    require 'vendor/autoload.php';
    $scraper = new BVP\\BoatraceScraper\\ScraperCore();
    echo json_encode($scraper->scrapePrograms('{date_str}', {stadium_number}, {race_number}), JSON_UNESCAPED_UNICODE);
    """
    
    start_time = time.time()
    program_data = run_php_script(program_script)
    program_time = time.time() - start_time
    
    if program_data:
        logging.info(f"出走表データ取得成功（{program_time:.2f}秒）")
        
        if str(stadium_number) in program_data and str(race_number) in program_data[str(stadium_number)]:
            race_info = program_data[str(stadium_number)][str(race_number)]
            print(f"\n=== レース情報 ===")
            print(f"レース名: {race_info.get('race_title', '不明')}")
            print(f"距離: {race_info.get('race_distance', '不明')}m")
            print(f"締切時刻: {race_info.get('race_closed_at', '不明')}")
            
            if 'boats' in race_info:
                print("\n=== 出走選手 ===")
                for boat_number, boat_info in race_info['boats'].items():
                    print(f"{boat_number}号艇: {boat_info.get('racer_name', '不明')} ({boat_info.get('racer_number', '不明')})")
        else:
            logging.warning("レース情報が見つかりません")
    else:
        logging.error("出走表データの取得に失敗しました")
    
    # 2. オッズを取得
    odds_script = f"""
    <?php
    require 'vendor/autoload.php';
    $scraper = new BVP\\BoatraceScraper\\ScraperCore();
    echo json_encode($scraper->scrapeOddses('{date_str}', {stadium_number}, {race_number}), JSON_UNESCAPED_UNICODE);
    """
    
    start_time = time.time()
    odds_data = run_php_script(odds_script)
    odds_time = time.time() - start_time
    
    if odds_data:
        logging.info(f"オッズデータ取得成功（{odds_time:.2f}秒）")
        
        if str(stadium_number) in odds_data and str(race_number) in odds_data[str(stadium_number)]:
            race_odds = odds_data[str(stadium_number)][str(race_number)]
            
            if 'win_oddses' in race_odds:
                print("\n=== 単勝オッズ ===")
                for boat_number, win_odds in race_odds['win_oddses'].items():
                    print(f"{boat_number}号艇: {win_odds}")
        else:
            logging.warning("オッズ情報が見つかりません")
    else:
        logging.error("オッズデータの取得に失敗しました")
    
    # 3. レース結果を取得
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
    
    start_time = time.time()
    result_data = run_php_script(result_script)
    result_time = time.time() - start_time
    
    if result_data:
        logging.info(f"結果データ取得成功（{result_time:.2f}秒）")
        
        if str(stadium_number) in result_data and str(race_number) in result_data[str(stadium_number)]:
            race_result = result_data[str(stadium_number)][str(race_number)]
            
            print("\n=== 着順 ===")
            if 'boats' in race_result:
                # 着順情報を整理
                place_info = []
                for boat_number, boat_info in race_result['boats'].items():
                    place_number = boat_info.get('racer_place_number', '不明')
                    racer_name = boat_info.get('racer_name', '不明')
                    start_timing = boat_info.get('racer_start_timing', '不明')
                    
                    place_info.append({
                        'place': place_number,
                        'boat': boat_number,
                        'name': racer_name,
                        'start': start_timing
                    })
                
                # 着順でソート
                try:
                    place_info.sort(key=lambda x: int(x['place']) if isinstance(x['place'], (int, str)) and str(x['place']).isdigit() else 99)
                except:
                    pass
                
                for info in place_info:
                    print(f"{info['place']}着: {info['boat']}号艇 {info['name']} (ST: {info['start']})")
            
            # 決まり手
            if 'race_technique_number' in race_result:
                print(f"\n決まり手: {race_result['race_technique_number']}")
            
            # 払い戻し情報
            if 'payouts' in race_result:
                print("\n=== 払い戻し ===")
                payouts = race_result['payouts']
                
                if 'win' in payouts:
                    win_payout = payouts['win']
                    win_combo = payouts.get('win_combination', '')
                    if isinstance(win_payout, list) and len(win_payout) > 0:
                        for win in win_payout:
                            print(f"単勝 {win.get('combination', '')}号艇: {win.get('payout', '')}円")
                    else:
                        print(f"単勝 {win_combo}号艇: {win_payout}円")
                
                if 'trifecta' in payouts:
                    trifecta_payout = payouts['trifecta']
                    trifecta_combo = payouts.get('trifecta_combination', '')
                    if isinstance(trifecta_payout, list) and len(trifecta_payout) > 0:
                        for trifecta in trifecta_payout:
                            print(f"3連単 {trifecta.get('combination', '')}: {trifecta.get('payout', '')}円")
                    else:
                        print(f"3連単 {trifecta_combo}: {trifecta_payout}円")
        else:
            logging.warning("結果情報が見つかりません")
    else:
        logging.error("結果データの取得に失敗しました")
    
    # 処理時間の合計
    total_time = program_time + odds_time + result_time
    logging.info(f"合計処理時間: {total_time:.2f}秒")
    print(f"\n合計処理時間: {total_time:.2f}秒")

if __name__ == "__main__":
    get_and_print_one_race() 