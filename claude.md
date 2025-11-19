# KIRINUKI Processor - 仕様書

## 目的

ひろゆきの動画の切り抜きに、Whisper生成の高精度字幕とライブチャットを重ねて見やすくする。

## 処理フロー

### ステップ0：動画のダウンロードと切り抜き

**説明**：YouTubeから指定した時刻の動画を直接ダウンロードして切り抜く。

**入力**：
- 動画URL（例：`https://www.youtube.com/watch?v=xxxxx`）
- 切り抜き開始時刻 START（必須、形式：`hh:mm:ss`）
- 切り抜き終了時刻 END（推奨、形式：`hh:mm:ss`）

**出力**：
- `clip.webm`（切り抜き済み動画、16:9）

**技術**：
- yt-dlpで動画をダウンロード
- 範囲指定ダウンロード（失敗時は全体ダウンロード後にFFmpegで切り抜き）

---

### ステップ1：Whisperによる字幕生成

**説明**：OpenAI Whisperを使用して切り抜き動画から音声認識により高精度な字幕を生成する。

**入力**：
- `clip.webm`（切り抜き済み動画）

**出力**：
- `subs_clip.srt`（生成された字幕、切り抜き0秒基準）
- `subs_clip.ass`（スタイル付き字幕、自動生成）

**技術**：
- OpenAI Whisper（音声認識モデル）
- デフォルト：`large`モデル（最高精度）
- 他のモデル：`tiny`, `base`, `small`, `medium`
- 言語：日本語（`ja`）
- 出力形式：SRT（SubRip）、ASS（Advanced SubStation Alpha）

**字幕スタイル（ASS）**：
- フォント：Hiragino Sans 110px
- 色：白文字（`&H00FFFFFF`）、黒アウトライン（7px）
- 配置：画面下部中央、縦マージン40px
- 自動改行：20文字を超える場合、句読点で2行に分割

**備考**：
- 切り抜き済み動画を入力するため、タイムスタンプは0秒起点で生成される
- YouTube字幕より精度が高い（特にlargeモデル）
- 処理時間：5分動画でlargeモデル10-20分程度（CPU環境）
- SRTを編集後、compose時に自動的にASSへ再変換される

---

### ステップ2：ライブチャット（リプレイ）の取得

**説明**：YouTubeのライブチャットリプレイを全量取得する。

**入力**：
- 動画URL

**出力**：
- `chat_full.json`（チャットがある場合）
- チャットリプレイなしのメモ（チャットがない場合）

**技術**：
- yt-dlpでライブチャットを取得（`--write-subs --sub-langs live_chat`）
- JSON形式で出力

---

### ステップ3：チャットの区間抽出・整形

**説明**：取得したチャットからSTART〜END区間のメッセージを抽出し、切り抜き基準に時刻を調整する。

**処理内容**：
- START〜ENDの範囲内のチャットメッセージのみ抽出
- タイムスタンプをSTARTを0秒として調整
- CHAT_DELAY_SECONDSによる表示タイミング調整（オプション）
- 読みやすいJSON配列形式に正規化

**チャット表示タイミング調整**：
- `CHAT_DELAY_SECONDS`：チャット表示のオフセット（秒）
- 正の値：チャットを早く表示（配信のディレイでチャットが遅れている場合）
- 負の値：チャットを遅く表示（チャットが早すぎる場合）
- デフォルト：0（調整なし）
- 例：`CHAT_DELAY_SECONDS=16` → チャットを16秒早く表示

**入力**：
- `chat_full.json`（全チャット）
- START時刻（必須）
- END時刻（推奨）
- CHAT_DELAY_SECONDS（任意、デフォルト: 0）

**出力**：
- `chat_clip.json`（切り抜き区間のチャット）

**形式**：
```json
[
  {
    "message": "コメント内容",
    "author": "投稿者名",
    "time_in_seconds": 12.5
  }
]
```

---

### ステップ4：チャット表示用オーバーレイの生成

**説明**：チャットメッセージをニコニコ動画風に表示するためのASS字幕オーバーレイを作成する。

