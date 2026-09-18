# DAI2FLIX 完全手動オペレーション手順書 (DEPLOYMENT_GUIDE.md)

本書は、Antigravityによって生成されたコードベースから、GitHub Public公開、自宅Ubuntu Server（Apache2既存稼働環境）への安全な配置、デーモン化、日次同期バッチ稼働、ドメイン公開・HTTPS化までの**全工程を網羅したステップ・バイ・ステップのマニュアル**です。

---

## 既存システムとの共存・非干渉保証について

> [!IMPORTANT]
> **Q. 既存で運用中の Apache2 や `https://zyuuuukak1n.dev/`（`/var/www/html/`）に干渉しませんか？**
>
> **A. はい、完全に干渉しない「安全な分離構成」となっています。**
>
> 本システムは以下の多層防御により、既存サイト・既存プロセスへの影響をゼロに抑えています：
> 1. **Apache VirtualHostの完全独立**:
>    既存の設定ファイルには一切手を加えず、`/etc/apache2/sites-available/dai2flix.conf` として独立した設定ファイルを新設します。
> 2. **名前ベースバーチャルホスト（Name-based VirtualHost）による分離**:
>    `ServerName dai2flix.zyuuuukak1n.dev` を明示指定するため、`zyuuuukak1n.dev` 宛てのリクエストは既存の `/var/www/html/` が引き続き100%処理し、DAI2FLIX側の設定が既存リクエストを横取りすることはありません。
> 3. **ファイル配置・DocumentRootの分離**:
>    `/var/www/html/` には一切触れず、`/var/www/dai2flix/` という独立ディレクトリに配置します。
> 4. **データベース・常駐プロセスの分離**:
>    既存のDBサーバー（MySQL/PostgreSQL等）を使わず、専用のSQLite（WALモード）で完結。バックエンドFastAPIデーモンも独立したsystemdユニット（`dai2flix-backend.service`）として管理されます。
> 5. **内部ポートの安全確保**:
>    FastAPIは外部に公開せず `127.0.0.1:8000`（ローカルループバック）にのみバインドします。既存で8000番ポートが使用中か確認する手順および変更手順も本書に記載しています。

---

