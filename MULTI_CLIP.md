# 複数クリップ連結機能

## 概要

複数の切り抜きシーンを1つの動画として出力できる機能を実装しました。

## 使い方

### 1. 設定ファイルの準備

各クリップ用の設定ファイルを作成し、`NEXT_CONFIG`パラメータで連鎖させます。

**config.txt（最初のクリップ）**
```
VIDEO_URL=https://www.youtube.com/watch?v=xxxxx
START_TIME=00:05:00
END_TIME=00:06:30
TITLE=動画のタイトル
NEXT_CONFIG=config2.txt
```

**config2.txt（2番目のクリップ）**
```
VIDEO_URL=https://www.youtube.com/watch?v=xxxxx
START_TIME=00:10:00
END_TIME=00:11:45
# タイトルは最初のconfigのみに指定
NEXT_CONFIG=config3.txt
```

**config3.txt（3番目のクリップ）**
```
VIDEO_URL=https://www.youtube.com/watch?v=xxxxx
START_TIME=00:15:20
END_TIME=00:17:00
# 最後のクリップなのでNEXT_CONFIGは不要
```

### 2. 実行

通常と同じコマンドで実行できます：

```bash
# 素材準備（全クリップを処理）
python main.py prepare config.txt

# 動画合成（全クリップを連結）
python main.py compose config.txt
```

## 処理の流れ

### prepare コマンド

1. config.txt を読み込み
2. NEXT_CONFIGをチェックして config2.txt を読み込み
3. さらにNEXT_CONFIGをチェックして config3.txt を読み込み
4. 各クリップごとに以下を生成：
   - `clip.webm`, `clip_1.webm`, `clip_2.webm`
   - `subs_clip.srt`, `subs_clip_1.srt`, `subs_clip_2.srt`
   - `chat_overlay.ass`, `chat_overlay_1.ass`, `chat_overlay_2.ass`

### compose コマンド

1. 全クリップの設定を読み込み
2. 複数クリップを連結：
   - 動画：FFmpegのconcatで連結 → `concatenated.webm`
   - 字幕：時間オフセットを調整してマージ → `subs_clip_merged.srt`
   - チャット：時間オフセットを調整してマージ → `chat_overlay_merged.ass`
3. 連結された動画に字幕とチャットを合成 → `final.mp4`

## 技術詳細

### 時間オフセット計算

各クリップの長さを `ffprobe` で取得し、2番目以降のクリップの字幕とチャットの時刻を調整します。

例：
- Clip 1: 0:00 - 1:30 (90秒)
- Clip 2: 0:00 - 2:00 (120秒) → 連結後は 1:30 - 3:30
- Clip 3: 0:00 - 1:45 (105秒) → 連結後は 3:30 - 5:15

### ファイル命名規則

- 最初のクリップ: `clip.webm`, `subs_clip.srt`, `chat_overlay.ass`
- 2番目のクリップ: `clip_1.webm`, `subs_clip_1.srt`, `chat_overlay_1.ass`
- 3番目のクリップ: `clip_2.webm`, `subs_clip_2.srt`, `chat_overlay_2.ass`
- ...

### 循環参照チェック

config.txt → config2.txt → config.txt のような循環参照はエラーとして検出されます。

## 制限事項

- TITLEは最初のconfigファイルのみに指定してください

## 各クリップの個別設定

各設定ファイルで以下を個別に指定できます：

- **動画URL（VIDEO_URL）**: 異なる動画から切り抜き可能
- **切り抜き時刻（START_TIME/END_TIME）**: 各クリップの時刻を個別指定
- **チャット表示タイミング（CHAT_DELAY_SECONDS）**: 動画ごとに異なるディレイを設定可能
- **クロップ設定（CROP_PERCENT等）**: 各クリップで異なるクロップを適用可能

**注意**: 各クリップは連結前にクロップされます。異なるクロップ設定を使うと、クリップ間で画面サイズが異なる可能性があります。

## サンプル

プロジェクトルートに以下のサンプルファイルがあります：
- `config.txt` - 1番目のクリップ（NEXT_CONFIG=config2.txt のコメント例あり）
- `config2.txt` - 2番目のクリップ例
- `config3.txt` - 3番目のクリップ例