**デザイン仕様（ニコニコ動画風）**：
- 画面を横切る流れるコメント（右→左）
- レーン方式で複数のコメントを同時表示（デフォルト：6レーン）
- レーン配置：画面上部（Y=260px〜、タイトルバーと被らない）
- レーン間隔：70px（下部の字幕を避ける）
- コメント速度：380px/秒
- レーン割り当て：最も早く空くレーンを選択
- レーン再利用：前のコメント終了後0.25秒の余白

**表示設定**：
- フォント：Hiragino Sans 55px
- 色：白文字（`&H00FFFFFF`）、黒アウトライン（3px）
- メッセージのみ表示（投稿者名なし）
- 開始位置：画面右端 + 80px（オフスクリーン）
- 終了位置：コメント幅分だけ画面左外

**入力**：
- `chat_clip.json`（切り抜き区間のチャット）

**出力**：
- `chat_overlay.ass`（ASS形式の字幕オーバーレイ）

**技術**：
- ASS（Advanced SubStation Alpha）形式で作成
- タイムスタンプ形式：`h:mm:ss.cc`
- アニメーション：`\move(x1,y1,x2,y2)`タグで横スクロール
- 表示時間：コメント幅と速度から自動計算

---

### ステップ4.5：タイトルバー生成（任意）

**説明**：設定ファイルで`TITLE`が指定されている場合、画面上部にスライドインアニメーション付きのタイトルバーを生成する。

**入力**：
- `TITLE`（設定ファイルで指定）

**出力**：
- `title_bar.ass`（ASS形式のタイトルバー）

**デザイン仕様**：
- **タイトルバー背景**：黄色（`&H0000E5FF`、RGB(255,229,0)）、高さ120px、Y=10px
- **タイトルテキスト**：Hiragino Sans 90px、黒文字、白アウトライン（5px）
- **チャンネル名背景**：青色（`&H00D77800`、RGB(0,120,215)）、高さ60px
- **チャンネル名**：「ひろゆき視点」、Hiragino Sans W9 48px、白文字、濃いグレーアウトライン（4px）
- **アニメーション**：左から右へスライドイン（1.2秒）
- **配置**：ロゴ中心（X=105px）から画面右端まで展開
- **表示時間**：動画終了まで表示（display_duration=Noneの場合）

**技術**：
- ASS（Advanced SubStation Alpha）形式で作成
- `\clip()`タグでクリップ範囲を制御
- `\t()`タグでアニメーション（クリップ範囲を徐々に拡大）
- Layer構造：0=タイトルバー背景、1=タイトル文字、2=チャンネル名背景、3=チャンネル名文字

---

### ステップ5：動画合成（字幕＋チャットオーバーレイ＋タイトルバー＋ロゴ）

**説明**：切り抜き動画に、Whisper字幕、チャットオーバーレイ、タイトルバー、ロゴを重ねて最終動画を生成する。

**入力**：
- `clip.webm`（切り抜き済み動画）
- `subs_clip.ass`（Whisper生成字幕、スタイル付き）
- `chat_overlay.ass`（チャットオーバーレイ、任意）
- `title_bar.ass`（タイトルバー、TITLEが設定されている場合）
- `data/input/ひろゆき視点【切り抜き】.png`（ロゴ画像、任意）

**出力**：
- `final.mp4`（完成品、1920x1080）

**処理フロー**：
1. **クロップ**（CROP_*_PERCENTが設定されている場合）
   - 上下左右を指定パーセンテージでクロップ
   - アスペクト比16:9を維持するよう自動調整
2. **スケール**：1920x1080にリサイズ
3. **ロゴ合成**：画面左上（X=15px, Y=10px）に円形ロゴを配置（高さ180px）
4. **字幕合成**：`subs_clip.ass`を適用
5. **チャットオーバーレイ合成**：`chat_overlay.ass`を適用
6. **タイトルバー合成**：`title_bar.ass`を適用

