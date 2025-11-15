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

### 基本的な使い方（2段階実行）- 推奨

字幕を編集できる2段階実行がおすすめです。

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
# CROP_PERCENT=0         # 全方向を均等にクロップしたい場合に使用
# CROP_TOP_PERCENT=0
# CROP_BOTTOM_PERCENT=0
# CROP_LEFT_PERCENT=0
# CROP_RIGHT_PERCENT=0
```

3. **素材を準備（字幕生成まで）**

```bash
python main.py prepare config.txt
```

このコマンドで以下が実行されます：
- 動画のダウンロード・切り抜き
- Whisperで字幕生成 → `data/temp/subs_clip.srt`
- チャット取得・抽出
- チャットオーバーレイ生成

**処理が完了したら、字幕ファイルを編集します：**

```bash
# VSCodeやお好みのエディタで編集
code data/temp/subs_clip.srt
```

4. **動画を合成**

字幕編集後、以下のコマンドで動画を合成：

```bash
python main.py compose config.txt
```

完成した動画は `data/output/final.mp4` に出力されます。

**字幕を再編集したい場合**は、`subs_clip.srt` を編集して `compose` コマンドを再実行するだけです（実行時にスタイル付き `subs_clip.ass` が自動再生成されます）。

### フルパイプライン（字幕編集なし）

字幕編集が不要な場合は、全自動で実行できます：

```bash
python main.py run config.txt
```

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

### 高度な使い方：個別ステップ実行

各ステップを個別に実行することもできます。詳細は `python main.py -h` で確認してください。

**主要なステップ：**
- `step0`: 動画ダウンロード・切り抜き
- `step1`: Whisper字幕生成（モデルサイズ: tiny, base, small, medium, large）
- `step2`: チャット取得
- `step3`: チャット抽出
- `step4`: チャットオーバーレイ生成
- `step5`: 動画合成

**例**：
```bash
# Whisperモデルサイズを指定して字幕生成
python main.py step1 -i data/temp/clip.webm -o data/temp/subs_clip.srt -m medium

# 動画合成のみ実行
python main.py step5 -v data/temp/clip.webm -s data/temp/subs_clip.srt -c data/temp/chat_overlay.ass -o data/output/final.mp4
# SRTを指定すると自動的にASSへ変換され、既存の字幕スタイルが適用されます
```

## プロジェクト構造

```
KIRINUKI/
├── main.py                          # メインスクリプト
├── config.txt                       # 設定ファイル（サンプル）
├── requirements.txt                 # 依存パッケージ
├── README.md                        # ドキュメント
├── data/
│   ├── input/                       # 入力動画を配置
│   ├── output/                      # 完成動画の出力先（final.mp4）
│   └── temp/                        # 一時ファイル（subs_clip.srt等）
└── kirinuki_processor/              # 処理モジュール
    ├── steps/                        # 各処理ステップ
    ├── utils/                        # ユーティリティ
    └── tests/                        # テスト
```

## カスタマイズ

### Whisperモデルサイズ

字幕の精度と処理時間のバランスを調整できます：

- `tiny`, `base`: 高速だが精度低
- `small`: バランス型
- `medium`: 高精度
- `large`: 最高精度（推奨、デフォルト）

`main.py`内の`run_prepare_pipeline()`関数でモデルサイズを変更できます。

### チャット表示設定

[kirinuki_processor/steps/step5_generate_overlay.py](kirinuki_processor/steps/step5_generate_overlay.py)の`OverlayConfig`クラスで、ニコニコ動画風に右→左へ流れるコメントのレーン数・高さ・速度・フォントなどをカスタマイズできます。

### トリミング設定

`config.txt` の `CROP_PERCENT` を設定すれば、上下左右すべてを同じ割合でクロップできます。細かく調整したい場合は `CROP_TOP_PERCENT` など個別キーを使うことも可能です。`compose` 実行時には、指定された値を満たしたうえで上下左右を均等に切り詰め、最終映像のアスペクト比（16:9）を保つように自動調整されます。

### 動画エンコード設定

[kirinuki_processor/steps/step6_compose_video.py](kirinuki_processor/steps/step6_compose_video.py:18-22)の`compose_video`関数で、動画コーデック、品質、プリセットを変更できます。

## トラブルシューティング

### 依存関係のエラー

**FFmpegが見つからない**
→ [インストール](#インストール)セクションを参照してFFmpegをインストールしてください

**yt-dlpが見つからない**
→ `pip install yt-dlp` を実行してください

**Whisperが見つからない**
→ `pip install -r requirements.txt` を実行してください

### 処理エラー

**チャットリプレイが取得できない**
→ ライブ配信でない動画やチャットリプレイが無効化されている動画では取得できません。処理は字幕のみで続行されます。

**Whisper処理でメモリ不足**
→ `large`モデルは約10GBのVRAMが必要です。`medium`や`small`モデルを試してください：
```bash
python main.py step1 -i input.webm -o output.srt -m medium
```

**動画のダウンロードが遅い/失敗する**
→ 範囲指定ダウンロードが失敗する場合は、`step0`コマンドで`--full`オプションを使用してください。

## ライセンス

MIT License
