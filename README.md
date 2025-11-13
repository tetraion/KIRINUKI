# KIRINUKI Processor

ひろゆき動画の切り抜きに字幕とライブチャットを重ねて見やすくするツール

## 概要

このツールは以下の処理を自動化します：

1. YouTubeから指定時刻の動画を直接ダウンロード・切り抜き
2. Whisper（OpenAI）で音声認識による高精度字幕生成
3. YouTubeからライブチャットリプレイを取得
4. チャットを切り抜き区間で抽出・整形
5. チャットをライブチャット風のオーバーレイ（ASS字幕）として生成
6. 切り抜き動画に字幕とチャットオーバーレイを合成

## 必要な環境

- Python 3.8以上
- FFmpeg（動画合成・音声抽出用）
- yt-dlp（YouTube動画・チャット取得用）
- OpenAI Whisper（音声認識による字幕生成）

## インストール

### 1. リポジトリのクローン

```bash
cd /path/to/KIRINUKI
```

### 2. 仮想環境の作成（推奨）

```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# または
venv\Scripts\activate  # Windows
```

### 3. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 4. FFmpegのインストール

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Windows:**
[FFmpeg公式サイト](https://ffmpeg.org/download.html)からダウンロード

## 使い方

### 基本的な使い方（フルパイプライン）- 推奨

1. **設定ファイルの作成**

```bash
python main.py init -o config.txt
```

2. **設定ファイルを編集**

`config.txt` を開いて、以下の情報を入力：

```
VIDEO_URL=https://www.youtube.com/watch?v=xxxxxxxxxxxxx
START_TIME=00:05:30
END_TIME=00:10:45
AUTO_DOWNLOAD=true
```

3. **処理を実行**

```bash
python main.py run config.txt
```

完成した動画は `data/output/final.mp4` に出力されます。

**これだけでOK！** 動画のダウンロード、切り抜き、字幕・チャットの取得、合成まで全て自動で行われます。

### 既存の切り抜き動画を使う場合

すでに切り抜き済みの動画がある場合：

```
VIDEO_URL=https://www.youtube.com/watch?v=xxxxxxxxxxxxx
START_TIME=00:05:30
END_TIME=00:10:45
AUTO_DOWNLOAD=false
WEBM_PATH=data/input/clip.webm
```

`AUTO_DOWNLOAD=false` に設定し、`WEBM_PATH` で既存ファイルを指定します。

### ステップごとの実行

各ステップを個別に実行することもできます：

#### ステップ0: 動画ダウンロード・切り抜き

```bash
python main.py step0 https://www.youtube.com/watch?v=xxxxx \
  -s 00:05:30 \
  -e 00:10:45 \
  -o data/temp/clip.webm
```

範囲指定ダウンロードが失敗する場合は `--full` オプションで全体ダウンロード:

```bash
python main.py step0 https://www.youtube.com/watch?v=xxxxx \
  -s 00:05:30 \
  -e 00:10:45 \
  -o data/temp/clip.webm \
  --full
```

#### ステップ1: Whisper字幕生成

切り抜き済み動画から音声認識で字幕を生成：

```bash
python main.py step1 \
  -i data/temp/clip.webm \
  -o data/temp/subs_clip.srt \
  -m large
```

モデルサイズのオプション:
- `tiny`, `base`: 高速だが精度低
- `small`: バランス型
- `medium`: 高精度
- `large`: 最高精度（推奨、デフォルト）

#### ステップ2: チャット取得

```bash
python main.py step2 https://www.youtube.com/watch?v=xxxxx -o data/temp/chat_full.json
```

#### ステップ3: チャット抽出

```bash
python main.py step3 \
  -i data/temp/chat_full.json \
  -o data/temp/chat_clip.json \
  -s 00:05:30 \
  -e 00:10:45
```

#### ステップ4: オーバーレイ生成

```bash
python main.py step4 \
  -i data/temp/chat_clip.json \
  -o data/temp/chat_overlay.ass
```

#### ステップ5: 動画合成

```bash
python main.py step5 \
  -v data/temp/clip.webm \
  -o data/output/final.mp4 \
  -s data/temp/subs_clip.srt \
  -c data/temp/chat_overlay.ass
```

## プロジェクト構造

```
KIRINUKI/
├── main.py                          # メインスクリプト
├── config.txt                       # 設定ファイル（サンプル）
├── requirements.txt                 # 依存パッケージ
├── README.md                        # このファイル
├── data/
│   ├── input/                       # 入力動画を配置
│   ├── output/                      # 完成動画の出力先
│   └── temp/                        # 一時ファイル
└── kirinuki_processor/
    ├── __init__.py
    ├── steps/                        # 各処理ステップ
    │   ├── step0_config.py           # 設定読み込み
    │   ├── step0_download_clip.py    # 動画ダウンロード・切り抜き
    │   ├── step1_generate_subtitles.py # Whisper字幕生成
    │   ├── step3_fetch_chat.py       # チャット取得
    │   ├── step4_extract_chat.py     # チャット抽出
    │   ├── step5_generate_overlay.py # オーバーレイ生成
    │   └── step6_compose_video.py    # 動画合成
    ├── utils/                        # ユーティリティ
    │   └── time_utils.py             # 時間変換
    └── tests/                        # テスト
        ├── test_time_utils.py
        └── test_config.py
```

## テスト実行

```bash
# 全テストを実行
python -m pytest kirinuki_processor/tests/

# 特定のテストを実行
python -m pytest kirinuki_processor/tests/test_time_utils.py

# カバレッジ付きで実行
python -m pytest --cov=kirinuki_processor kirinuki_processor/tests/
```

## オプション設定

### チャット表示のカスタマイズ

`kirinuki_processor/steps/step5_generate_overlay.py` の `OverlayConfig` クラスで、
以下の設定をカスタマイズできます：

- `video_width`, `video_height`: 動画解像度
- `chat_area_width`: チャット表示エリアの幅
- `font_size`: フォントサイズ
- `text_color`, `author_color`: テキスト・投稿者名の色
- `message_display_duration`: メッセージ表示時間

### 動画エンコード設定

`kirinuki_processor/steps/step6_compose_video.py` の `compose_video` 関数で、
以下のエンコード設定をカスタマイズできます：

- `video_codec`: 動画コーデック（デフォルト: libx264）
- `preset`: エンコードプリセット（ultrafast, fast, medium, slow, veryslow）
- `crf`: 品質設定（0-51、低いほど高品質、デフォルト: 23）

## トラブルシューティング

### FFmpegが見つからない

```
✗ ffmpeg is not installed.
```

→ FFmpegをインストールしてください（上記「インストール」参照）

### yt-dlpが見つからない

```
✗ yt-dlp is not installed.
```

→ `pip install yt-dlp` を実行してください

### 字幕が取得できない

一部の動画には字幕が提供されていない場合があります。
その場合、字幕なしで処理が続行されます。

### チャットリプレイが取得できない

ライブ配信でない動画やチャットリプレイが無効化されている動画では、
チャットを取得できません。その場合、チャットなしで処理が続行されます。

### 動画のダウンロードが遅い

デフォルトでは範囲指定ダウンロードを試みますが、一部の動画では全体ダウンロードが必要な場合があります。
設定ファイルで個別に指定することはできませんが、ステップ0を手動実行する際に `--full` オプションを使用できます。

### ダウンロードした動画の品質

yt-dlpのデフォルト設定では、可能な限り高品質なwebm形式でダウンロードします。
特定の品質やフォーマットが必要な場合は、`step0_download_clip.py` の `video_format` パラメータをカスタマイズしてください。

## ライセンス

MIT License

## 作者

KIRINUKI Processor Development Team

## 貢献

バグ報告や機能要望は、GitHubのIssuesでお願いします。
