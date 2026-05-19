# Discord Web Briefing Bots

毎朝ウェブ情報を収集してDiscordへ要約を投稿するボットと、同じDiscordサーバーで収集済み情報から質問に答える別ボットのセット

## 構成

- `digest_bot`: RSSやWebページから記事を集め、SQLiteへ保存し、毎朝指定チャンネルへ要約を投稿
- `qa_bot`: `/ask` コマンドで、保存済み記事を検索し、根拠URLつきで回答
- `data/knowledge.sqlite3`: 両ボットが共有する記事データベース（Railway Volume で永続化）

## 本番環境（Railway）

QA Bot と Digest Bot は Railway 上で稼働している。

| サービス | 種別 | 起動コマンド |
|---------|------|-------------|
| qa_bot | Worker（常時起動） | `python -m briefing_bots.qa_bot` |
| digest_bot | Cron（毎日 07:00 JST） | `python -m briefing_bots.run_notify_once` |

両サービスは同じ Railway Volume（`/data`）を共有し、SQLite データベースを永続化している。

### Railway に初めてデプロイする場合

1. Railway でプロジェクトを作成し、このリポジトリを接続
2. 各サービスに環境変数を設定（下記参照）
3. Volume を作成してマウントパス `/data` で両サービスに接続
4. digest_bot サービスの Cron Schedule を `0 22 * * *`（UTC）に設定

## ローカルセットアップ

Python 3.10以上

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
Copy-Item .env.example .env
```

`.env` に以下を設定

- `OPENAI_API_KEY`
- `DIGEST_DISCORD_TOKEN`
- `DIGEST_CHANNEL_ID`
- `QA_DISCORD_TOKEN`
- `DISCORD_GUILD_ID`

Discord Developer Portal で2つの Application/Bot を作り、同じサーバーへ招待する

必要な権限

- Digest Bot: Send Messages, View Channels
- QA Bot: Use Slash Commands, Send Messages, View Channels

## 環境変数一覧

| 変数名 | 説明 | 対象サービス |
|--------|------|-------------|
| `OPENAI_API_KEY` | OpenAI API キー | 両方 |
| `DIGEST_DISCORD_TOKEN` | Digest Bot のトークン | digest_bot |
| `DIGEST_CHANNEL_ID` | 投稿先チャンネル ID | digest_bot |
| `QA_DISCORD_TOKEN` | QA Bot のトークン | qa_bot |
| `DISCORD_GUILD_ID` | サーバー ID | qa_bot |
| `DATABASE_PATH` | SQLite パス（Railway: `/data/knowledge.sqlite3`） | 両方 |
| `CONFIG_PATH` | 設定ファイルパス（`config/sources.yml`） | 両方 |
| `TIMEZONE` | タイムゾーン（`Asia/Tokyo`） | 両方 |

## Discord コマンド

配信用ボット

- `/keyword_add keyword:...`: 収集キーワードを追加
- `/keyword_delete keyword:...`: 収集キーワードを削除
- `/keyword_list`: 収集キーワードを表示

質問応答ボット

- `/ask question:...`: 収集済み情報から回答

朝の要約は、登録済みキーワードごとに大きく分けて投稿

## ローカル起動

配信用ボット

```powershell
python -m briefing_bots.digest_bot
```

質問応答ボット

```powershell
python -m briefing_bots.qa_bot
```

## 手動実行

動作確認や初回データ収集

```powershell
python -m briefing_bots.run_digest_once
```

## 情報源の追加

### RSS フィードを追加する

[config/sources.yml](config/sources.yml) の `sources` に追記する

```yaml
- name: "サイト名"
  url: "https://example.com/feed.xml"
  kind: "rss"
```

Twitter アカウントを RSS に変換したい場合は [rss.app](https://rss.app) で URL を生成して追加する

キーワードが未登録の場合は先に `/keyword_add` でキーワードを追加すること。収集はキーワードにマッチした記事のみ保存される
