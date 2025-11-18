"""
ステップ1.5: Whisper生成字幕の修正

Whisper生成字幕の以下の問題を修正：
1. 不自然な空白の削除
2. 単語の途中で切れている問題の修正（ルールベース）
3. 時刻は完全に維持
"""

import os
import re
from typing import List, Tuple, Optional


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


def fix_subtitle_text_rule_based(text: str) -> str:
    """
    ルールベースで字幕テキストを修正

    Args:
        text: 元のテキスト

    Returns:
        修正されたテキスト
    """
    # 1. 不自然な空白を削除
    # 「答え が」→「答えが」
    # 「幸せに なる」→「幸せになる」
    # ひらがな・カタカナ・漢字の間の空白を削除
    text = re.sub(r'([\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF])\s+([\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF])', r'\1\2', text)

    # 2. 連続する空白を1つに
    text = re.sub(r'\s+', ' ', text)

    # 3. 行頭・行末の空白を削除
    text = text.strip()

    # 4. よくある誤字・分割パターンの修正
    # 「なが自信」→「ない自信」（単語の途中で切れているパターン）
    replacements = {
        'なが自信': 'ない自信',
        'おりよう': '折れよう',
        'ら自信': 'たら自信',
        'ですけど あの': 'ですけど、あの',
        'ですよ あの': 'ですよ、あの',
        'んですけど あの': 'んですけど、あの',
        'じゃないですか あの': 'じゃないですか、あの',
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


def fix_subtitles_rule_based(
    entries: List[Tuple[int, str, str, str]]
) -> List[Tuple[int, str, str, str]]:
    """
    ルールベースで字幕を修正

    Args:
        entries: List of (番号, 開始時刻, 終了時刻, テキスト)

    Returns:
        修正された字幕エントリのリスト
    """
    fixed_entries = []
    for num, start, end, text in entries:
        # ルールベースで修正
        fixed_text = fix_subtitle_text_rule_based(text)
        fixed_entries.append((num, start, end, fixed_text))

    return fixed_entries


def fix_subtitle_file(
    input_srt_path: str,
    output_srt_path: str,
    model: str = "rule-based"
) -> bool:
    """
    SRT字幕ファイルを修正して保存

    Args:
        input_srt_path: 入力SRTファイルのパス
        output_srt_path: 出力SRTファイルのパス
        model: 使用する修正方法（現在は"rule-based"のみ対応）

    Returns:
        bool: 修正に成功したかどうか
    """
    print(f"[Step 1.5] Fixing subtitles...")

    try:
        # 1. SRTファイルをパース
        print(f"  Parsing SRT file...")
        entries = parse_srt(input_srt_path)
        print(f"  ✓ Parsed {len(entries)} subtitle entries")

        # 2. ルールベースで字幕を修正
        print(f"  Fixing subtitles with rule-based method...")
        fixed_entries = fix_subtitles_rule_based(entries)
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