## 目次
1. [STEP 1: GitHubリポジトリの初期化とPush](#step-1-githubリポジトリの初期化とpush)
2. [STEP 2: アーキテクチャ判定結果と設計理由](#step-2-アーキテクチャ判定結果と設計理由)
3. [STEP 3: 既存環境チェックとホスティング環境のセットアップ](#step-3-既存環境チェックとホスティング環境のセットアップ)
4. [STEP 4: ドメイン公開とSSL/HTTPS化手順（dai2flix.zyuuuukak1n.dev）](#step-4-ドメイン公開とsslhttps化手順)
5. [STEP 5: 環境変数（.env）の配置と設定](#step-5-環境変数envの配置と設定)
6. [STEP 6: CI/CD（GitHub Actions）の設定](#step-6-cicdgithub-actionsの設定)
7. [STEP 7: 動作確認・ヘルスチェック・トラブルシューティング](#step-7-動作確認ヘルスチェックトラブルシューティング)

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

| 区分 | 採用技術 | 選定理由と既存環境保護 |
| :--- | :--- | :--- |
| **全体区分** | **Webアプリ (FastAPI + React SPA) ＋ 定期実行バッチ** | 自宅Ubuntu Server（Apache2環境）の既存リソースを最大限活用し、追加クラウド課金をゼロにするため。 |
| **Webサーバー / リバースプロキシ** | **Apache 2.4 (VirtualHost / ProxyPass)** | 既存の `zyuuuukak1n.dev`（`/var/www/html/`）に一切干渉しないよう、独立した `ServerName dai2flix.zyuuuukak1n.dev` のVirtualHost（`/etc/apache2/sites-available/dai2flix.conf`）を新設。SPAルーティング（`FallbackResource`）と機密ファイル遮断をWebサーバー層で強制。 |
| **バックエンド** | **FastAPI + Uvicorn (systemd 常駐)** | 非同期高速処理、Pydanticによる厳格な入出力バリデーション、N+1問題を抑止するSQLAlchemy 2.0を採用。systemdで自動復旧・サンドボックス化。 |
| **データベース** | **SQLite (WALモード有効化)** | 既存のDBサーバーに影響を与えない単一ファイル完結型。WALモードにより、cronバッチ書き込み中もWeb読み込みがブロックされない高並行性を担保。 |
| **データ同期バッチ** | **Python (cron 毎日深夜3時実行)** | YouTube APIクオータ消費を最小化（`search.list`完全排除、`playlists.list` / `playlistItems.list` / `videos.list` のみ使用）。Gemini APIは新着動画検知時のみ1回実行し、コストとクオータを保護。多重起動はPID検証付きファイルロック（`BatchLock`）で防止。 |
| **フロントエンド** | **React + Tailwind CSS (SPA)** | Netflixの漆黒テーマ・マイクロインタラクションを再現。パーソナライズはブラウザの `localStorage` で処理し、ユーザー認証テーブルを作らないことで保守工数ゼロ・個人情報リスクゼロを実現。 |

---

## STEP 3: 既存環境チェックとホスティング環境のセットアップ

自宅のUbuntu Server上で以下の作業を実行します。

### 3-1. 既存ポート衝突の事前確認（非干渉チェック）
バックエンドFastAPIがデフォルトで使用するポート `8000` が、既に他のサービスで使用されていないか確認します。

```bash
# 8000番ポートの使用状況を確認
sudo ss -tulpn | grep :8000
# または
sudo lsof -i :8000
```
- **何も表示されなければOKです（8000番が利用可能）。**
- ※もし既に別のアプリが8000番を使用している場合は、後述の「ポート番号の変更手順」に従って `8008` 等の空きポートに変更してください。

### 3-2. 必要なパッケージとApacheモジュールの確認
既にApache2が稼働中の環境のため、必要なモジュールが有効になっているか確認し、不足しているものだけを有効化します。

```bash
# 必要なApacheモジュールを有効化（既に有効な場合はスキップされます）
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo a2enmod rewrite
sudo a2enmod headers
sudo a2enmod deflate

# 設定構文をチェックしてからApacheをリロード
sudo apache2ctl configtest
sudo systemctl reload apache2
```

### 3-3. プロジェクトコードの配置（独立ディレクトリ）
既存の `/var/www/html/` とは完全に分離された `/var/www/dai2flix/` を作成します。

```bash
# 独立ディレクトリの作成
sudo mkdir -p /var/www/dai2flix
sudo chown -R $USER:$USER /var/www/dai2flix

# リポジトリのクローン
git clone https://github.com/your-username/dai2flix.git /var/www/dai2flix
cd /var/www/dai2flix
```

### 3-4. Python仮想環境と依存関係のセットアップ

```bash
cd /var/www/dai2flix
python3 -m venv .venv
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r backend/requirements.txt
```

### 3-5. フロントエンドのビルド

```bash
cd /var/www/dai2flix/frontend
npm ci
npm run build

# ビルド成果物 (frontend/dist/) が存在することを確認
ls -la /var/www/dai2flix/frontend/dist
```

### 3-6. 環境変数（.env）の配置と systemd サービスの登録

FastAPIデーモンが起動時に参照する設定ファイル（`.env`）を作成し、systemdサービスを起動します。

```bash
# 1. .env.example から本番用 .env を作成
sudo cp /var/www/dai2flix/backend/.env.example /var/www/dai2flix/backend/.env

# 2. サービスユニットファイルの配置
sudo cp /var/www/dai2flix/infra/dai2flix-backend.service /etc/systemd/system/dai2flix-backend.service

# 3. ディレクトリおよび .env の所有権を www-data に付与（パーミッション 600）
sudo chown -R www-data:www-data /var/www/dai2flix
sudo chmod 600 /var/www/dai2flix/backend/.env

# 4. 必要に応じて .env を開き、実際の API キーを設定
# sudo nano /var/www/dai2flix/backend/.env

# 5. systemd デーモンのリロードと起動・自動起動有効化
sudo systemctl daemon-reload
sudo systemctl enable dai2flix-backend
sudo systemctl start dai2flix-backend

# 6. 正常起動の確認（Active: active (running) であること）
sudo systemctl status dai2flix-backend
```

> [!TIP]
> **万一起動に失敗した場合のログ確認コマンド**:
> `sudo journalctl -u dai2flix-backend.service -n 50 --no-pager`

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

# logrotateの構文チェック
sudo logrotate -d /etc/logrotate.d/dai2flix
```

---

## STEP 4: ドメイン公開とSSL/HTTPS化手順

既存のメインドメイン `https://zyuuuukak1n.dev/` を保護しながら、DAI2FLIXを公開する手順です。
**サブドメイン `dai2flix.zyuuuukak1n.dev` を用いる方式（プランA：大推奨）** を推奨します。

### プランA: サブドメイン `dai2flix.zyuuuukak1n.dev` による公開（推奨）

この方式は、既存の `zyuuuukak1n.dev`（`/var/www/html/`）の設定ファイルに**1行も変更を加えない**ため、既存Webサイトの停止・障害リスクがゼロになります。

#### 4-A-1. DNSレコードの追加
お使いのDNS管理サービス（Cloudflare、お名前.com、Route 53など）で、`zyuuuukak1n.dev` に以下のサブドメインレコードを追加します：

| レコードタイプ | ホスト名 / 名前 | 値 / コンテンツ | 備考 |
| :--- | :--- | :--- | :--- |
| **A** | `dai2flix` | 自宅サーバーのグローバルIPアドレス | ルーターでポート80/443がUbuntu Serverに向いていること |
| *(または CNAME)* | `dai2flix` | `zyuuuukak1n.dev` | 同一IPに向ける場合 |

※DNS反映を確認するコマンド:
```bash
dig +short dai2flix.zyuuuukak1n.dev
# 自宅サーバーのIPが返ってくれば反映完了
```

#### 4-A-2. Apache バーチャルホストの配置と有効化

```bash
# 設定ファイルを sites-available に配置
sudo cp /var/www/dai2flix/infra/apache-dai2flix.conf /etc/apache2/sites-available/dai2flix.conf

# 設定ファイル内の ServerName が dai2flix.zyuuuukak1n.dev になっていることを確認
grep "ServerName" /etc/apache2/sites-available/dai2flix.conf

# サイトの有効化
sudo a2ensite dai2flix.conf

# 既存サイトを含めてApache全体の設定構文をチェック
sudo apache2ctl configtest
# -> "Syntax OK" と表示されることを確認

# Apacheをリロード（既存サイトの中断なし）
sudo systemctl reload apache2
```

この時点で、`http://dai2flix.zyuuuukak1n.dev`（HTTP）でDAI2FLIXが表示され、`https://zyuuuukak1n.dev` は以前と全く変わらず `/var/www/html/` が表示される状態になります。

#### 4-A-3. Certbotによる無料SSL証明書取得（HTTPS化）
Let's Encrypt（Certbot）を用いて、サブドメイン専用のSSL証明書を取得し、HTTPS化します。

```bash
# Certbot を実行（Apacheプラグイン）
sudo certbot --apache -d dai2flix.zyuuuukak1n.dev
```

対話プロンプトでの選択:
- メールアドレスの入力（未登録の場合）
- 利用規約への同意（`Y`）
- HTTPSへの自動リダイレクト: `2: Redirect - Make all requests redirect to secure HTTPS access`（推奨）

Certbotが自動的に `/etc/apache2/sites-available/dai2flix-le-ssl.conf` を生成し、既存の `zyuuuukak1n.dev` のSSL証明書とは独立して管理されます。

```bash
# 証明書の自動更新テスト
sudo certbot renew --dry-run
```

---

### （参考）プランB: サブディレクトリ `https://zyuuuukak1n.dev/dai2flix/` で公開する場合

もしサブドメインを使用せず、既存のメインドメイン配下の `/dai2flix` パスで公開したい場合は、以下の手順となります。
*(※既存のVirtualHost設定ファイルを編集する必要があるため、必ずバックアップを取ってから作業してください)*

1. **既存のSSL設定ファイルをバックアップ**:
   ```bash
   sudo cp /etc/apache2/sites-available/000-default-le-ssl.conf /etc/apache2/sites-available/000-default-le-ssl.conf.bak
   ```
2. **既存の `<VirtualHost *:443>` 内にリバースプロキシとエイリアスを追記**:
   ```apache
   # フロントエンド静的ファイル
   Alias /dai2flix /var/www/dai2flix/frontend/dist
   <Directory /var/www/dai2flix/frontend/dist>
       Options -Indexes +FollowSymLinks
       AllowOverride None
       Require all granted
       FallbackResource /dai2flix/index.html
   </Directory>

   # バックエンドAPI
   ProxyPass /dai2flix/api/ http://127.0.0.1:8000/api/
   ProxyPassReverse /dai2flix/api/ http://127.0.0.1:8000/api/
   ```
3. **フロントエンドのベースパス設定**:
   `frontend/vite.config.ts` に `base: '/dai2flix/'` を設定し、`npm run build` を再実行して静的アセットの参照パスを合わせます。

---

## STEP 5: 環境変数（.env）の配置と設定

バックエンドの設定ファイルを作成し、厳格なパーミッションを付与します。

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

# サーバーバインド設定 (FastAPI)
HOST=127.0.0.1
PORT=8000
LOG_LEVEL=INFO
```

> [!TIP]
> **ポート8000が既存サービスで使用されていた場合**:
> 1. `backend/.env` の `PORT=8000` を `PORT=8008` 等に変更。
> 2. `infra/dai2flix-backend.service` の `--port 8000` を `--port 8008` に変更。
> 3. `infra/apache-dai2flix.conf` の `http://127.0.0.1:8000/` を `http://127.0.0.1:8008/` に変更。

設定反映のため、バックエンドを再起動します:
```bash
sudo systemctl restart dai2flix-backend
```

---

## STEP 6: CI/CD（GitHub Actions）の設定

本リポジトリには `.github/workflows/main.yml` が同梱されており、GitHubへPushすると自動的に以下が実行されます。

1. **Backend Tests**: Python 3.10, 3.11, 3.12 マトリックスでの全単体テスト・結合テスト。
2. **Frontend Build**: Node.js 20 での `npm ci` および TypeScript型チェック付き本番バンドルビルド。

単体テストはすべてモック化されているため、GitHub SecretsへのAPIキー登録なしでCIがグリーン（成功）になります。

---

## STEP 7: 動作確認・ヘルスチェック・トラブルシューティング

### 7-1. 初回データ同期バッチの手動実行
cronの深夜3時を待たずに、初回データを即座に収集・永続化します。

```bash
# www-data ユーザー権限で同期バッチを手動トリガー
sudo -u www-data /var/www/dai2flix/.venv/bin/python /var/www/dai2flix/backend/scripts/sync_batch.py
```

### 7-2. 各サイトの疎通確認（干渉チェック）

1. **既存サイトの正常性確認**:
   ```bash
   curl -I https://zyuuuukak1n.dev/
   # -> HTTP 200 OK が返り、既存の /var/www/html/ が正常に応答することを確認
   ```

2. **DAI2FLIX ヘルスチェックAPIの確認**:
   ```bash
   curl -s https://dai2flix.zyuuuukak1n.dev/api/health | jq .
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

3. **DAI2FLIX Web画面の確認**:
   ブラウザで `https://dai2flix.zyuuuukak1n.dev/` を開き、Billboardヒーローバナー、公式再生リスト行、AIタグ行、動画クリックでのYouTubeモーダル再生が正常に動作することを確認します。

### 7-3. 機密ファイル遮断のセキュリティ検証

Webブラウザまたは curl で、機密ファイルへのアクセスが **403 Forbidden** で遮断されることを確認します。

```bash
curl -I https://dai2flix.zyuuuukak1n.dev/.env
curl -I https://dai2flix.zyuuuukak1n.dev/backend/.env
curl -I https://dai2flix.zyuuuukak1n.dev/dai2flix.db
curl -I https://dai2flix.zyuuuukak1n.dev/.git/config
# -> すべて HTTP 403 Forbidden になれば合格
```

### 7-4. トラブルシューティング

| 症状 | 原因と対処法 |
| :--- | :--- |
| **`dai2flix.zyuuuukak1n.dev` にアクセスすると既存サイトが表示される** | Apacheの設定で `dai2flix.conf` が有効化されていないか、デフォルトVirtualHostが優先されています。<br>`sudo a2ensite dai2flix.conf` を実行し、`sudo apache2ctl -S` で VirtualHost の `ServerName` 一覧を確認してください。 |
| **APIアクセス時に 502 Bad Gateway** | FastAPIサービスが停止している可能性があります。<br>`sudo systemctl status dai2flix-backend`<br>`sudo journalctl -u dai2flix-backend -n 50` でログを確認してください。 |
| **同期バッチが起動しない / スキップされる** | 前回のプロセスが異常終了しロックファイルが残っている可能性があります。<br>`sudo -u www-data /var/www/dai2flix/.venv/bin/python /var/www/dai2flix/backend/scripts/sync_batch.py --force-unlock` を実行してロックを解除してください。 |
| **画面をリロードすると 404 Not Found になる** | ApacheのSPAルーティングが無効になっている可能性があります。<br>`/etc/apache2/sites-available/dai2flix.conf` 内の `FallbackResource /index.html` が有効か確認し、`sudo a2enmod rewrite && sudo systemctl reload apache2` を実行してください。 |

---

以上で、既存システム（`https://zyuuuukak1n.dev/`）に一切干渉することなく、DAI2FLIXの本番公開と完全放置運用が完了します。
