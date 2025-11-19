# Agents: KIRINUKI Processor

YouTube切り抜き動画に字幕とライブチャットを重ねるこのアプリは、複数の処理ステップで構成されています。それぞれを「エージェント」と見立て、役割と入出力、関連コマンドを整理しました。各エージェントは `main.py` の CLI から直列に呼び出され、`prepare / compose / run` でフルパイプラインを実行できます。

```
config.txt ──▶ Step0 Config Agent
              ├─▶ Step0 Clip Agent
              ├─▶ Step1 Subtitle Agent
              ├─▶ Step2 ChatFetch Agent
              ├─▶ Step3 ChatCurator Agent
              ├─▶ Step4 Overlay Agent
              ├─▶ Step TitleBar Agent (任意)
              └─▶ Step5 Composer Agent
data/temp と data/output に成果物を蓄積
```

## 共通セットアップ
- 必須コマンド: `yt-dlp`, `ffmpeg`, `python3`, Whisper 依存 (`openai-whisper`, `torch`, `torchaudio`)。
- ルート直下の `config.txt` を複製して案件ごとの設定ファイルを作成。
- 標準ディレクトリ:
  - `data/input`: 既存の切り抜き動画や素材画像 (`ひろゆき視点【切り抜き】.png`)。
  - `data/temp`: ステップ間の中間生成物 (`clip.webm`, `subs_clip.srt`, `chat_*.json`, `chat_overlay.ass`, `title_bar.ass`)。
  - `data/output`: 最終成果物 (`final.mp4`)。

## Config Agent (`kirinuki_processor/steps/step0_config.py`)
- 役割: `config.txt` 形式の設定を `ClipConfig` に読み込み、必須項目や時間フォーマットを検証。
- CLI: `python main.py init -o config.txt` でサンプル生成。以降は手動編集。
- 出力: `ClipConfig` オブジェクト (動画 URL、開始/終了時刻、AUTO_DOWNLOAD、タイトル、クロップパーセンテージなど)。`CROP_PERCENT` を設定すれば上下左右をまとめてトリミング、個別に数値を入れれば細かく調整できます。

## Clip Agent (`kirinuki_processor/steps/step0_download_clip.py`)
- 役割: 指定区間を YouTube から直接ダウンロードし `data/temp/clip.webm` に保存。`AUTO_DOWNLOAD=false` の場合はスキップして `WEBM_PATH` を参照。
- 実装ポイント:
  - `yt-dlp --download-sections` で範囲指定。失敗時はフルダウンロード→`ffmpeg` 切り抜きにフォールバック。
  - `download_full=True` を指定すると常にフル DL → 切り抜き。
- CLI: `python main.py step0 URL -s 00:00:00 -e 00:05:00 -o data/temp/clip.webm [--full]`。
- エラーが出た場合は `yt-dlp`/`ffmpeg` のインストールと PATH を確認。

## Subtitle Agent (`kirinuki_processor/steps/step1_generate_subtitles.py`)
- 役割: Whisper で `clip.webm` から音声を抽出 (`ffmpeg`) し、`subs_clip.srt` とスタイル付き `subs_clip.ass` を生成（ASSは再生時に太字・大サイズで表示）。
- デフォルト: `model_size="large"`, `language="ja"`, `fp16=False` (CPU 互換)。
- CLI: `python main.py step1 -i data/temp/clip.webm -o data/temp/subs_clip.srt -m medium` など。
- 字幕編集フロー: `prepare` 実行後に `data/temp/subs_clip.srt` を手動で校正 → `compose` 実行時にASSへ自動反映される。

## ChatFetch Agent (`kirinuki_processor/steps/step3_fetch_chat.py`)
- 役割: `yt-dlp --write-subs --sub-langs live_chat` でチャットリプレイを JSONL 取得し、正規化 (`normalized_chat`) して `data/temp/chat_full.json` に保存。
- CLI: `python main.py step2 VIDEO_URL -o data/temp/chat_full.json`。
- 注意: ライブチャットが無効な動画ではスキップ扱いで以降のチャット処理が行われません。

