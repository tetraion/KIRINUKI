"""
ステップ3: ライブチャット取得

YouTubeのライブ配信からチャットリプレイを取得する。
yt-dlpを使用してJSON形式で保存。
"""

import os
import subprocess
import json
from typing import List, Dict, Any, Optional


def fetch_chat(
    video_url: str,
    output_path: str,
    message_types: Optional[List[str]] = None
) -> bool:
    """
    YouTube動画からライブチャットを取得

    Args:
        video_url: YouTube動画のURL
        output_path: 出力先パス（.json）
        message_types: 取得するメッセージタイプのリスト（未使用、互換性のため保持）

    Returns:
        bool: チャット取得に成功したかどうか

    Raises:
        RuntimeError: yt-dlpの実行に失敗した場合
    """
    # 出力ディレクトリを作成
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # 出力パスから拡張子を除いたベース名を取得
    base_name = os.path.splitext(output_path)[0]

    # yt-dlpコマンドを構築（live_chat字幕として取得）
    cmd = [
        "yt-dlp",
        "--skip-download",  # 動画はダウンロードしない
        "--write-subs",
        "--sub-langs", "live_chat",
        "-o", f"{base_name}.%(ext)s",
        video_url
    ]

    try:
        # yt-dlpを実行
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # 生成されたファイルを探す
        # yt-dlpは .live_chat.json という拡張子で保存する
        possible_files = [
            f"{base_name}.live_chat.json",
            f"{base_name}.json",
            output_path
        ]

        found_file = None
        for file_path in possible_files:
            if os.path.exists(file_path):
                found_file = file_path
                break

        if found_file:
            # JSONファイルをパースして正規化
            normalized_chat = normalize_chat_format(found_file)

            # 指定されたパスに保存
            with open(output_path, "w", encoding="utf-8") as f:
                for msg in normalized_chat:
                    f.write(json.dumps(msg, ensure_ascii=False) + "\n")

            # 元のファイルが異なる場合は削除
            if found_file != output_path and os.path.exists(found_file):
                os.remove(found_file)

            # チャット件数を確認
            chat_count = len(normalized_chat)
            print(f"✓ Chat downloaded: {output_path}")
            print(f"  Total messages: {chat_count}")
            return True
        else:
            print(f"✗ No chat replay found for video: {video_url}")
            return False

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)

        # yt-dlpが見つからない場合のエラーメッセージ
        if "not found" in error_msg or "command not found" in error_msg:
            print("✗ yt-dlp is not installed.")
            print("  Please install it with: pip install yt-dlp")
            return False

        # チャットリプレイがない場合のエラー
        if "No chat" in error_msg or "disabled" in error_msg or "Requested format" in error_msg:
            print(f"✗ No chat replay available for this video")
            return False

        print(f"✗ Failed to download chat: {error_msg}")
        return False

    except Exception as e:
        raise RuntimeError(f"Unexpected error while fetching chat: {e}")


def normalize_chat_format(chat_file: str) -> List[Dict[str, Any]]:
    """
    yt-dlpのライブチャット形式を正規化

    Args:
        chat_file: yt-dlpが生成したチャットファイル（JSONL形式）

    Returns:
        正規化されたチャットメッセージのリスト
    """
    normalized = []

    # JSONL形式（1行1JSON）で読み込む
    with open(chat_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)

                # replayChatItemActionを探す
                if "replayChatItemAction" in data:
                    replay_action = data["replayChatItemAction"]
                    actions = replay_action.get("actions", [])

                    for action in actions:
                        if "addChatItemAction" in action:
                            chat_item = action["addChatItemAction"]["item"]

                            # テキストメッセージを抽出
                            if "liveChatTextMessageRenderer" in chat_item:
                                renderer = chat_item["liveChatTextMessageRenderer"]

                                # メッセージテキスト
                                message_text = ""
                                if "message" in renderer:
                                    runs = renderer["message"].get("runs", [])
                                    message_text = "".join([run.get("text", "") for run in runs])

                                # 投稿者名
                                author_name = ""
                                if "authorName" in renderer:
                                    author_name = renderer["authorName"].get("simpleText", "")

                                # タイムスタンプ（マイクロ秒）
                                timestamp_usec = int(renderer.get("timestampUsec", 0))

                                # 動画内での秒数を計算
                                time_in_seconds = 0
                                if "videoOffsetTimeMsec" in replay_action:
                                    offset_ms = int(replay_action["videoOffsetTimeMsec"])
                                    time_in_seconds = offset_ms / 1000.0

                                # メッセージが空でない場合のみ追加
                                if message_text:
                                    normalized.append({
                                        "time_in_seconds": time_in_seconds,
                                        "author": author_name,
                                        "message": message_text,
                                        "timestamp": timestamp_usec // 1000  # ミリ秒に変換
                                    })

            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse chat line: {e}")
                continue

    return normalized


def count_chat_messages(chat_path: str) -> int:
    """
    チャットファイル内のメッセージ数をカウント

    Args:
        chat_path: チャットJSONファイルのパス

    Returns:
        メッセージ数
    """
    try:
        with open(chat_path, "r", encoding="utf-8") as f:
            count = 0
            for line in f:
                if line.strip():
                    count += 1
            return count
    except Exception:
        return 0


def load_chat_messages(chat_path: str) -> List[Dict[str, Any]]:
    """
    チャットJSONファイルを読み込む

    chat-downloaderは1行1JSONの形式（JSONL）で出力する

    Args:
        chat_path: チャットJSONファイルのパス

    Returns:
        チャットメッセージのリスト
    """
    messages = []

    with open(chat_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
                messages.append(msg)
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse chat message: {e}")
                continue

    return messages


