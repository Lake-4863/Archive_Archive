# リモート通知

PC停止中でもDiscord通知を送るためのGitHub Actions設定

## 動き

- GitHub Actionsが毎日 `06:10` 日本時間に起動
- `config/sources.yml` の各チャンネル向けに要約を生成
- Discord Bot APIで各 `channel_id` へ投稿
- 手動実行はGitHubの `Actions` から `Discord digest` を選択して `Run workflow`

## 必要なGitHub Secrets

リポジトリの `Settings` → `Secrets and variables` → `Actions` に追加

- `OPENAI_API_KEY`
- `DIGEST_DISCORD_TOKEN`

## ローカル確認

投稿せずに内容だけ確認

```powershell
python -m briefing_bots.run_notify_once --dry-run
```

投稿まで実行

```powershell
python -m briefing_bots.run_notify_once
```

## 時刻変更

`.github/workflows/discord-digest.yml` の `cron` はUTC

- 日本時間 `06:10` → UTC `21:10`
- 日本時間 `08:00` → UTC `23:00`

## 注意

- Discord側でBotが対象チャンネルへ投稿できる権限
- GitHub Actionsの定時実行は数分遅れる場合あり
- QA Botの常時応答もPC停止中に使う場合は、RenderやRailwayなどの常時起動先が必要
