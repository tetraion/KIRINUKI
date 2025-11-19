# KIRINUKI Processor - 仕様書

## 概要

YouTube動画を切り抜き、Whisper生成の高精度字幕とライブチャットを重ねて見やすい動画を作成する。

## 処理フロー

### ステップ0：動画ダウンロードと切り抜き

- **入力**：動画URL、切り抜き開始時刻（START）、切り抜き終了時刻（END）
- **出力**：`clip.webm`

### ステップ1：Whisper字幕生成

- **入力**：`clip.webm`
- **出力**：`subs_clip.srt`, `subs_clip.ass`
- **モデル**：デフォルト`large`（`tiny`, `base`, `small`, `medium`も選択可）
- **字幕スタイル**：Hiragino Sans 110px、白文字、黒アウトライン（7px）、画面下部中央

### ステップ2：ライブチャット取得

- **入力**：動画URL
- **出力**：`chat_full.json`

### ステップ3：チャット区間抽出・整形

- **入力**：`chat_full.json`, START, END, CHAT_DELAY_SECONDS（任意）
- **出力**：`chat_clip.json`
- **タイミング調整**：
  - `CHAT_DELAY_SECONDS > 0`：チャットを早く表示（遅延がある場合）
  - `CHAT_DELAY_SECONDS < 0`：チャットを遅く表示（早すぎる場合）

### ステップ4：チャットオーバーレイ生成

- **入力**：`chat_clip.json`
- **出力**：`chat_overlay.ass`
- **表示形式**：ニコニコ動画風の横スクロール（右→左）
- **スタイル**：Hiragino Sans 55px、白文字、黒アウトライン（3px）、6レーン

### ステップ4.5：タイトルバー生成（任意）

- **入力**：`TITLE`（設定ファイルで指定）
- **出力**：`title_bar.ass`
- **デザイン**：
  - タイトルバー：黄色背景、Hiragino Sans 90px、黒文字
  - チャンネル名：青色背景、「ひろゆき視点」、Hiragino Sans W9 48px、白文字
  - アニメーション：左から右へスライドイン（1.2秒）

### ステップ5：動画合成

- **入力**：`clip.webm`, `subs_clip.ass`, `chat_overlay.ass`, `title_bar.ass`（任意）, ロゴ画像（任意）
- **出力**：`final.mp4`（1920x1080）
- **処理**：クロップ → スケール → ロゴ合成 → 字幕合成 → チャット合成 → タイトルバー合成

### ステップ6：YouTube説明欄生成（任意）

- **入力**：`subs_clip.srt`, `data/input/setumei`, `.env.local`
- **出力**：`description.txt`
- **生成内容**：動画概要タイトル、要点まとめ、元動画リンク、おすすめ関連動画、ハッシュタグ

---

## コマンド

### メインコマンド

```bash
# 全自動実行（素材準備→動画合成）
python main.py run config.txt

# 素材準備のみ
python main.py prepare config.txt

# 動画合成のみ
python main.py compose config.txt

# 完成動画を整理保存
python main.py output config.txt
```

### 便利コマンド

```bash
# 字幕のみ再生成
python main.py resub config.txt

# チャットタイミング調整
python main.py rechat config.txt

# 字幕AI補正（手動実行のみ）
python main.py step1.5 config.txt

# 一時ファイル削除（次の動画作成準備）
python main.py clear config.txt
python main.py clear config.txt --keep-videos  # 動画ファイルは残す
```

---

## 使用例

### 基本ワークフロー（字幕編集あり）

```bash
# 1. 素材準備
python main.py prepare config.txt

# 2. 字幕を編集
code data/temp/subs_clip.srt

# 3. 動画合成
python main.py compose config.txt

# 4. 整理保存
python main.py output config.txt
```

### 全自動実行

```bash
python main.py run config.txt
python main.py output config.txt
```

### チャットタイミング調整

```bash
python main.py prepare config.txt
python main.py compose config.txt

# config.txtのCHAT_DELAY_SECONDSを調整
python main.py rechat config.txt
python main.py compose config.txt
```

---

## 設定ファイル（config.txt）

### 基本設定

```
VIDEO_URL=https://www.youtube.com/watch?v=xxxxx
START_TIME=00:05:30
END_TIME=00:10:45
TITLE=動画のタイトル（任意）
```

### クロップ設定

```
CROP_PERCENT=5.0  # 全方向均等

# または個別設定
CROP_TOP_PERCENT=5.0
CROP_BOTTOM_PERCENT=5.0
CROP_LEFT_PERCENT=3.0
CROP_RIGHT_PERCENT=3.0
```

### チャットタイミング調整

```
CHAT_DELAY_SECONDS=16   # チャットが遅れている場合（正の値）
CHAT_DELAY_SECONDS=-10  # チャットが早すぎる場合（負の値）
```

### 既存動画を使用

```
AUTO_DOWNLOAD=false
WEBM_PATH=data/input/clip.webm
```

---

## ディレクトリ構成

```
data/
├── input/
│   ├── ひろゆき視点【切り抜き】.png  # ロゴ画像
│   └── setumei                       # 説明欄プロンプト
├── temp/
│   ├── clip.webm
│   ├── subs_clip.srt
│   ├── subs_clip.ass
│   ├── chat_full.json
│   ├── chat_clip.json
│   ├── chat_overlay.ass
│   └── title_bar.ass
└── output/
    ├── final.mp4
    └── description.txt
```
