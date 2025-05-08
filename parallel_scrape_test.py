import subprocess
import json
import os
import time
import datetime
import logging
import sys
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("parallel_test.log"),
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

def get_race_result(date_str, stadium_number, race_number):
    """指定レースの結果データを取得"""
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
    
    try:
        start_time = time.time()
        result_data = run_php_script(result_script)
        elapsed_time = time.time() - start_time
        
        success = False
        if result_data and str(stadium_number) in result_data and str(race_number) in result_data[str(stadium_number)]:
            success = True
        
        return {
            "date": date_str,
            "stadium": stadium_number,
            "race": race_number,
            "success": success,
            "time": elapsed_time
        }
    except Exception as e:
        logging.error(f"結果取得エラー({date_str} {stadium_number} {race_number}): {e}")
        return {
            "date": date_str,
            "stadium": stadium_number,
            "race": race_number,
            "success": False,
            "time": 0
        }

def get_one_stadium_results(date_str, stadium_number, max_races=12, workers=4):
    """指定した開催場の全レース結果を並列で取得"""
    race_tasks = []
    for race_number in range(1, max_races + 1):
        race_tasks.append((date_str, stadium_number, race_number))
    
    results = []
    successful = 0
    total_time = 0
    
    print(f"\n=== {date_str} 開催場{stadium_number}の全レース結果取得 (並列数: {workers}) ===")
    
    # 開始時間
    start_time = time.time()
    
    # 並列処理
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_race = {executor.submit(get_race_result, date, stadium, race): (date, stadium, race) 
                         for date, stadium, race in race_tasks}
        
        # 進捗バー付きで実行
        for future in tqdm(as_completed(future_to_race), total=len(race_tasks), desc=f"レース結果取得"):
            date, stadium, race = future_to_race[future]
            try:
                result = future.result()
                results.append(result)
                
                if result["success"]:
                    successful += 1
                    total_time += result["time"]
            except Exception as e:
                logging.error(f"並列処理エラー({date} {stadium} {race}): {e}")
    
    # 処理時間の合計と平均
    elapsed_time = time.time() - start_time
    avg_time = total_time / successful if successful > 0 else 0
    
    print(f"\n=== 結果 ===")
    print(f"取得成功: {successful}/{len(race_tasks)}")
    print(f"並列処理の合計時間: {elapsed_time:.2f}秒")
    print(f"各レース処理の合計時間: {total_time:.2f}秒")
    print(f"処理時間の節約: {total_time - elapsed_time:.2f}秒 (並列化による削減率: {(total_time - elapsed_time) / total_time * 100:.1f}%)")
    print(f"1レース当たりの平均時間: {avg_time:.2f}秒")
    
    return {
        "date": date_str,
        "stadium": stadium_number,
        "successful": successful,
        "total": len(race_tasks),
        "parallel_time": elapsed_time,
        "sequential_time": total_time,
        "avg_time": avg_time
    }

def test_multiple_stadiums(date_str="2022-12-31", stadiums=[1, 2, 3, 4], max_races=12, workers_per_stadium=4, max_stadiums=2):
    """複数の開催場で並列処理のパフォーマンステスト"""
    print(f"\n====== 並列スクレイピングパフォーマンステスト ======")
    print(f"日付: {date_str}")
    print(f"開催場: {stadiums}")
    print(f"各開催場の最大レース数: {max_races}")
    print(f"各開催場の並列処理数: {workers_per_stadium}")
    print(f"同時処理する開催場数: {max_stadiums}")
    
    # 開始時間
    start_time = time.time()
    
    all_results = []
    
    # 開催場ごとの並列処理
    with ThreadPoolExecutor(max_workers=max_stadiums) as executor:
        future_to_stadium = {executor.submit(get_one_stadium_results, date_str, stadium, max_races, workers_per_stadium): 
                            stadium for stadium in stadiums}
        
        for future in as_completed(future_to_stadium):
            stadium = future_to_stadium[future]
            try:
                result = future.result()
                all_results.append(result)
            except Exception as e:
                logging.error(f"開催場処理エラー({date_str} {stadium}): {e}")
    
    # 合計時間と結果
    total_elapsed = time.time() - start_time
    
    # 集計
    total_races = sum(r["total"] for r in all_results)
    successful_races = sum(r["successful"] for r in all_results)
    sequential_time = sum(r["sequential_time"] for r in all_results)
    
    print(f"\n====== 総合結果 ======")
    print(f"総処理時間: {total_elapsed:.2f}秒")
    print(f"シーケンシャル処理した場合の合計時間: {sequential_time:.2f}秒")
    print(f"並列化による時間節約: {sequential_time - total_elapsed:.2f}秒")
    print(f"並列化による高速化率: {sequential_time / total_elapsed:.1f}倍")
    print(f"取得成功レース数: {successful_races}/{total_races}")
    
    return {
        "date": date_str,
        "stadiums": len(stadiums),
        "total_races": total_races,
        "successful_races": successful_races,
        "parallel_time": total_elapsed,
        "sequential_time": sequential_time,
        "speedup": sequential_time / total_elapsed if total_elapsed > 0 else 0
    }

