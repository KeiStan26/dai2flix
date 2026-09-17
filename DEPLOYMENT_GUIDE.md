# DAI2FLIX 完全手動オペレーション手順書 (DEPLOYMENT_GUIDE.md)

本書は、Antigravityによって生成されたコードベースから、GitHub Public公開、自宅Ubuntu Server（Apache2環境）への配置、デーモン化、日次同期バッチ稼働、ヘルスチェックまでの**全工程を網羅したステップ・バイ・ステップのマニュアル**です。

---

## 目次
1. [STEP 1: GitHubリポジトリの初期化とPush](#step-1-githubリポジトリの初期化とpush)
2. [STEP 2: アーキテクチャ判定結果と設計理由](#step-2-アーキテクチャ判定結果と設計理由)
3. [STEP 3: 実行・ホスティング環境のセットアップ](#step-3-実行ホスティング環境のセットアップ)
4. [STEP 4: 環境変数（.env）の配置と設定](#step-4-環境変数envの配置と設定)
5. [STEP 5: CI/CD（GitHub Actions）の設定](#step-5-cicdgithub-actionsの設定)
6. [STEP 6: 動作確認・ヘルスチェック・トラブルシューティング](#step-6-動作確認ヘルスチェックトラブルシューティング)

---

## STEP 1: GitHubリポジトリの初期化とPush

### 1-1. 機密情報の非保持確認
リポジトリ公開前に、機密情報（`.env` 等）が含まれていないことを確認します。

```bash
# Gitステータス確認（.env や *.db が Untracked になっていないこと）
git status

# .gitignore が適切に機能しているかの確認
git check-ignore -v backend/.env backend/dai2flix.db
```

### 1-2. GitHubリポジトリの作成
1. ブラウザで [GitHub](https://github.com/new) にアクセスします。
2. 設定項目:
   - **Repository name**: `dai2flix`
   - **Description**: `YouTubeクリエイター「だいにぐるーぷ」特化型Netflix風動画配信Webアプリ。YouTube Data API v3の最小クオータ運用とGemini APIによるキャッチコピー・あらすじ自動抽出、FastAPI＋SQLite(WAL)、React+Tailwindを採用し、Ubuntu+Apache2環境での完全放置運用を実現。`
   - **Public / Private**: `Public` を選択
   - **Initialize this repository with**: すべてチェックを外す（ローカルの既存コードをPushするため）
3. 「Create repository」をクリックします。

### 1-3. リモート登録と初回Push

```bash
# リモートリポジトリのURLを設定（ユーザー名は自身のアカウントに変更）
git remote add origin https://github.com/your-username/dai2flix.git

# メインブランチのPush
git branch -M main
git push -u origin main
```

---

## STEP 2: アーキテクチャ判定結果と設計理由

本要件におけるアーキテクチャ選定結果と選定理由は以下の通りです。

| 区分 | 採用技術 | 選定理由と設計判断 |
| :--- | :--- | :--- |
| **全体区分** | **Webアプリ (FastAPI + React SPA) ＋ 定期実行バッチ** | 自宅Ubuntu Server（Apache2環境）の既存リソースを最大限活用し、外部有料SaaSコストをゼロにするため。 |
| **Webサーバー / リバースプロキシ** | **Apache 2.4 (VirtualHost / ProxyPass)** | 既存稼働サイトを保護するため独立したバーチャルホスト設定ファイル（`/etc/apache2/sites-available/dai2flix.conf`）を作成。SPA用ルーティング（`FallbackResource`）と機密ファイル遮断をWebサーバー層で強制。 |
| **バックエンド** | **FastAPI + Uvicorn (systemd 常駐)** | 非同期高速処理、Pydanticによる厳格な入出力バリデーション、N+1問題を抑止するSQLAlchemy 2.0を採用。systemdで自動復旧・サンドボックス化。 |
| **データベース** | **SQLite (WALモード有効化)** | PostgreSQL等の重厚な外部DBサーバー構築を避け、メンテナンスフリーを実現。WAL（Write-Ahead Logging）により、バッチ書き込み中もWeb読み込みがブロックされない高並行性を担保。 |
| **データ同期バッチ** | **Python (cron 毎日深夜3時実行)** | YouTube APIクオータ消費を最小化（`search.list`完全排除、`playlists.list` / `playlistItems.list` / `videos.list` のみ使用）。Gemini APIは新着動画検知時のみ1回実行し、コストとクオータを保護。多重起動はPID検証付きファイルロック（`BatchLock`）で防止。 |
| **フロントエンド** | **React + Tailwind CSS (SPA)** | Netflixの漆黒テーマ・マイクロインタラクションを再現。パーソナライズはブラウザの `localStorage` で処理し、サーバーレス・認証不要による完全放置運用を実現。 |

---

## STEP 3: 実行・ホスティング環境のセットアップ

自宅のUbuntu Server上で以下の作業を実行します。

### 3-1. 必要なパッケージのインストール
Ubuntu Serverにログインし、Python, Node.js, Apache2モジュールを導入します。

```bash
sudo apt update && sudo apt install -y \
  git \
  python3 \
  python3-venv \
  python3-pip \
  nodejs \
  npm \
  apache2 \
  logrotate

# Apacheの必要モジュールを有効化
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo a2enmod rewrite
sudo a2enmod headers
sudo a2enmod deflate
sudo systemctl restart apache2
```

### 3-2. プロジェクトコードの配置

```bash
# アプリケーション配置ディレクトリの作成
sudo mkdir -p /var/www/dai2flix
sudo chown -R $USER:$USER /var/www/dai2flix

# リポジトリのクローン
git clone https://github.com/your-username/dai2flix.git /var/www/dai2flix
cd /var/www/dai2flix
```

### 3-3. Python仮想環境と依存関係のセットアップ

```bash
cd /var/www/dai2flix
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r backend/requirements.txt
```

### 3-4. フロントエンドのビルドと静的配置

```bash
cd /var/www/dai2flix/frontend
npm ci
npm run build

# ビルド成果物 (dist/) が /var/www/dai2flix/dist に存在することを確認
ls -la /var/www/dai2flix/dist
```

### 3-5. Apache2 バーチャルホストの設定
リポジトリ内の設定ファイルをApacheにコピーし、有効化します。

```bash
# 設定ファイルの配置
sudo cp /var/www/dai2flix/infra/apache-dai2flix.conf /etc/apache2/sites-available/dai2flix.conf

# ドメイン名やポートを環境に合わせて編集（任意）
# sudo nano /etc/apache2/sites-available/dai2flix.conf

# サイトの有効化と設定構文チェック
sudo a2ensite dai2flix.conf
sudo apache2ctl configtest

# Apacheの再読み込み
sudo systemctl reload apache2
```

### 3-6. systemdサービス（バックエンド常駐）の登録

```bash
# サービスファイルの配置
sudo cp /var/www/dai2flix/infra/dai2flix-backend.service /etc/systemd/system/dai2flix-backend.service

# ディレクトリ所有権を www-data（実行ユーザー）に調整
sudo chown -R www-data:www-data /var/www/dai2flix

# systemd デーモンのリロードと起動・自動起動の有効化
sudo systemctl daemon-reload
sudo systemctl enable dai2flix-backend
sudo systemctl start dai2flix-backend

# 起動状態の確認
sudo systemctl status dai2flix-backend
```

### 3-7. cron（同期バッチ）および logrotate の設定

```bash
# ログ出力用ディレクトリの作成
sudo mkdir -p /var/log/dai2flix
sudo chown -R www-data:www-data /var/log/dai2flix

# cron設定の配置（パーミッションは644必須）
sudo cp /var/www/dai2flix/infra/dai2flix.cron /etc/cron.d/dai2flix-sync
sudo chmod 644 /etc/cron.d/dai2flix-sync

# logrotate設定の配置
sudo cp /var/www/dai2flix/infra/dai2flix.logrotate /etc/logrotate.d/dai2flix
sudo chmod 644 /etc/logrotate.d/dai2flix

# logrotateのドライラン確認
sudo logrotate -d /etc/logrotate.d/dai2flix
```

---

## STEP 4: 環境変数（.env）の配置と設定

本番環境のバックエンド設定ファイルを作成し、厳格なパーミッションを付与します。

```bash
# .env.example からコピー
sudo cp /var/www/dai2flix/backend/.env.example /var/www/dai2flix/backend/.env

# www-data 以外からの読み書きを禁止 (chmod 600)
sudo chown www-data:www-data /var/www/dai2flix/backend/.env
sudo chmod 600 /var/www/dai2flix/backend/.env

# エディタで開き、実際のキーを入力
sudo nano /var/www/dai2flix/backend/.env
```

### `.env` の設定項目一覧

```ini
# ==============================================================================
# 本番環境 .env 設定値
# ==============================================================================

# YouTube Data API v3 キー (必須)
YOUTUBE_API_KEY=AIzaSy...your_actual_youtube_api_key

# Google Gemini API キー (必須: キャッチコピー・あらすじ生成用)
GEMINI_API_KEY=AIzaSy...your_actual_gemini_api_key

# だいにぐるーぷ公式チャンネルID
CHANNEL_ID=UCbfRz3J6n7G4t1v1Kj9M2xA

# 同期対象のプレイリストID（カンマ区切り。空の場合はチャンネル全公開プレイリストを自動同期）
SYNC_PLAYLIST_IDS=

# データベース接続文字列（SQLite WALモード）
DATABASE_URL=sqlite:////var/www/dai2flix/backend/dai2flix.db

# 排他ロックファイルパス
LOCK_FILE_PATH=/var/www/dai2flix/backend/sync.lock

# サーバーバインド設定
HOST=127.0.0.1
PORT=8000
LOG_LEVEL=INFO
```

設定反映のため、バックエンドを再起動します:
```bash
sudo systemctl restart dai2flix-backend
```

---

## STEP 5: CI/CD（GitHub Actions）の設定

本リポジトリには `.github/workflows/main.yml` が同梱されており、GitHubへPushすると自動的に以下が実行されます。

1. **Backend Tests**: Python 3.10, 3.11, 3.12 マトリックスでの単体テスト・結合テスト。
2. **Frontend Build**: Node.js 20 での `npm ci` および TypeScript型チェック付き本番バンドルビルド。

### Secretsの登録（必要な場合）
単体テストはすべてMock化されているため、CIテストの実行に実APIキーは不要です。
将来的に本番自動デプロイ（SSH経由の自動Pull＆Restart等）を追加する場合は、GitHubリポジトリの **Settings > Secrets and variables > Actions** に以下を登録します:

- `SERVER_HOST`: 自宅サーバーのグローバルIPまたはDDNSホスト名
- `SERVER_USER`: SSH接続ユーザー名
- `SSH_PRIVATE_KEY`: デプロイ用SSH秘密鍵

---

## STEP 6: 動作確認・ヘルスチェック・トラブルシューティング

### 6-1. 初回データ同期バッチの手動実行
cronの深夜3時を待たずに、初回データを即座に収集します。

```bash
# www-data ユーザー権限で同期バッチを手動トリガー
sudo -u www-data /var/www/dai2flix/.venv/bin/python /var/www/dai2flix/backend/scripts/sync_batch.py
```

ログ出力例:
```text
[2026-09-17 14:00:00] [INFO] sync_batch: Starting DAI2FLIX sync batch...
[2026-09-17 14:00:01] [INFO] sync_batch: Found 12 target playlists for synchronization.
[2026-09-17 14:00:05] [INFO] sync_batch: Fetching details for 86 unique videos...
[2026-09-17 14:00:10] [INFO] sync_batch: Found 86 new videos requiring AI enrichment.
[2026-09-17 14:00:40] [INFO] sync_batch: Successfully enriched video '【1週間逃亡生活】' [v_xyz...]
[2026-09-17 14:01:00] [INFO] sync_batch: Sync batch completed: {'playlists_synced': 12, 'videos_synced': 86, 'videos_enriched': 86, 'errors': 0}
[2026-09-17 14:01:00] [INFO] sync_batch: Batch lock released successfully.
```

### 6-2. ヘルスチェックAPIの確認

```bash
# ローカル内部APIの直接疎通確認
curl -s http://127.0.0.1:8000/api/health | jq .
```
期待されるレスポンス:
```json
{
  "status": "healthy",
  "database": "connected",
  "video_count": 86,
  "playlist_count": 12,
  "last_synced_at": "2026-09-17T05:01:00Z",
  "version": "0.1.0"
}
```

```bash
# Apacheリバースプロキシ経由の疎通確認
curl -s http://localhost/api/health | jq .
```

### 6-3. フィード集約APIの確認

```bash
curl -s http://localhost/api/v1/feed?limit_per_row=2 | jq .billboard
```

### 6-4. 機密ファイル遮断のセキュリティ検証

Webブラウザまたは curl で、機密ファイルへのアクセスが **403 Forbidden** で遮断されることを確認します。

```bash
# 以下のリクエストがすべて HTTP 403 Forbidden になることを確認
curl -I http://localhost/.env
curl -I http://localhost/backend/.env
curl -I http://localhost/dai2flix.db
curl -I http://localhost/.git/config
```

### 6-5. トラブルシューティング

| 症状 | 原因と対処法 |
| :--- | :--- |
| **APIアクセス時に 502 Bad Gateway** | FastAPIサービスが停止している可能性があります。<br>`sudo systemctl status dai2flix-backend`<br>`sudo journalctl -u dai2flix-backend -n 50` でログを確認してください。 |
| **同期バッチが起動しない / スキップされる** | 前回のプロセスが異常終了しロックファイルが残っている可能性があります。<br>`sudo -u www-data /var/www/dai2flix/.venv/bin/python /var/www/dai2flix/backend/scripts/sync_batch.py --force-unlock` を実行してロックを解除してください。 |
| **Gemini AIのエンリッチメントがスキップされる** | `backend/.env` 内の `GEMINI_API_KEY` が未設定、またはAPIクオータ超過の可能性があります。<br>ヒューリスティックフォールバックによりバッチ自体は正常終了しますが、AI StudioのAPIキー有効性を確認してください。 |
| **画面が真っ白 / 404エラー** | ApacheのSPAルーティングが無効になっている可能性があります。<br>`/etc/apache2/sites-available/dai2flix.conf` 内の `FallbackResource /index.html` が記載されているか確認し、`sudo a2enmod rewrite && sudo systemctl restart apache2` を実行してください。 |

---

以上で本番公開と完全放置運用のセットアップは完了です。
毎日の新着動画が自動同期され、Netflix風のリッチな動画視聴体験が提供されます。
