"""
ステップ7: YouTube説明欄生成

Whisper生成字幕からトランスクリプトを抽出し、
Groq APIを使用してYouTube説明欄の文章を生成する。
"""

import os
from pathlib import Path
from typing import Optional
from groq import Groq
from dotenv import load_dotenv


def extract_transcript_from_srt(srt_path: str) -> str:
    """
    SRTファイルからトランスクリプトテキストを抽出
    
    Args:
        srt_path: SRTファイルのパス
    
    Returns:
        抽出されたトランスクリプト
    """
    if not os.path.exists(srt_path):
        raise FileNotFoundError(f"SRT file not found: {srt_path}")
    
    transcript_lines = []
    
    with open(srt_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    # SRT形式から字幕テキストのみを抽出
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # 番号行をスキップ
        if line.isdigit():
            i += 1
            continue
        
        # タイムスタンプ行をスキップ
        if "-->" in line:
            i += 1
            # 次の行からテキストを読む
            while i < len(lines) and lines[i].strip() != "":
                text = lines[i].strip()
                if text:
                    transcript_lines.append(text)
                i += 1
            continue
        
        i += 1
    
    # 改行で結合
    transcript = "\n".join(transcript_lines)
    return transcript


def load_prompt_template(template_path: str) -> str:
    """
    プロンプトテンプレートを読み込み
    
    Args:
        template_path: テンプレートファイルのパス
    
    Returns:
        プロンプトテンプレート
    """
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Prompt template not found: {template_path}")
    
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()
    
    return template


def generate_description_with_groq(
    transcript: str,
    prompt_template: str,
    api_key: Optional[str] = None,
    model: str = "llama-3.3-70b-versatile"
) -> str:
    """
    Groq APIを使用してYouTube説明欄を生成
    
    Args:
        transcript: 動画のトランスクリプト
        prompt_template: プロンプトテンプレート
        api_key: Groq APIキー（Noneの場合は環境変数から取得）
        model: 使用するモデル名
    
    Returns:
        生成されたYouTube説明欄の文章
    """
    # APIキーの取得
    if api_key is None:
        # .env.localから環境変数を読み込み
        load_dotenv(dotenv_path=".env.local")
        api_key = os.getenv("GROQ_API_KEY")
    
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set. Please set it in .env.local")
    
    # Groqクライアントを初期化
    client = Groq(api_key=api_key)
    
    # プロンプトを構築
    full_prompt = prompt_template.replace("（ここに文字起こしを貼る）", transcript)
    
    try:
        # Groq APIでチャット補完を実行
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": full_prompt,
                }
            ],
            model=model,
            temperature=0.7,
            max_tokens=2048,
        )
        
        # 生成されたテキストを取得
        description = chat_completion.choices[0].message.content
        return description
    
    except Exception as e:
        raise RuntimeError(f"Failed to generate description with Groq API: {e}")


def generate_youtube_description(
    srt_path: str,
    output_path: str,
    prompt_template_path: str = "data/input/setumei",
    model: str = "llama-3.3-70b-versatile",
    video_url: Optional[str] = None
) -> bool:
    """
    SRT字幕からYouTube説明欄を生成

    Args:
        srt_path: SRTファイルのパス
        output_path: 出力するテキストファイルのパス
        prompt_template_path: プロンプトテンプレートのパス
        model: 使用するGroqモデル名
        video_url: 元動画のURL（指定された場合は説明文に挿入）

    Returns:
        bool: 生成に成功したかどうか
    """
    print(f"[Step 7] Generating YouTube description...")

    try:
        # 1. SRTからトランスクリプトを抽出
        print(f"  Extracting transcript from SRT...")
        transcript = extract_transcript_from_srt(srt_path)
        print(f"  ✓ Extracted {len(transcript)} characters")

        # 2. プロンプトテンプレートを読み込み
        print(f"  Loading prompt template...")
        prompt_template = load_prompt_template(prompt_template_path)
        print(f"  ✓ Loaded template from {prompt_template_path}")

        # 3. Groq APIでYouTube説明欄を生成
        print(f"  Generating description with Groq API (model: {model})...")
        description = generate_description_with_groq(
            transcript=transcript,
            prompt_template=prompt_template,
            model=model
        )
        print(f"  ✓ Generated {len(description)} characters")

        # 4. 元動画リンクを挿入
        if video_url:
            # 「【背景情報】」の後に元動画リンクを挿入
            link_section = f"\n🎥【元動画】\n👉 {video_url}\n\n"
            # チャンネルについての前に挿入
            if "💬【チャンネルについて】" in description:
                description = description.replace(
                    "💬【チャンネルについて】",
                    link_section + "💬【チャンネルについて】"
                )
            else:
                # チャンネル情報がない場合は末尾に追加
                description += link_section

        # 5. 出力ディレクトリを作成
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # 6. ファイルに保存
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(description)

        print(f"✓ YouTube description generated successfully!")
        print(f"  Output: {output_path}")

        return True

    except Exception as e:
        print(f"✗ Failed to generate YouTube description: {e}")
        return False
