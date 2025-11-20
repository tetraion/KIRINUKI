# ショート動画生成機能

完成した切り抜き動画（final.mp4）から、YouTubeショート向けの縦型動画（1080x1920）を生成する機能です。

## 機能概要

- **シンプル**: 時間指定で切り出すだけ
- **高速**: 複雑な処理なし
- **柔軟**: 上下の黒背景部分へタイトルや補足テキストを自動描画可能

## 使い方

### 1. 切り抜き動画を作成

まず通常の切り抜き動画（final.mp4）を作成します：

```bash
python main.py run config.txt
```

### 2. 設定ファイルを作成

`short_config.txt` というファイルを作成します（サンプル: `short_config_sample.txt`）:

```txt
# 入力動画（final.mp4）
INPUT_VIDEO=data/output/final.mp4

# 切り取り開始時刻（final.mp4内の相対時刻）
START_TIME=00:00:05

# 切り取り終了時刻（final.mp4内の相対時刻）
END_TIME=00:00:35

# 出力先
OUTPUT=data/output/short.mp4
```

### 3. ショート動画を生成

```bash
python main.py short short_config.txt
```

## パラメータ説明

### INPUT_VIDEO
- 入力動画のパス
- デフォルト: `data/output/final.mp4`
- 先に `python main.py compose config.txt` を実行して作成してください

### START_TIME / END_TIME
- 切り取る時間範囲（final.mp4内の相対時刻）
- 形式: `hh:mm:ss` または `mm:ss` または `ss`
- 例: `00:00:05` (5秒目) ～ `00:00:35` (35秒目)
- YouTubeショートは最大60秒

### OUTPUT
- 出力動画のパス
- デフォルト: `data/output/short.mp4`

### TOP_TEXT / BOTTOM_TEXT（任意）
- 上下の余白に表示するテキスト
- `\n` で改行可能、もしくは自動折返し（後述）を利用
- 例: `TOP_TEXT=ひろゆきが語る「仕事\nと人生」の極意`
- サイズや色は以下のパラメータで調整可能

| パラメータ | 説明 | デフォルト |
| --- | --- | --- |
| `TOP_TEXT_SIZE` / `BOTTOM_TEXT_SIZE` | フォントサイズ | 72 / 64 |
| `TOP_TEXT_COLOR` / `BOTTOM_TEXT_COLOR` | フォントカラー | `white` |
| `TOP_TEXT_FONT` / `BOTTOM_TEXT_FONT` | フォント名またはフォントファイルパス | システム既定 |
| `TOP_TEXT_BOX_COLOR` / `BOTTOM_TEXT_BOX_COLOR` | ボックス色（@透明度指定可） | `black@0.65` |
| `TOP_TEXT_BOX_BORDER` / `BOTTOM_TEXT_BOX_BORDER` | ボックスの上下余白 | 28 |
| `TOP_TEXT_BOX` / `BOTTOM_TEXT_BOX` | ボックス表示のON/OFF (`1`/`0`) | ON（テキスト指定時） |
| `TOP_TEXT_WRAP` / `BOTTOM_TEXT_WRAP` | 自動折返しを有効化 (`1`/`0`) | 上：ON / 下：OFF |
| `TOP_TEXT_WRAP_WIDTH` / `BOTTOM_TEXT_WRAP_WIDTH` | 折返し文字数の目安 | 14 / 20 |
| `TOP_TEXT_OFFSET_Y` / `BOTTOM_TEXT_OFFSET_Y` | 上下移動量（正の値で上方向へシフト、ピクセル） | 0 |

下部テキストを使わない場合は `BOTTOM_TEXT` を空のままにしてください。

## ワークフロー例

```bash
# 1. 通常の切り抜き動画を作成
python main.py run config.txt

# 2. ショート動画の設定ファイルを作成
cp short_config_sample.txt short_config.txt
# short_config.txt を編集

# 3. ショート動画を生成
python main.py short short_config.txt
```

## 技術仕様

### 処理内容

1. **時間切り出し**: final.mp4から指定時間範囲を抽出
2. **スケール**: 1080幅にリサイズ（アスペクト比維持）
3. **パディング**: 上下に黒背景を追加して1920の高さに

### 出力形式

- 解像度: 1080x1920（縦型）
- コーデック: H.264（libx264）
- 音声: AAC 128kbps
- 品質: CRF 23（バランス型）

### レイアウト

```
┌─────────────────┐ ← 1080x1920
│  黒背景（上）   │
├─────────────────┤
│                 │
│   元動画 16:9   │ ← 1080x607（アスペクト比維持）
│                 │
├─────────────────┤
│  黒背景（下）   │
└─────────────────┘

※ 上下の黒背景部分に設定ファイルで指定したテキストが描画されます
```

## ファイル構成

```
shorts/
├── __init__.py          # パッケージ初期化
├── short_generator.py   # ショート動画生成モジュール
└── README.md            # このファイル

data/
└── output/
    ├── final.mp4        # 入力動画（切り抜き完成版）
    └── short.mp4        # 出力動画（縦型ショート）
```

## トラブルシューティング

### 入力動画が見つからない

```
Error: Input video not found: data/output/final.mp4
```

先に `python main.py compose config.txt` を実行してfinal.mp4を作成してください。

### 時間範囲が動画の長さを超えている

final.mp4の長さを確認してください：

```bash
ffprobe data/output/final.mp4
```

## 今後の拡張予定

- 上下の黒背景部分にコメントを表示
- 自動ハイライト検出（音量・話速から面白い箇所を抽出）
- 複数のショート動画を一度に生成するバッチ処理
