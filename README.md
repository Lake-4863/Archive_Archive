# Discord Web Briefing Bots

毎朝ウェブ情報を収集してDiscordへ要約を投稿するボットと、同じDiscordサーバーで収集済み情報から質問に答える別ボットのセット

## 構成

- `digest_bot`: RSSやWebページから記事を集め、SQLiteへ保存し、毎朝指定チャンネルへ要約を投稿
- `qa_bot`: `/ask` コマンドで、保存済み記事を検索し、根拠URLつきで回答
- `data/knowledge.sqlite3`: 両ボットが共有する記事データベース

## セットアップ

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

Discord Developer Portalで2つのApplication/Botを作り、同じサーバーへ招待する

必要な権限

- Digest Bot: Send Messages, View Channels
- QA Bot: Use Slash Commands, Send Messages, View Channels

## Discordコマンド

配信用ボット

- `/keyword_add keyword:...`: 収集キーワードを追加
- `/keyword_delete keyword:...`: 収集キーワードを削除
- `/keyword_list`: 収集キーワードを表示

質問応答ボット

- `/ask question:...`: 収集済み情報から回答

朝の要約は、登録済みキーワードごとに大きく分けて投稿

## 起動

配信用ボット

```powershell
python -m briefing_bots.digest_bot
```

質問応答ボット

```powershell
python -m briefing_bots.qa_bot
```

## 手動実行

朝の配信前に動作確認する場合

```powershell
python -m briefing_bots.run_digest_once
```

## 情報源の追加

### RSSフィードを追加する

[config/sources.yml](config/sources.yml) の `sources` に追記する

```yaml
- name: "サイト名"
  url: "https://example.com/feed.xml"
  kind: "rss"
```

TwitterアカウントをRSSに変換したい場合は [rss.app](https://rss.app) でURLを生成して追加する

### 一度だけ情報収集を実行する

```powershell
python -m briefing_bots.run_digest_once
```

キーワードが未登録の場合は先に `/keyword_add` でキーワードを追加すること。収集はキーワードにマッチした記事のみ保存される
