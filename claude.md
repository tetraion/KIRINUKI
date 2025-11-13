# KIRINUKI Processor - 仕様書

## 目的

ひろゆきの動画の切り抜きに、字幕とライブチャットを重ねて見やすくする。

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

### ステップ1：字幕の取得

**説明**：YouTubeから日本語の字幕（公開字幕または自動生成字幕）を取得する。

**入力**：
- 動画URL

**出力**：
- `subs_full.srt`（字幕がある場合）
- 字幕なしのメモ（字幕がない場合）

**技術**：
- yt-dlpで字幕をダウンロード（`--write-subs --sub-langs ja`）

---

### ステップ2：字幕の時間合わせ（リベース）

**説明**：取得した字幕のタイムスタンプを切り抜き区間に合わせて調整する。

**処理内容**：
- STARTの時刻を0秒起点として全タイムスタンプをシフト
- END時刻がある場合、範囲外の字幕エントリを削除

**入力**：
- `subs_full.srt`（元動画の字幕）
- START時刻（必須）
- END時刻（推奨）

**出力**：
- `subs_clip.srt`（切り抜き用に調整された字幕）

---

### ステップ3：ライブチャット（リプレイ）の取得

**説明**：YouTubeのライブチャットリプレイを全量取得する。

**入力**：
- 動画URL

**出力**：
- `chat_full.json`（チャットがある場合）
- チャットリプレイなしのメモ（チャットがない場合）

**技術**：
- yt-dlpでライブチャットを取得（`--write-subs --sub-langs live_chat`）
- JSONL形式で出力される

---

### ステップ4：チャットの区間抽出・整形

**説明**：取得したチャットからSTART〜END区間のメッセージを抽出し、切り抜き基準に時刻を調整する。

**処理内容**：
- START〜ENDの範囲内のチャットメッセージのみ抽出
- タイムスタンプをSTARTを0秒として調整
- JSONL形式を読みやすいJSON配列形式に正規化

**入力**：
- `chat_full.json`（全チャット）
- START時刻（必須）
- END時刻（推奨）

**出力**：
- `chat_clip.json`（切り抜き区間のチャット）

**備考**：
- 匿名化やNGワード除去は不要（YouTubeで既にフィルタリング済み）

---

### ステップ5：チャット表示用オーバーレイの生成

**説明**：チャットメッセージをライブチャット風に表示するためのASS字幕オーバーレイを作成する。

**デザイン仕様**：
- 右側にチャットエリアを配置
- 常に最大7件のコメントを表示（スロット方式）
- 新しいコメントが下部（slot 0）に追加され、古いコメントは上にシフト
- 7件を超えると最古のコメントが消える
- メッセージのみ表示（投稿者名なし）
- フェードイン/アウト効果（200ms）

**入力**：
- `chat_clip.json`（切り抜き区間のチャット）

**出力**：
- `chat_overlay.ass`（ASS形式の字幕オーバーレイ）

**技術**：
- ASS（Advanced SubStation Alpha）形式で作成
- タイムスタンプ形式：`h:mm:ss.cc`

---

### ステップ6：動画合成（字幕＋チャットオーバーレイ）

**説明**：切り抜き動画に、字幕とチャットオーバーレイを重ねて最終動画を生成する。

**入力**：
- `clip.webm`（切り抜き済み動画）
- `subs_clip.srt`（調整済み字幕）
- `chat_overlay.ass`（チャットオーバーレイ）

**出力**：
- `final.mp4`（完成品）

**技術**：
- FFmpegで合成
- H.264エンコード（CRF 23、medium preset）
- 字幕とASSオーバーレイを同時に適用

---

### ステップ7：簡易チェック（手動）

**説明**：完成した動画を数十秒視聴して品質を確認する。

**チェック項目**：
- 開始/終了のタイミングがズレていないか
- 字幕が読みやすいか
- チャットが正しく表示されているか
- 音量が適切か

**入力**：
- `final.mp4`

**出力**：
- OK または修正点のメモ

---

## 技術スタック

- **Python 3.8+**：メイン言語
- **yt-dlp**：動画・字幕・チャットのダウンロード
- **FFmpeg**：動画の切り抜きと合成
- **pytest**：テスト

## ディレクトリ構成

```
data/
├── input/          # 入力ファイル（必要に応じて）
├── temp/           # 一時ファイル
│   ├── clip.webm
│   ├── subs_full.srt
│   ├── subs_clip.srt
│   ├── chat_full.json
│   ├── chat_clip.json
│   └── chat_overlay.ass
└── output/         # 完成動画
    └── final.mp4
```

## 設定ファイル（config.txt）

```
VIDEO_URL=https://www.youtube.com/watch?v=xxxxx
START_TIME=00:05:30
END_TIME=00:10:45
AUTO_DOWNLOAD=true
```

**AUTO_DOWNLOAD=false の場合**：
既存の切り抜き動画を使用（WEBM_PATH で指定）

```
VIDEO_URL=https://www.youtube.com/watch?v=xxxxx
START_TIME=00:05:30
END_TIME=00:10:45
AUTO_DOWNLOAD=false
WEBM_PATH=data/input/clip.webm
```

## 実装上の注意点

### 字幕形式（SRT）

```
1
00:00:00,000 --> 00:00:03,500
字幕テキスト1行目
字幕テキスト2行目

2
00:00:04,000 --> 00:00:07,200
次の字幕
```

- タイムスタンプ形式：`hh:mm:ss,mmm`
- ミリ秒はカンマ区切り

### チャットJSON形式

```json
[
  {
    "message": "コメント内容",
    "author": "投稿者名",
    "timestamp": 12.5
  }
]
```

- timestamp は秒単位（float）

### ASSオーバーレイ形式

```
[Script Info]
Title: Chat Overlay
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, ...
Style: ChatAuthor,Arial,24, ...
Style: ChatMessage,Arial,20, ...

[Events]
Format: Layer, Start, End, Style, Text
Dialogue: 0,0:00:12.50,0:00:20.50,ChatAuthor,投稿者名
Dialogue: 0,0:00:12.50,0:00:20.50,ChatMessage,コメント内容
```

- タイムスタンプ形式：`h:mm:ss.cc`
- 時間は1桁でもOK（例：`0:00:05.00`）

## エラーハンドリング

- 字幕が取得できない場合：字幕なしで処理続行
- チャットが取得できない場合：チャットなしで処理続行
- 範囲指定ダウンロード失敗時：全体ダウンロードにフォールバック

## 変更履歴

- **2025-11-13**：初版作成
  - KirinukiDB依存を削除
  - yt-dlpによる動画ダウンロード機能を追加
  - chat-downloaderをyt-dlpに置き換え
