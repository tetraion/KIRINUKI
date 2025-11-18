"""
ステップ1.5: Whisper生成字幕の修正（AIベース）

AIを使用して字幕を修正しますが、時刻は完全に維持します。
"""

import os
import re
from typing import List, Tuple, Optional
from groq import Groq
from dotenv import load_dotenv


def parse_srt(srt_path: str) -> List[Tuple[int, str, str, str]]:
    """
    SRTファイルをパースして字幕エントリのリストを返す

    Args:
        srt_path: SRTファイルのパス

    Returns:
        List of (番号, 開始時刻, 終了時刻, テキスト)
    """
    if not os.path.exists(srt_path):
        raise FileNotFoundError(f"SRT file not found: {srt_path}")

    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()

    # SRTエントリを分割
    entries = []
    blocks = content.strip().split('\n\n')

    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            number = lines[0].strip()
            time_range = lines[1].strip()
            text = '\n'.join(lines[2:])

            # 時刻範囲を分割
            match = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', time_range)
            if match:
                start_time = match.group(1)
                end_time = match.group(2)
                entries.append((int(number), start_time, end_time, text))

    return entries


def format_srt(entries: List[Tuple[int, str, str, str]]) -> str:
    """
    字幕エントリのリストをSRT形式に整形

    Args:
        entries: List of (番号, 開始時刻, 終了時刻, テキスト)

    Returns:
        SRT形式の文字列
    """
    srt_content = []
    for i, (_, start_time, end_time, text) in enumerate(entries, 1):
        srt_content.append(f"{i}")
        srt_content.append(f"{start_time} --> {end_time}")
        srt_content.append(text)
        srt_content.append("")

    return '\n'.join(srt_content)


