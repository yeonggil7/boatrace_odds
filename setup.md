# ボートレースオッズ分析アプリのセットアップ手順

このドキュメントでは、ボートレースオッズ分析アプリケーションのセットアップ方法について説明します。
アプリケーションはAPIサーバーとStreamlitアプリの2つの部分から構成されています。

## 前提条件

- Python 3.8以上
- PHP 7.4以上
- Composer（PHPのパッケージマネージャー）

## セットアップ手順

### 1. リポジトリのクローン

```bash
git clone https://github.com/yeonggil7/boatrace_odds.git
cd boatrace_odds
```

### 2. PHPの依存関係をインストール

```bash
composer install
```

### 3. Pythonの依存関係をインストール

APIサーバー用の依存関係:

```bash
pip install -r api_requirements.txt
```

Streamlitアプリ用の依存関係:

```bash
pip install -r requirements.txt
```

## 実行方法

### APIサーバーの起動

```bash
uvicorn api_server:app --reload
```

デフォルトでは、APIサーバーは http://localhost:8000 で実行されます。

### Streamlitアプリの起動

APIサーバーを起動した状態で、別のターミナルウィンドウで以下のコマンドを実行します。

```bash
streamlit run odds_streamlit_api.py
```

デフォルトでは、Streamlitアプリは http://localhost:8501 で実行されます。

## デプロイ方法

### Herokuへのデプロイ

1. Herokuアカウントを作成し、Heroku CLIをインストールします。
2. Herokuにログインし、新しいアプリケーションを作成します。

```bash
heroku login
heroku create your-app-name
```

3. リポジトリをHerokuにプッシュします。

```bash
git push heroku streamlit-app:main
```

4. Buildpackを設定します（Python + PHPの両方が必要）。

```bash
heroku buildpacks:add heroku/python
heroku buildpacks:add heroku/php
```

5. 環境変数を設定します。

```bash
heroku config:set API_URL=https://your-app-name.herokuapp.com/api
```

6. アプリケーションを開きます。

```bash
heroku open
```

### StreamlitのShare/Cloudを使用する場合

1. APIサーバーを別途デプロイします（Heroku、AWS、GCPなど）。
2. `odds_streamlit_api.py`の`API_BASE_URL`を実際のAPIサーバーのURLに更新します。
3. Streamlit Shareにログインし、GithubリポジトリとMainファイルパス（`odds_streamlit_api.py`）を指定してデプロイします。

## トラブルシューティング

- **APIサーバー接続エラー**: APIのベースURLが正しく設定されていることを確認してください。
- **PHPスクリプト実行エラー**: PHPがインストールされており、パスが正しく設定されていることを確認してください。
- **レース情報が取得できない**: 指定した日付のレース情報が存在するか確認してください。

## 注意事項

このアプリケーションは、公開されているボートレース情報をスクレイピングして表示しています。
利用にあたっては、各ボートレース場および公式サイトの利用規約に従ってください。

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。詳細はLICENSEファイルを参照してください。 