**技術**：
- FFmpegで合成
- H.264エンコード（CRF 23、medium preset）
- フィルター：`crop`, `scale`, `overlay`, `subtitles`, `ass`

**FFmpegコマンド例**：
```bash
ffmpeg -i clip.webm -i logo.png \
  -filter_complex "[0:v]crop=...,scale=1920:1080,subtitles=subs_clip.ass,ass=chat_overlay.ass,ass=title_bar.ass[v_base];[1:v]scale=180:180,format=rgba,...[logo];[v_base][logo]overlay=15:10" \
  -c:v libx264 -preset medium -crf 23 \
  -c:a aac final.mp4
```

---

### ステップ6：YouTube説明欄生成（任意）

**説明**：Whisper生成字幕（SRT）からトランスクリプトを抽出し、Groq APIを使用してYouTube説明欄の文章を自動生成する。

**入力**：
- `subs_clip.srt`（Whisper生成字幕）
- `data/input/setumei`（プロンプトテンプレート）
- `.env.local`（Groq APIキー）

**出力**：
- `description.txt`（生成されたYouTube説明欄、Markdown形式）

**生成内容**：
- 動画概要タイトル（20〜40文字）
- 動画の要点・議題・主張のまとめ（2〜4行）
- 元動画リンク（手動差し替え用プレースホルダー）
- チャンネル説明（固定テキスト）
- おすすめ関連動画（3つ）
- 自動生成ハッシュタグ（5〜8個）

**技術**：
- Groq API（高速LLM推論）
- デフォルトモデル：`llama-3.3-70b-versatile`
- プロンプトエンジニアリング：SEO最適化、自然な文体

**備考**：
- compose時に自動実行される（字幕が存在する場合）
- APIキーは`.env.local`に`GROQ_API_KEY=xxx`の形式で設定
- 全体で300〜600文字程度に自動調整
- プロンプトテンプレートはカスタマイズ可能

---

## コマンドリファレンス

### メインコマンド

**`run`**：全自動実行（素材準備→動画合成を一括実行）
```bash
python main.py run config.txt
```

**`prepare`**：素材準備のみ（動画ダウンロード、字幕生成、チャット取得まで）
```bash
python main.py prepare config.txt
```

**`compose`**：動画合成のみ（prepareで生成した素材から最終動画を作成）
```bash
python main.py compose config.txt
```

**`output`**：完成動画とconfigをタイトル名のフォルダに保存
```bash
python main.py output config.txt
```
- 用途：完成した動画を整理保存（config.txtも一緒に保存されるため後から設定を確認可能）
- 実行内容：`data/output/{TITLE}/` フォルダを作成し、以下をコピー
  - `final.mp4`
  - `description.txt`（存在する場合）
  - `config.txt`
- 注意：TITLEが設定されていない場合はエラーになります

### 便利コマンド

**`resub`**：字幕のみ再生成（Whisperによる音声認識をやり直す）
- 用途：Whisper字幕に問題がある場合（文字起こしミス、タイミングずれ等）
- 実行内容：`subs_clip.srt`と`subs_clip.ass`を再生成
```bash
python main.py resub config.txt
```

**`rechat`**：チャットオーバーレイのみ再生成（チャット表示タイミングを調整）
- 用途：`CHAT_DELAY_SECONDS`を変更した後、チャットのタイミングだけ再調整したい場合
- 実行内容：`chat_clip.json`と`chat_overlay.ass`を再生成（元動画やWhisper字幕は再生成しない）
```bash
# 1. config.txtのCHAT_DELAY_SECONDSを変更
# 2. チャットオーバーレイを再生成
python main.py rechat config.txt

# 3. 動画合成
python main.py compose config.txt
```

**`step1.5`**：字幕修正（AI自動補正）- 手動実行のみ
- 用途：Whisper字幕の誤字脱字、句読点、改行を手動で修正したい場合
- 実行内容：`subs_clip.srt`をLLMで補正し、`subs_clip_fixed.srt`を生成
- 注意：このコマンドは自動ワークフロー（prepare/compose）には含まれていません
```bash
python main.py step1.5 config.txt
```