def fix_subtitles_with_ai(
    entries: List[Tuple[int, str, str, str]],
    api_key: Optional[str] = None,
    model: str = "llama-3.3-70b-versatile"
) -> List[Tuple[int, str, str, str]]:
    """
    AIを使用して字幕を修正（時刻は維持）

    Args:
        entries: List of (番号, 開始時刻, 終了時刻, テキスト)
        api_key: Groq APIキー（Noneの場合は環境変数から取得）
        model: 使用するモデル名

    Returns:
        修正された字幕エントリのリスト
    """
    # APIキーの取得
    if api_key is None:
        load_dotenv(dotenv_path=".env.local")
        api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError("GROQ_API_KEY is not set. Please set it in .env.local")

    # Groqクライアントを初期化
    client = Groq(api_key=api_key)

    # 字幕を時刻情報付きで提示
    subtitle_list = []
    for i, (num, start, end, text) in enumerate(entries, 1):
        subtitle_list.append(f"{i}. [{start} --> {end}] {text}")

    original_subtitles = "\n".join(subtitle_list)

    # プロンプトを構築
    prompt = f"""以下の日本語字幕を修正してください。

【絶対に守るべき制約】
1. **字幕の数は{len(entries)}個のまま変更しないこと**
2. **各字幕の時刻（[XX:XX:XX,XXX --> XX:XX:XX,XXX]）は絶対に変更しないこと**
3. **各字幕は独立して処理し、統合や分割をしないこと**
4. **各字幕のテキスト部分のみを修正すること**

【修正内容】
- 不自然な空白を削除（例：「答え が」→「答えが」）
- 明らかな誤字を修正（例：「なが自信」→「ない自信」）
- 文の途中で切れている場合は、読みやすいように調整：
  * 「問題を出し」→「問題を出しました」（次の字幕が「ました」の場合）
  * 「言われて」→「言われています」（次の字幕が「います」の場合）
  * ただし、前後の字幕を見て文脈を理解し、自然な文になるように補完すること
  * 補完する際は、元の意味を変えず、自然な日本語になるように注意
- 読みやすいように軽く整形

【重要な注意点】
- 前後の字幕を見て文脈を把握してください
- 文が途中で切れている場合は、その字幕内で完結するように自然に補完してください
- 例：
  * 元: 「問題を出し」（次が「ました」）→ 修正: 「問題を出しました」
  * 元: 「自信を持っている人について」（次が「いく人が多い」）→ 修正: 「自信を持っている人についていく」
  * 元: 「ます」（前が「問題を出し」）→ 修正: 「（前の字幕から続く内容）」または適切に削除・調整

【元の字幕（時刻情報付き）】
{original_subtitles}

【出力形式】
必ず以下の形式で、時刻情報を含めて出力してください：
1. [00:00:00,000 --> 00:00:03,540] 修正後のテキスト
2. [00:00:03,540 --> 00:00:09,620] 修正後のテキスト
...

**重要：**
- 必ず{len(entries)}個の字幕を出力
- 時刻情報は元のまま変更しない
- 番号、時刻、テキストの順で出力
- 説明文は一切不要
- 各字幕は前後の文脈を見て、その字幕内で自然に完結するように修正
"""

    try:
        # Groq APIでチャット補完を実行
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model=model,
            temperature=0.2,
            max_tokens=8000,
        )

        # 生成されたテキストを取得
        response = chat_completion.choices[0].message.content

        # レスポンスをパース
        fixed_entries = []
        for line in response.strip().split('\n'):
            line = line.strip()
            # 「番号. [開始時刻 --> 終了時刻] テキスト」の形式を解析
            match = re.match(r'^\d+\.\s*\[(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\]\s*(.+)$', line)
            if match:
                start = match.group(1)
                end = match.group(2)
                text = match.group(3)
                fixed_entries.append((len(fixed_entries) + 1, start, end, text))

        # 元の字幕数と一致しない場合は警告して元のデータを使用
        if len(fixed_entries) != len(entries):
            print(f"  ⚠ Warning: Number of fixed subtitles ({len(fixed_entries)}) does not match original ({len(entries)})")
            print(f"  ⚠ Using original subtitles to prevent time misalignment")
            return entries

        # 時刻が一致するか確認
        for i, ((orig_num, orig_start, orig_end, _), (_, fix_start, fix_end, _)) in enumerate(zip(entries, fixed_entries)):
            if orig_start != fix_start or orig_end != fix_end:
                print(f"  ⚠ Warning: Time mismatch at entry {i+1}")
                print(f"  ⚠ Using original subtitles to prevent time misalignment")
                return entries

        return fixed_entries

    except Exception as e:
        print(f"  ⚠ Error during AI fixing: {e}")
        print(f"  ⚠ Using original subtitles")
        return entries


def fix_subtitle_file_ai(
    input_srt_path: str,
    output_srt_path: str,
    model: str = "llama-3.3-70b-versatile"
) -> bool:
    """
    SRT字幕ファイルをAIで修正して保存

    Args:
        input_srt_path: 入力SRTファイルのパス
        output_srt_path: 出力SRTファイルのパス
        model: 使用するGroqモデル名

    Returns:
        bool: 修正に成功したかどうか
    """
    print(f"[Step 1.5] Fixing subtitles with AI...")

    try:
        # 1. SRTファイルをパース
        print(f"  Parsing SRT file...")
        entries = parse_srt(input_srt_path)
        print(f"  ✓ Parsed {len(entries)} subtitle entries")

        # 2. AIで字幕を修正
        print(f"  Fixing subtitles with AI (model: {model})...")
        fixed_entries = fix_subtitles_with_ai(entries, model=model)
        print(f"  ✓ Fixed {len(fixed_entries)} subtitle entries")

        # 3. 修正された字幕をSRT形式に整形
        print(f"  Formatting fixed subtitles...")
        fixed_srt = format_srt(fixed_entries)

        # 4. 出力ディレクトリを作成
        output_dir = os.path.dirname(output_srt_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # 5. ファイルに保存
        with open(output_srt_path, "w", encoding="utf-8") as f:
            f.write(fixed_srt)

        print(f"✓ Subtitles fixed successfully!")
        print(f"  Input: {input_srt_path}")
        print(f"  Output: {output_srt_path}")

        return True

    except Exception as e:
        print(f"✗ Failed to fix subtitles: {e}")
        return False
