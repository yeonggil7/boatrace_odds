# ボートレースデータスクレイピング

このスクリプトは2018年から2024年までのボートレースの選手データ、オッズデータ、結果データを全てCSVファイルで取得するためのものです。

## 機能

- 指定した期間（デフォルトでは2018年〜2024年4月）のレースデータを収集
- 以下のデータを取得してCSV形式で保存:
  - 開催場情報
  - 選手データ
  - レース情報（出走表）
  - オッズデータ（単勝・複勝、2連単・2連複、3連単・3連複）
  - レース結果データ（着順、スタートタイミング）
  - 払戻情報データ

## 必要環境

- Python 3.7以上
- PHP 7.4以上
- Composer（PHPのパッケージマネージャー）

## 依存パッケージ

- pandas: データ処理用
- tqdm: 進捗バー表示用
- python-dateutil: 日付処理用

## セットアップ

1. PHPの依存関係をインストール:

```bash
composer install
```

2. Pythonの依存関係をインストール:

```bash
pip install -r scrape_data_requirements.txt
```

## 使用方法

1. スクリプトを実行:

```bash
python scrape_data.py
```

処理が始まると、以下のようにデータ収集が行われます:

- 指定期間の各日付について開催場情報を取得
- 各開催場のレースごとに出走表、オッズ、結果データを取得
- 取得したデータをCSVファイルとして保存

## 出力データ

データは以下のディレクトリ構造で保存されます:

```
data/
├── stadiums/                 # 開催場情報
│   └── stadiums_YYYY-MM-DD.csv
├── programs/                 # レース情報（出走表）
│   └── program_YYYY-MM-DD_STADIUM_RACE.csv
├── racers/                   # 選手データ
│   └── racers_YYYY-MM-DD_STADIUM_RACE.csv
├── odds/                     # オッズデータ
│   ├── win_place_YYYY-MM-DD_STADIUM_RACE.csv    # 単勝・複勝
│   ├── exacta_YYYY-MM-DD_STADIUM_RACE.csv       # 2連単
│   ├── quinella_YYYY-MM-DD_STADIUM_RACE.csv     # 2連複
│   ├── trifecta_YYYY-MM-DD_STADIUM_RACE.csv     # 3連単
│   └── trio_YYYY-MM-DD_STADIUM_RACE.csv         # 3連複
└── results/                  # 結果データ
    ├── result_YYYY-MM-DD_STADIUM_RACE.csv         # レース結果情報
    ├── racer_results_YYYY-MM-DD_STADIUM_RACE.csv  # 選手成績
    └── payouts_YYYY-MM-DD_STADIUM_RACE.csv        # 払戻情報
```

各CSVファイルには以下のようなデータが含まれます:

### 開催場情報 (stadiums_YYYY-MM-DD.csv)
- stadium_number: 開催場番号
- stadium_name: 開催場名
- date: 日付

### 選手データ (racers_YYYY-MM-DD_STADIUM_RACE.csv)
- date: 日付
- stadium_number: 開催場番号
- race_number: レース番号
- boat_number: 艇番
- racer_name: 選手名
- racer_number: 選手登録番号
- racer_weight: 体重
- racer_class_code: 級別
- motor_number: モーター番号
- boat_number_2: ボート番号
- racer_age: 年齢
- branch_number: 支部番号
- birthplace_number: 出身地番号
- racer_flying_count: フライング回数
- racer_late_count: 遅れ回数
- racer_average_start_timing: 平均スタートタイミング

### レース情報 (program_YYYY-MM-DD_STADIUM_RACE.csv)
- date: 日付
- stadium_number: 開催場番号
- race_number: レース番号
- race_title: レースタイトル
- race_distance: レース距離
- race_closed_at: 締切時刻
- race_started_at: 発走時刻

### オッズデータ
各種オッズデータが対応するCSVファイルに保存されます。

### レース結果 (result_YYYY-MM-DD_STADIUM_RACE.csv)
- date: 日付
- stadium_number: 開催場番号
- race_number: レース番号
- race_weather_number: 天候番号
- race_temperature: 気温
- race_wind_direction_number: 風向番号
- race_wind: 風速
- race_wave: 波高
- race_water_temperature: 水温
- race_technique_number: 決まり手番号

### 選手成績 (racer_results_YYYY-MM-DD_STADIUM_RACE.csv)
- date: 日付
- stadium_number: 開催場番号
- race_number: レース番号
- boat_number: 艇番
- racer_name: 選手名
- racer_number: 選手登録番号
- racer_course_number: 進入コース
- racer_start_timing: スタートタイミング
- racer_place_number: 着順

### 払戻情報 (payouts_YYYY-MM-DD_STADIUM_RACE.csv)
- date: 日付
- stadium_number: 開催場番号
- race_number: レース番号
- bet_type: 賭け式（win:単勝, place:複勝, exacta:2連単, quinella:2連複, trifecta:3連単, trio:3連複）
- combination: 組合せ
- payout: 払戻金額

## 注意事項

- データ量が膨大になります（2018年〜2024年の全データで数GB以上）
- スクレイピングには時間がかかります（全期間で数日〜1週間程度）
- サーバー負荷を考慮して、リクエスト間隔を適切に設定しています
- エラーが発生した場合はlogファイル(scrape_data.log)を確認してください

## カスタマイズ

スクリプト内の以下の変数を編集することで、取得期間や動作を調整できます：

- `start_date`と`end_date`: データ取得期間
- `TIMEOUT`: リクエストのタイムアウト時間
- `max_workers`: 並列処理数（サーバー負荷を考慮して通常は1）

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。詳細はLICENSEファイルを参照してください。 