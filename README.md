# 履修の手引き読解支援システム

入学年度別の履修の手引きを、段階的な検索、根拠付き回答、PDFハイライト、匿名集合知とともに閲覧する教材アプリです。WebMCPは使用しません。

> **現在のフェーズ: コンセプト確認用のクラウド無料枠構成。** Docker/Ollama/ローカルDBは前提とせず、
> Vercel（Web + API、どちらもVercelプロジェクト）+ Supabase（DB）+ Cohere API（生成AI/Embedding/
> Rerank、無料トライアル）だけで動作します。APIはVercel Python Serverless Functionsとして
> `api/`をデプロイします。長時間実行が心配な場合はRender（`render.yaml`同梱）に差し替え可能です。

## 学生向けの使い方

デプロイ済みのURL（教員から共有されます）をブラウザで開くだけです。インストールは不要です。
Stage 1とStage 2はCohere側の障害・レート制限時でも動作するようフォールバックされます。

## 6段階の検索

1. 質問文そのままの文字列検索
2. `api/data/search_lexicon.yaml`による学生語の制度用語への展開
3. Cohere Chat APIによる検索語追加
4. Embedding（Cohere Embed）と文字検索の統合
5. Cohere Rerank APIによる再順位付け
6. 根拠に限定した回答生成（Cohere Chat）

辞書を編集した後は再デプロイ（Renderの自動デプロイ、または`mise run restart`でローカル反映）で反映できます。PDFの再取り込みやEmbeddingの再生成は不要です。

## クラウドAI構成

- Cohere Chat: 検索語生成と根拠付き回答
- Cohere Embed（多言語モデル）: 意味検索
- Cohere Rerank（多言語モデル）: 上位候補のRerank
- Supabase PostgreSQL + pgvector: 作成済みEmbeddingの保存

Cohereの無料トライアルキーにはレート制限があります。制限に達した場合はStage1-2の結果にフォールバックします。

## 教員・開発者向け: ローカル開発

必要なのは[mise](https://mise.jdx.dev/)と、Supabaseプロジェクト・Cohere APIキーです（どちらも無料枠で作成可能）。Docker Desktopは不要です。

```bash
mise install
cp .env.example .env
# .env に Supabase の DATABASE_URL と COHERE_API_KEY を設定してください
mise run setup
```

2回目以降は`mise run start`（バックグラウンド起動）または`mise run dev`（フォアグラウンド）、終了時は`mise run stop`です。ブラウザで http://localhost:3000 を開きます。

`mise run status`で状態確認、`mise run ingest`でPDF再取り込み、`mise run reembed`で全Embeddingを再生成できます。`mise run test`はAPI/Webテストとproduction buildを実行します。

## クラウドへのデプロイ

初回は次の順序で進めると環境変数の行き来がスムーズです。Vercel上に**2つのプロジェクト**（web用・api用）を作る点に注意してください。

1. **Supabase**: プロジェクトを作成（または既存のものを使用）し、Database の接続文字列（`postgresql+psycopg://...`形式に直したもの）を控えます。`vector`拡張は`mise run setup`（`alembic upgrade head`）が有効化するので事前作業は不要です。
2. **Cohere**: https://dashboard.cohere.com/api-keys で無料トライアルキーを取得します。
3. **Vercel（API）**: このリポジトリをインポートし、Root Directory を`api`にしたプロジェクトを作成します（Vercel Python Serverless Functionsとして`api/api/index.py`がエントリポイントになります）。環境変数に`DATABASE_URL`・`COHERE_API_KEY`・`ADMIN_PASSWORD`・`ADMIN_SESSION_SECRET`を設定してください（`CORS_ALLOW_ORIGINS`は手順5で設定）。デプロイ後のURL（`https://xxx.vercel.app`）を控えます。
   - 代わりにRenderを使う場合: ルートの`render.yaml`（Blueprint）で`api/`をWeb Serviceとしてデプロイできます。常時起動したいとき・実行時間制限が気になるときはこちらを推奨します。
4. **Vercel（Web）**: 同じリポジトリで、Root Directory を`web`にした別プロジェクトを作成します。環境変数`NEXT_PUBLIC_API_BASE_URL`に手順3のURLを設定してデプロイします。デプロイ後のURL（`https://xxx.vercel.app`）を控えます。
5. **APIのCORSを更新**: 手順3のプロジェクトの`CORS_ALLOW_ORIGINS`に手順4のVercel URLを設定し、再デプロイします。管理者ログインはWeb/APIが別ドメインになるため、Cookieは`SameSite=None; Secure`で発行されます（HTTPS必須。ローカルの`http://localhost`では管理者ログインは動作しません）。
6. **PDF取り込み・Embedding生成**: ローカルの`.env`に手順1・2の値を設定し、`mise run setup`（初回）または`mise run ingest && mise run reembed`（再取り込み時）を実行します。本番のSupabase DBに直接書き込む運用のため、デプロイ済みAPI側でPyMuPDF処理やEmbedding生成を都度実行することはありません。

## 構成

- `web`: Next.js、PDF.js、検索・閲覧UI
- `api`: FastAPI、PyMuPDF、検索・回答・集計API（Cohere API呼び出しを含む）
- `web/public/handbook`: 2022〜2026年度PDF（Next.jsが静的配信。Vercel Python Functionsは
  自プロジェクトのルート外のファイルを含められないため、APIではなくここに置いています）
- `api/data/search_lexicon.yaml`: 学生語→制度用語の辞書（APIが検索時に読むためapi/配下に配置）
- `data/evaluation.json`: 教員用評価質問の雛形
- `AGENTS.md`, `api/AGENTS.md`, `web/AGENTS.md`: コーディングエージェント向け指示

API仕様はローカル起動後 http://localhost:8000/docs で確認できます。

## 検索改善ダッシュボード

学生は検索候補の適否とAI回答の解決度を評価できます。教員は`/admin`から、年度・カテゴリ別の指標（検索回数、評価件数、役立った割合、解決した割合）、低評価の質問一覧、個別の検索トレース（`/api/admin/search-traces/{search_query_id}`、各Stageの検索語・件数）を確認でき、評価データをCSVでエクスポートできます。

`.env`の次の2項目は、共有前に必ず独自の値へ変更してください。未設定の場合、管理APIは無効です。

```dotenv
ADMIN_PASSWORD=change-this-for-class
ADMIN_SESSION_SECRET=change-this-to-a-long-random-string
```

変更後は再デプロイ（ローカルは`mise run restart`）で反映します。管理者セッションは8時間で失効し、CSVや管理APIに匿名端末IDは出力されません。