---

## 推奨ワークフロー

### 方法1：2段階実行（字幕編集あり）- 推奨

```bash
# 1. 素材準備（字幕生成まで実行、動画合成はしない）
python main.py prepare config.txt

# 2. 字幕を編集
code data/temp/subs_clip.srt

# 3. 動画合成
python main.py compose config.txt

# 4. タイトル名のフォルダに保存（任意）
python main.py output config.txt
```

### 方法2：全自動実行（字幕編集なし）

```bash
python main.py run config.txt

# タイトル名のフォルダに保存（任意）
python main.py output config.txt
```

### 方法3：チャットタイミング調整

```bash
# 1. 素材準備
python main.py prepare config.txt

# 2. 動画合成（チャットタイミングが合わない場合）
python main.py compose config.txt

# 3. config.txtのCHAT_DELAY_SECONDSを調整（例: 16秒早くしたい → 16）
code config.txt

# 4. チャットオーバーレイのみ再生成
python main.py rechat config.txt

# 5. 動画合成
python main.py compose config.txt

# 6. タイトル名のフォルダに保存（任意）
python main.py output config.txt
```

### 方法4：Whisper字幕再生成

```bash
# Whisper字幕に問題がある場合
python main.py resub config.txt
python main.py compose config.txt

# タイトル名のフォルダに保存（任意）
python main.py output config.txt
```

---

## 技術スタック

- **Python 3.8+**：メイン言語
- **OpenAI Whisper**：音声認識による字幕生成
- **PyTorch**：Whisperの実行環境
- **yt-dlp**：動画・チャットのダウンロード
- **FFmpeg**：動画の切り抜きと合成、音声抽出
- **pytest**：テスト

---

## ディレクトリ構成

```
data/
├── input/          # 入力ファイル
│   ├── ひろゆき視点【切り抜き】.png  # ロゴ画像（任意）
│   └── setumei                       # YouTube説明欄プロンプトテンプレート
├── temp/           # 一時ファイル
│   ├── clip.webm
│   ├── subs_clip.srt        # Whisper生成字幕（SRT）
│   ├── subs_clip.ass        # Whisper生成字幕（ASSスタイル付き）
│   ├── chat_full.json
│   ├── chat_clip.json
│   ├── chat_overlay.ass     # ニコニコ風チャットオーバーレイ
│   └── title_bar.ass        # タイトルバー（TITLEが指定されている場合）
└── output/         # 完成動画
    ├── final.mp4            # 最終出力（1920x1080）
    └── description.txt      # YouTube説明欄（自動生成）
```

---

## 設定ファイル（config.txt）

### 基本設定（自動ダウンロード）

```
VIDEO_URL=https://www.youtube.com/watch?v=xxxxx
START_TIME=00:05:30
END_TIME=00:10:45
AUTO_DOWNLOAD=true
TITLE=動画のタイトル（任意）
```

### クロップ設定

```
# 全方向を均等にクロップする場合
CROP_PERCENT=5.0

# または、個別に設定する場合
CROP_TOP_PERCENT=5.0
CROP_BOTTOM_PERCENT=5.0
CROP_LEFT_PERCENT=3.0
CROP_RIGHT_PERCENT=3.0
```

**注意**：
- `CROP_PERCENT`を設定すると、上下左右すべてが同じ割合でクロップされます
- 個別設定（`CROP_TOP_PERCENT`など）も可能です
- クロップ後、アスペクト比16:9を維持するよう自動調整されます

### 既存動画を使用する場合

```
VIDEO_URL=https://www.youtube.com/watch?v=xxxxx
START_TIME=00:05:30
END_TIME=00:10:45
AUTO_DOWNLOAD=false
WEBM_PATH=data/input/clip.webm
```

### チャット表示タイミング調整

```
# チャットが遅れている場合（配信のディレイ）
CHAT_DELAY_SECONDS=16  # チャットを16秒早く表示

# チャットが早すぎる場合
CHAT_DELAY_SECONDS=-10  # チャットを10秒遅く表示
```

