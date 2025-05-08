from fastapi import FastAPI, HTTPException
import subprocess
import json
import os
from datetime import datetime
import uvicorn
from pydantic import BaseModel
from typing import Optional, Dict, Any, Union
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ボートレースAPI", description="ボートレース情報取得API")

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では適切に制限すること
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# タイムアウト設定（秒）
STADIUM_TIMEOUT = 30
CHECK_TIMEOUT = 15
ODDS_TIMEOUT = 30
PROGRAM_TIMEOUT = 20
PREVIEW_TIMEOUT = 20

class DateRequest(BaseModel):
    date: Optional[str] = None

class RaceRequest(BaseModel):
    stadium_number: int
    race_number: int
    date: Optional[str] = None

@app.get("/")
def read_root():
    return {"message": "ボートレースAPIサーバーが稼働中です"}

@app.post("/api/stadiums")
def get_stadiums(request: DateRequest):
    """指定日付のボートレース場情報を取得"""
    date_str = request.date if request.date else datetime.today().strftime('%Y-%m-%d')
    
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
            return {"error": f"開催場情報の取得に失敗しました: {result.stderr}", "stdout": result.stdout}
            
        try:
            stadiums = json.loads(result.stdout)
            if not stadiums:
                return {"warning": f"{date_str}の開催場情報が空です", "data": {}}
                
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
                        continue
                        
                    try:
                        program_data = json.loads(check_result.stdout)
                        if not program_data:
                            continue
                            
                        # プログラムデータが存在し、レース情報が取得できれば有効な開催場
                        if stadium_number in program_data and "1" in program_data[stadium_number]:
                            valid_stadiums[stadium_number] = stadium_name
                    except json.JSONDecodeError:
                        continue
                except subprocess.TimeoutExpired:
                    continue
                except Exception:
                    continue
            
            if not valid_stadiums:
                return {"warning": f"{date_str}の有効な開催場が見つかりませんでした。", "data": {}}
            
            return {"data": valid_stadiums}
            
        except json.JSONDecodeError as e:
            return {"error": f"開催場情報の解析に失敗しました: {e}", "stdout": result.stdout}
            
    except Exception as e:
        return {"error": f"開催場情報の取得に失敗しました: {e}"}

@app.post("/api/race/odds")
def get_race_odds(request: RaceRequest):
    """指定したレース場・レース番号のオッズ情報を取得"""
    stadium_number = request.stadium_number
    race_number = request.race_number
    date_str = request.date if request.date else datetime.today().strftime('%Y-%m-%d')
    
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
            return {"error": f"PHPスクリプトの実行に失敗しました: {result.stderr}", "stdout": result.stdout}
            
        try:
            odds_data = json.loads(result.stdout)
            if not odds_data:
                return {"error": "オッズデータが空です"}
                
            if str(stadium_number) not in odds_data:
                return {"error": f"開催場 {stadium_number} のデータが見つかりません"}
                
            if str(race_number) not in odds_data[str(stadium_number)]:
                return {"error": f"レース {race_number} のデータが見つかりません"}
                
            return {"data": odds_data}
        except json.JSONDecodeError as e:
            return {"error": f"オッズデータの解析に失敗しました: {e}", "stdout": result.stdout}
            
    except subprocess.TimeoutExpired:
        return {"error": f"オッズデータの取得がタイムアウトしました（{ODDS_TIMEOUT}秒）"}
    except Exception as e:
        return {"error": f"予期せぬエラーが発生しました: {e}"}

@app.post("/api/race/program")
def get_race_program(request: RaceRequest):
    """指定したレース場・レース番号の出走表情報を取得"""
    stadium_number = request.stadium_number
    race_number = request.race_number
    date_str = request.date if request.date else datetime.today().strftime('%Y-%m-%d')
    
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
        
        try:
            program_data = json.loads(result.stdout)
            return {"data": program_data}
        except json.JSONDecodeError:
            return {"error": f"出走表データの解析に失敗しました", "stdout": result.stdout}
    except subprocess.TimeoutExpired:
        return {"error": f"出走表データの取得がタイムアウトしました（{PROGRAM_TIMEOUT}秒）"}
    except Exception as e:
        return {"error": f"予期せぬエラーが発生しました: {e}"}