def test_parallel_processing():
    """並列処理の効果を検証するためのテスト"""
    print("====== 並列処理性能検証 ======")
    
    # テスト設定
    date = "2022-12-31"  # 過去の確実に開催があった日付
    
    # パフォーマンステスト
    print("\n----- シングルスレッド vs マルチスレッド -----")
    
    # 1. シングルスレッドで1開催場のデータ取得
    result_single = get_one_stadium_results(date, 1, max_races=12, workers=1)
    
    # 2. マルチスレッド(4)で同じ開催場のデータ取得
    result_multi = get_one_stadium_results(date, 1, max_races=12, workers=4)
    
    # 3. マルチスレッド(8)で同じ開催場のデータ取得
    result_multi8 = get_one_stadium_results(date, 1, max_races=12, workers=8)
    
    # 4. 複数開催場の同時処理
    print("\n----- 複数開催場の並列処理 -----")
    
    # 2開催場を同時処理
    result_multi_stadium = test_multiple_stadiums(date, stadiums=[1, 2], max_races=12, 
                                                 workers_per_stadium=4, max_stadiums=2)
    
    # 速度比較
    print("\n====== 並列処理効果の比較 ======")
    
    print(f"シングルスレッド (1開催場): {result_single['parallel_time']:.2f}秒")
    print(f"マルチスレッド(4) (1開催場): {result_multi['parallel_time']:.2f}秒, 高速化率: {result_single['parallel_time'] / result_multi['parallel_time']:.1f}倍")
    print(f"マルチスレッド(8) (1開催場): {result_multi8['parallel_time']:.2f}秒, 高速化率: {result_single['parallel_time'] / result_multi8['parallel_time']:.1f}倍")
    print(f"複数開催場の並列処理: {result_multi_stadium['parallel_time']:.2f}秒, 高速化率: {result_multi_stadium['sequential_time'] / result_multi_stadium['parallel_time']:.1f}倍")
    
    # 結論出力
    print("\n====== 並列処理検証の結論 ======")
    
    # 最適な並列数を計算
    if result_multi['parallel_time'] <= result_multi8['parallel_time']:
        optimal_threads = 4
        best_time = result_multi['parallel_time']
    else:
        optimal_threads = 8
        best_time = result_multi8['parallel_time']
    
    print(f"1. 最適なスレッド数: 1開催場あたり {optimal_threads} スレッド")
    print(f"2. 単一開催場での最適実行時間: {best_time:.2f}秒")
    print(f"3. 全データ取得での推奨並列処理: 複数開催場 x {optimal_threads}スレッド/開催場")
    
    estimated_full_time = best_time * (24 * 30 / result_multi_stadium['stadiums'])  # 24開催日 x 30日
    print(f"4. 1ヶ月分データの推定取得時間: {estimated_full_time:.1f}秒 ({estimated_full_time/60:.1f}分)")

if __name__ == "__main__":
    test_parallel_processing() 