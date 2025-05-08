# ボートレースオッズ分析アプリ

ボートレースのオッズ情報と結果を視覚的に分析するStreamlitアプリケーションです。

## 機能

- 日付ごとのレース情報の表示
- オッズデータの可視化（単勝、複勝、2連単、2連複、3連単、3連複）
- レース結果の表示（着順、払い戻し情報）
- シンプルなAI予想機能（モック実装）

## 使用方法

1. サイドバーから日付を選択
2. 開催場とレース番号を選択
3. 「オッズ情報を取得」ボタンをクリック
4. タブを切り替えて、各種情報を閲覧

## 必要条件

- Python 3.8以上
- Streamlit
- Pandas
- NumPy
- Matplotlib
- PHP（スクレイピング機能に必要）

## インストール方法

```bash
pip install -r requirements.txt
```

## 起動方法

```bash
streamlit run odds_streamlit.py
```

## デプロイ方法

Streamlit Cloudを使用して簡単にデプロイできます：

1. GitHubアカウントでStreamlit Cloudにログイン
2. このリポジトリを選択
3. ファイルパスに「odds_streamlit.py」を指定
4. デプロイボタンをクリック

## ライセンス

MIT