@app.post("/api/race/preview")
def get_race_preview(request: RaceRequest):
    """指定したレース場・レース番号の直前情報を取得"""
    stadium_number = request.stadium_number
    race_number = request.race_number
    date_str = request.date if request.date else datetime.today().strftime('%Y-%m-%d')
    
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
        
        try:
            preview_data = json.loads(result.stdout)
            return {"data": preview_data}
        except json.JSONDecodeError:
            return {"error": f"直前情報の解析に失敗しました", "stdout": result.stdout}
    except subprocess.TimeoutExpired:
        return {"error": f"直前情報の取得がタイムアウトしました（{PREVIEW_TIMEOUT}秒）"}
    except Exception as e:
        return {"error": f"予期せぬエラーが発生しました: {e}"}

@app.post("/api/race/result")
def get_race_result(request: RaceRequest):
    """指定したレース場・レース番号のレース結果を取得"""
    stadium_number = request.stadium_number
    race_number = request.race_number
    date_str = request.date if request.date else datetime.today().strftime('%Y-%m-%d')
    
    # 日付形式の変換
    if isinstance(date_str, datetime):
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
            return {"error": "レース結果の取得に失敗しました", "debug_info": debug_info}
            
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
                return {"error": "レース結果のJSONデータ解析に失敗しました", "debug_info": debug_info}
            
            if isinstance(result_data, dict) and 'error' in result_data:
                debug_info["error"] = result_data['error']
                return {"error": result_data['error'], "debug_info": debug_info}
            
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
                        return {"error": "レース結果データが不完全です", "debug_info": debug_info}
                    
                    # 払い戻し情報の整理
                    payoffs = {}
                    if 'payouts' in race_data:
                        payoffs = race_data['payouts']
                        
                        # 単勝
                        if 'win' in payoffs:
                            if isinstance(payoffs['win'], list) and len(payoffs['win']) > 0:
                                for win in payoffs['win']:
                                    payoffs['win'] = win['payout']
                                    payoffs['win_combination'] = win['combination']
                            elif isinstance(payoffs['win'], (int, float)) and payoffs.get('win_combination'):
                                payoffs['win'] = payoffs['win']
                                payoffs['win_combination'] = payoffs['win_combination']
                        
                        # 複勝
                        if 'place' in payoffs:
                            if isinstance(payoffs['place'], list) and len(payoffs['place']) > 0:
                                for place in payoffs['place']:
                                    payoffs['place'] = place['payout']
                                    payoffs['place_combination'] = place['combination']
                            elif isinstance(payoffs['place'], (int, float)) and payoffs.get('place_combination'):
                                payoffs['place'] = payoffs['place']
                                payoffs['place_combination'] = payoffs['place_combination']
                        
                        # 3連単
                        if 'trifecta' in payoffs:
                            if isinstance(payoffs['trifecta'], list) and len(payoffs['trifecta']) > 0:
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
                    return {"data": processed_data, "debug_info": debug_info}
                else:
                    # キーが見つからない場合
                    available_keys = list(result_data.keys())
                    debug_info["error"] = f"必要なデータキーが見つかりません。利用可能なキー: {available_keys}"
                    return {"error": "必要なデータキーが見つかりません", "debug_info": debug_info}
            
            debug_info["error"] = "レースデータの構造が不正です"
            debug_info["data_type"] = str(type(result_data))
            return {"error": "レースデータの構造が不正です", "debug_info": debug_info}
            
        except json.JSONDecodeError as e:
            debug_info["error"] = f"レース結果の解析に失敗しました: {e}"
            debug_info["raw_output"] = result.stdout
            return {"error": "レース結果の解析に失敗しました", "debug_info": debug_info}
            
    except subprocess.TimeoutExpired:
        debug_info["error"] = f"レース結果の取得がタイムアウトしました（{PROGRAM_TIMEOUT}秒）"
        return {"error": "レース結果の取得がタイムアウトしました", "debug_info": debug_info}
    except Exception as e:
        debug_info["error"] = f"予期せぬエラーが発生しました: {e}"
        debug_info["exception_type"] = str(type(e))
        return {"error": "予期せぬエラーが発生しました", "debug_info": debug_info}

if __name__ == "__main__":
    # 開発サーバー起動（本番では適切なサーバー設定を使用すること）
    uvicorn.run(app, host="0.0.0.0", port=8000) 