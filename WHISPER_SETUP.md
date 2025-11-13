# Whisper字幕生成機能のセットアップ

## 概要

KIRINUKI ProcessorにWhisperを使った音声認識による字幕生成機能が追加されました。
切り抜き済みの動画から直接、高精度な日本語字幕を生成できます。

## インストール

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

これにより以下がインストールされます：
- `openai-whisper`: OpenAIのWhisper音声認識モデル
- `torch`: PyTorch（機械学習フレームワーク）
- `torchaudio`: 音声処理ライブラリ

**注意**: 初回インストール時、特にPyTorchは大きなファイルをダウンロードするため時間がかかります。

### 2. FFmpegの確認

Whisperは内部でFFmpegを使用します。FFmpegがインストールされていることを確認してください：

```bash
ffmpeg -version
```

## 使い方

### 基本的な使い方

```bash
python main.py step1w -i data/temp/clip.webm -o data/temp/subs_clip.srt
```

### オプション

| オプション | 説明 | デフォルト値 |
|----------|------|------------|
| `-i, --input` | 入力動画ファイル（必須） | - |
| `-o, --output` | 出力SRTファイル（必須） | - |
| `-m, --model` | Whisperモデルサイズ | `large` |
| `-l, --language` | 言語コード | `ja` |

### モデルサイズの選択

Whisperには複数のモデルサイズがあります：

| モデル | パラメータ数 | 必要VRAM | 速度 | 精度 |
|--------|------------|---------|------|------|
| `tiny` | 39M | ~1GB | 最速 | 低 |
| `base` | 74M | ~1GB | 速い | やや低 |
| `small` | 244M | ~2GB | 普通 | 普通 |
| `medium` | 769M | ~5GB | やや遅い | 高 |
| `large` | 1550M | ~10GB | 遅い | 最高 |

**推奨**: ひろゆき動画の場合、精度を重視して `large` モデルを使用することを推奨します。

### 例

#### 1. largeモデルで字幕生成（推奨）

```bash
python main.py step1w \
  -i data/temp/clip.webm \
  -o data/temp/subs_clip.srt \
  -m large \
  -l ja
```

#### 2. mediumモデルで高速処理

```bash
python main.py step1w \
  -i data/temp/clip.webm \
  -o data/temp/subs_clip.srt \
  -m medium
```

#### 3. フルパイプラインでの使用

1. 動画をダウンロード・切り抜き
```bash
python main.py step0 https://www.youtube.com/watch?v=xxxxx \
  -s 00:05:30 \
  -e 00:10:45 \
  -o data/temp/clip.webm
```

2. Whisperで字幕生成（ステップ1をスキップして直接step1w）
```bash
python main.py step1w \
  -i data/temp/clip.webm \
  -o data/temp/subs_clip.srt
```

3. チャット取得
```bash
python main.py step3 https://www.youtube.com/watch?v=xxxxx \
  -o data/temp/chat_full.json
```

4. チャット抽出
```bash
python main.py step4 \
  -i data/temp/chat_full.json \
  -o data/temp/chat_clip.json \
  -s 00:05:30 \
  -e 00:10:45
```

5. チャットオーバーレイ生成
```bash
python main.py step5 \
  -i data/temp/chat_clip.json \
  -o data/temp/chat_overlay.ass
```

6. 最終動画合成
```bash
python main.py step6 \
  -v data/temp/clip.webm \
  -s data/temp/subs_clip.srt \
  -c data/temp/chat_overlay.ass \
  -o data/output/final.mp4
```

## 処理時間の目安

- **tiny/base**: 5分の動画で約1-2分
- **small**: 5分の動画で約3-5分
- **medium**: 5分の動画で約5-10分
- **large**: 5分の動画で約10-20分

※ CPUのみの環境での目安。GPU（CUDA対応）がある場合は大幅に高速化されます。

## トラブルシューティング

### エラー: `ModuleNotFoundError: No module named 'whisper'`

Whisperがインストールされていません：
```bash
pip install openai-whisper
```

### エラー: `RuntimeError: Couldn't find ffmpeg or avconv`

FFmpegがインストールされていません。README.mdの「必要な環境」セクションを参照してください。

### メモリ不足エラー

largeモデルは約10GBのVRAMが必要です。メモリが不足する場合は、小さいモデルを使用してください：
```bash
python main.py step1w -i input.webm -o output.srt -m medium
```

### GPU（CUDA）の使用

PyTorchがCUDA対応でインストールされている場合、自動的にGPUが使用されます。
GPU使用を確認するには：
```python
import torch
print(torch.cuda.is_available())  # True であればGPU使用可能
```

## YouTube字幕 vs Whisper字幕

| 比較項目 | YouTube字幕（step1） | Whisper字幕（step1w） |
|---------|-------------------|---------------------|
| 必要条件 | YouTubeに字幕が存在 | 動画の音声のみ |
| 処理時間 | 数秒 | 数分〜数十分 |
| 精度 | YouTubeの自動字幕の品質に依存 | 高精度（特にlargeモデル） |
| タイミング | YouTubeの字幕に依存 | 音声認識に基づく自然なタイミング |
| 使用場面 | 字幕が存在する場合 | 字幕がない、またはより高品質な字幕が必要な場合 |

## 推奨ワークフロー

1. まずYouTube字幕（step1）を試す
2. 字幕がない、または品質が低い場合はWhisper（step1w）を使用
3. Whisperを使う場合は、まず切り抜き（step0）を実行してから字幕生成