**注意**：
- 配信のディレイでチャットが映像より遅れている場合、正の値を指定してチャットを早く表示します
- チャットが映像より早すぎる場合、負の値を指定してチャットを遅く表示します
- デフォルト：0（調整なし）

### 完全な設定例

```
VIDEO_URL=https://www.youtube.com/watch?v=xxxxx
START_TIME=00:05:30
END_TIME=00:10:45
TITLE=ヤマトがベトナム人運転手500人採用
AUTO_DOWNLOAD=true
CROP_PERCENT=5.0
CHAT_DELAY_SECONDS=16
OUTPUT_DIR=data/output
TEMP_DIR=data/temp
```

---

## 実装上の注意点

### 字幕形式（SRT）

```
1
00:00:00,000 --> 00:00:03,500
字幕テキスト1行目

2
00:00:04,000 --> 00:00:07,200
次の字幕
```

- タイムスタンプ形式：`hh:mm:ss,mmm`
- ミリ秒はカンマ区切り
- Whisperが自動生成

### Whisperモデルサイズ

| モデル | パラメータ数 | 必要VRAM | 速度 | 精度 |
|--------|------------|---------|------|------|
| `tiny` | 39M | ~1GB | 最速 | 低 |
| `base` | 74M | ~1GB | 速い | やや低 |
| `small` | 244M | ~2GB | 普通 | 普通 |
| `medium` | 769M | ~5GB | やや遅い | 高 |
| `large` | 1550M | ~10GB | 遅い | **最高（推奨）** |

---

## エラーハンドリング

- Whisper字幕生成失敗時：字幕なしで処理続行
- チャットが取得できない場合：チャットなしで処理続行
- 範囲指定ダウンロード失敗時：全体ダウンロードにフォールバック
- メモリ不足時：小さいモデル（medium/small）を使用

---

## 変更履歴

- **2025-11-18**：チャット表示タイミング調整機能とクイックコマンド追加
  - チャット表示タイミング調整機能を追加（`CHAT_DELAY_SECONDS`設定）
    - 正の値でチャットを早く表示（配信ディレイ対応）
    - 負の値でチャットを遅く表示（チャット先行対応）
  - 字幕再生成コマンド追加（`resub`）
    - Whisper字幕のみ再生成（文字起こしミス修正用）
  - チャットオーバーレイ再生成コマンド追加（`rechat`）
    - チャットタイミング調整後の再生成用
  - チャット冒頭10秒非表示のハードコード削除
    - 切り抜き冒頭からチャットを表示可能に
  - Step 1.5（字幕AI補正）をワークフローから除外
    - 手動実行のみに変更（`python main.py step1.5`）

- **2025-11-17**：AI生成機能の追加
  - YouTube説明欄自動生成機能を追加（`step7_generate_description.py`）
  - Groq API統合（高速LLM推論）
  - プロンプトテンプレートのカスタマイズ機能
  - `.env.local`による環境変数管理
  - compose時に自動実行（字幕が存在する場合）

- **2025-11-15**：UI/UX機能拡張
  - タイトルバー生成機能を追加（`step_title_bar.py`）
  - ニコニコ動画風の横スクロールチャット表示に変更（従来の右側固定表示から変更）
  - ロゴ画像の合成機能を追加（円形ロゴ、画面左上）
  - クロップ機能を追加（CROP_*_PERCENT設定）
  - ASS字幕スタイルの自動生成・再生成機能
  - 設定ファイルにTITLEパラメータを追加

- **2025-11-14**：Whisperベースに全面刷新
  - YouTube字幕取得を削除
  - Whisper音声認識による字幕生成を追加
  - 2段階ワークフロー（prepare/compose）を追加
  - 字幕のリベース処理を削除（Whisperが切り抜き動画から直接生成）

- **2025-11-13**：初版作成
  - KirinukiDB依存を削除
  - yt-dlpによる動画ダウンロード機能を追加
  - chat-downloaderをyt-dlpに置き換え