## ChatCurator Agent (`kirinuki_processor/steps/step4_extract_chat.py`)
- 役割: `chat_full.json` を読み込み、切り抜き開始時刻を 0 秒基準に再マッピング。`END_TIME` があればその前で打ち切り。
- 出力: `data/temp/chat_clip.json` (JSON配列）。`ChatMessage` dataclass を JSON 化。
- CLI: `python main.py step3 -i data/temp/chat_full.json -o data/temp/chat_clip.json -s 00:05:30 -e 00:10:45`。
- 補助ユーティリティ: `kirinuki_processor/utils/time_utils.py` で時間変換を共通化。

## Overlay Agent (`kirinuki_processor/steps/step5_generate_overlay.py`)
- 役割: `chat_clip.json` を元に、ニコニコ動画風に右→左へ流れるチャット ASS (`data/temp/chat_overlay.ass`) を描画。
- 表示スタイル: `OverlayConfig` (レーン数・縦位置・速度・フォントなど) を上書き可能。
- CLI: `python main.py step4 -i data/temp/chat_clip.json -o data/temp/chat_overlay.ass`。

## TitleBar Agent (`kirinuki_processor/steps/step_title_bar.py`)
- 役割: `TITLE=` が config にある場合、スライドイン付きタイトルバーを `data/temp/title_bar.ass` として生成し、ロゴ ( `data/input/ひろゆき視点【切り抜き】.png` ) と揃う高さ・速度で表示。
- 引数: `generate_title_bar(title, output_path, video_width=1920, video_height=1080, slide_duration=1.2, display_duration=None)`。
- `compose` 実行時に自動で呼ばれるため単体コマンドは不要。

## Composer Agent (`kirinuki_processor/steps/step6_compose_video.py`)
- 役割: `ffmpeg` で動画・字幕(SRT/ASS)・チャットオーバーレイ・タイトルバー・ロゴを合成し `data/output/final.mp4` を生成。
- 処理:
  - ロゴ入力が存在すれば `filter_complex` を使って円形マスク＋白縁を適用。
  - 字幕はSRT編集内容から必要に応じてASSへ再変換した上で `ass=` フィルターにかける（ASSが無い場合は `subtitles=` を使用）。
  - `CROP_*_PERCENT` で指示された分を削りつつ、上下左右を均等に切り詰めて16:9のままズーム。
  - 既定エンコード: `libx264`, `aac`, `preset=medium`, `crf=23`。
- CLI: `python main.py step5 -v data/temp/clip.webm -o data/output/final.mp4 -s data/temp/subs_clip.srt -c data/temp/chat_overlay.ass`。タイトルバーやロゴは `compose` / `run` のときに自動注入。

## 代表的なワークフロー
1. 設定ファイルを用意: `python main.py init -o config_myclip.txt` → 値を編集。
2. 素材準備: `python main.py prepare config_myclip.txt`  
   - `clip.webm`, `subs_clip.srt`, `chat_overlay.ass` などが `data/temp` に出力される。
3. 字幕を手動編集。
4. 合成: `python main.py compose config_myclip.txt` → `data/output/final.mp4`。
5. フル自動一発実行 (字幕編集なし): `python main.py run config_myclip.txt`。

## テスト
- 単体テストは `kirinuki_processor/tests` に配置。構成やユーティリティの回 regressions を `pytest` で確認:  
  `python -m pytest kirinuki_processor/tests -q`

## トラブルシューティングのヒント
- `yt-dlp` / `ffmpeg` が見つからない: `pip install yt-dlp`, `brew install ffmpeg` 等で導入し PATH を確認。
- Whisper メモリ不足: `python main.py step1 ... -m small` のようにモデルを縮小。
- チャットが取得できない場合: ライブチャット未提供の動画はチャット系ステップをスキップしても `compose` 可能。
- 再合成時は `data/temp/subs_clip.srt` を更新 → `python main.py compose config.txt` のみでOK (再ダウンロード不要)。
