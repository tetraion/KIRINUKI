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

**技術**：
- OpenAI Whisper（音声認識モデル）
- デフォルト：`large`モデル（最高精度）
- 他のモデル：`tiny`, `base`, `small`, `medium`
- 言語：日本語（`ja`）
- 出力形式：SRT（SubRip）

**備考**：
- 切り抜き済み動画を入力するため、タイムスタンプは0秒起点で生成される
- YouTube字幕より精度が高い（特にlargeモデル）
- 処理時間：5分動画でlargeモデル10-20分程度（CPU環境）

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
- 読みやすいJSON配列形式に正規化

**入力**：
- `chat_full.json`（全チャット）
- START時刻（必須）
- END時刻（推奨）

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

**説明**：チャットメッセージをライブチャット風に表示するためのASS字幕オーバーレイを作成する。

**デザイン仕様**：
- 右側にチャットエリアを配置
- 常に最大7件のコメントを表示（スロット方式）
- 新しいコメントが下部（slot 0）に追加され、古いコメントは上にシフト
- 7件を超えると最古のコメントが消える
- メッセージのみ表示（投稿者名なし）
- スライドアニメーション（0.3秒）

**入力**：
- `chat_clip.json`（切り抜き区間のチャット）

**出力**：
- `chat_overlay.ass`（ASS形式の字幕オーバーレイ）

**技術**：
- ASS（Advanced SubStation Alpha）形式で作成
- タイムスタンプ形式：`h:mm:ss.cc`
- アニメーション：`\move()`, `\fad()`タグ使用

---

### ステップ5：動画合成（字幕＋チャットオーバーレイ）

**説明**：切り抜き動画に、Whisper字幕とチャットオーバーレイを重ねて最終動画を生成する。

**入力**：
- `clip.webm`（切り抜き済み動画）
- `subs_clip.srt`（Whisper生成字幕）
- `chat_overlay.ass`（チャットオーバーレイ）

**出力**：
- `final.mp4`（完成品）

**技術**：
- FFmpegで合成
- H.264エンコード（CRF 23、medium preset）
- 字幕フィルター：`subtitles=` + `ass=`

**FFmpegコマンド例**：
```bash
ffmpeg -i clip.webm \
  -vf "subtitles=subs_clip.srt,ass=chat_overlay.ass" \
  -c:v libx264 -preset medium -crf 23 \
  -c:a aac final.mp4
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
```

### 方法2：全自動実行（字幕編集なし）

```bash
python main.py run config.txt
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
├── input/          # 入力ファイル（必要に応じて）
├── temp/           # 一時ファイル
│   ├── clip.webm
│   ├── subs_clip.srt        # Whisper生成字幕
│   ├── chat_full.json
│   ├── chat_clip.json
│   └── chat_overlay.ass
└── output/         # 完成動画
    └── final.mp4
```

---

## 設定ファイル（config.txt）

### 基本設定（自動ダウンロード）

```
VIDEO_URL=https://www.youtube.com/watch?v=xxxxx
START_TIME=00:05:30
END_TIME=00:10:45
AUTO_DOWNLOAD=true
```

### 既存動画を使用する場合

```
VIDEO_URL=https://www.youtube.com/watch?v=xxxxx
START_TIME=00:05:30
END_TIME=00:10:45
AUTO_DOWNLOAD=false
WEBM_PATH=data/input/clip.webm
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

- **2025-11-14**：Whisperベースに全面刷新
  - YouTube字幕取得を削除
  - Whisper音声認識による字幕生成を追加
  - 2段階ワークフロー（prepare/compose）を追加
  - 字幕のリベース処理を削除（Whisperが切り抜き動画から直接生成）

- **2025-11-13**：初版作成
  - KirinukiDB依存を削除
  - yt-dlpによる動画ダウンロード機能を追加
  - chat-downloaderをyt-dlpに置き換え
