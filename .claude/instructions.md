# KIRINUKI Processor - Claude Code Instructions

## Overview

KIRINUKI Processor is a video processing tool that creates annotated clips of Hiroyuki YouTube videos by adding Whisper-generated subtitles and live chat overlays.

**Key Technology Stack:**
- Python 3.8+ with virtual environment
- OpenAI Whisper (large model) for speech-to-text subtitle generation
- yt-dlp for YouTube video and chat downloading
- FFmpeg for video processing and composition
- ASS format for chat overlays

## Essential Commands

### Setup
```bash
# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate  # Windows

# Install dependencies (if needed)
pip install -r requirements.txt
```

### Main Workflows

**2-Stage Workflow (Recommended):**
```bash
# 1. Initialize config file
python main.py init -o config.txt

# 2. Edit config.txt with VIDEO_URL, START_TIME, END_TIME

# 3. Prepare materials (downloads video, generates subtitles, fetches chat)
python main.py prepare config.txt

# 4. Edit subtitles manually
code data/temp/subs_clip.srt

# 5. Compose final video
python main.py compose config.txt
```

**Full Pipeline (No subtitle editing):**
```bash
python main.py run config.txt
```

### Individual Steps

```bash
# Step 0: Download and clip video
python main.py step0 -u VIDEO_URL -s START_TIME -e END_TIME -o data/temp/clip.webm

# Step 1: Generate Whisper subtitles (default: large model)
python main.py step1 -i data/temp/clip.webm -o data/temp/subs_clip.srt -m large

# Step 2: Fetch chat replay
python main.py step2 -u VIDEO_URL -o data/temp/chat_full.json

# Step 3: Extract chat for clip range
python main.py step3 -i data/temp/chat_full.json -s START_TIME -e END_TIME -o data/temp/chat_clip.json

# Step 4: Generate chat overlay (ASS format)
python main.py step4 -i data/temp/chat_clip.json -o data/temp/chat_overlay.ass

# Step 5: Compose final video
python main.py step5 -v data/temp/clip.webm -s data/temp/subs_clip.srt -c data/temp/chat_overlay.ass -o data/output/final.mp4
```

### Testing

```bash
# Run tests
python -m pytest kirinuki_processor/tests/

# Run with coverage
pytest --cov=kirinuki_processor
```

## Architecture

### Processing Pipeline (6 Steps)

**Step 0: Download & Clip** ([step0_download_clip.py](kirinuki_processor/steps/step0_download_clip.py))
- Downloads YouTube video using yt-dlp
- Clips to START-END range using FFmpeg
- Output: `clip.webm` (16:9 format)

**Step 1: Generate Subtitles** ([step1_generate_subtitles.py](kirinuki_processor/steps/step1_generate_subtitles.py))
- Extracts audio from clipped video (16kHz mono PCM)
- Runs OpenAI Whisper speech recognition (default: large model)
- Generates SRT subtitle file with 0-second base timestamp
- Output: `subs_clip.srt`
- **Critical**: Subtitles are generated from clipped video, so timestamps start at 00:00:00,000

**Step 2: Fetch Chat** ([step2_fetch_chat.py](kirinuki_processor/steps/step2_fetch_chat.py))
- Downloads live chat replay using yt-dlp
- Output: `chat_full.json`

**Step 3: Extract Chat** ([step3_extract_chat.py](kirinuki_processor/steps/step3_extract_chat.py))
- Extracts messages within START-END range
- Rebases timestamps to 0-second origin
- Output: `chat_clip.json`

**Step 4: Generate Overlay** ([step5_generate_overlay.py](kirinuki_processor/steps/step5_generate_overlay.py))
- Creates ASS subtitle file for chat display
- Right-side column with up to 7 visible messages
- Slide animation with 0.3s transitions
- Output: `chat_overlay.ass`

**Step 5: Compose Video** ([step6_compose_video.py](kirinuki_processor/steps/step6_compose_video.py))
- Burns SRT subtitles and ASS chat overlay into video
- FFmpeg command: `-vf "subtitles=subs_clip.srt,ass=chat_overlay.ass"`
- Encoding: H.264 (libx264, CRF 23, medium preset)
- Output: `final.mp4`

### Directory Structure

```
KIRINUKI/
├── main.py                    # CLI entry point
├── config.txt                 # User configuration
├── requirements.txt           # Python dependencies
├── README.md                  # User documentation (Japanese)
├── CLAUDE.md                  # Technical specification (Japanese)
├── .claude/
│   └── instructions.md        # This file (for Claude Code)
├── data/
│   ├── input/                 # Optional: pre-clipped videos
│   ├── temp/                  # Intermediate files
│   │   ├── clip.webm          # Clipped video
│   │   ├── subs_clip.srt      # Whisper-generated subtitles
│   │   ├── chat_full.json     # Full chat replay
│   │   ├── chat_clip.json     # Extracted chat range
│   │   └── chat_overlay.ass   # Chat overlay
│   └── output/                # Final output
│       └── final.mp4          # Completed video
└── kirinuki_processor/
    ├── steps/                 # Processing step modules
    │   ├── step0_download_clip.py
    │   ├── step1_generate_subtitles.py
    │   ├── step2_fetch_chat.py
    │   ├── step3_extract_chat.py
    │   ├── step5_generate_overlay.py
    │   └── step6_compose_video.py
    ├── utils/                 # Utility functions
    │   └── time_utils.py
    └── tests/                 # Test suite
```

## Key Technical Decisions

### Whisper for Subtitle Generation
- **Why**: YouTube subtitles (auto-generated) have poor accuracy for Japanese speech
- **Model**: large (1550M parameters, ~10GB VRAM) for maximum accuracy
- **Alternatives**: medium, small, base, tiny (faster but less accurate)
- **Input**: 16kHz mono PCM audio extracted from video
- **Output**: SRT format with timestamps starting at 00:00:00,000

### 0-Second Timestamp Base
- Subtitles are generated from the **clipped video**, not the original
- No timestamp rebasing needed (unlike old YouTube subtitle system)
- Timestamps directly correspond to the clipped video timeline

### 2-Stage Workflow (prepare + compose)
- **Why**: Allows subtitle editing between generation and video composition
- **prepare**: Runs steps 0-4, stops before video composition
- **compose**: Runs step 5 only using existing materials
- Users can edit `subs_clip.srt` manually and re-run `compose` without regenerating subtitles

### ASS Format for Chat Overlays
- **Why**: ASS supports animations, positioning, and styling
- **Design**: Right column with max 7 visible messages, sliding upward animation
- **Alternative**: Could use SRT, but no animation support

### Step Renumbering History
- **Old System** (YouTube subtitles): 7 steps
  - step1: Fetch YouTube subtitles
  - step2: Rebase subtitle timestamps
  - step3-6: Chat processing and composition
- **New System** (Whisper): 6 steps
  - step1: Generate Whisper subtitles (no rebasing needed)
  - step2-5: Chat processing and composition

## Common Tasks

### Changing Whisper Model
Edit [main.py](../main.py) line ~60 in `run_prepare_pipeline()`:
```python
# Default: large model
success = generate_subtitles_with_whisper(
    clip_path, subs_clip_path,
    model_size="large",  # Change to: medium, small, base, tiny
    verbose=True
)
```

### Customizing Chat Display
Edit [step5_generate_overlay.py](../kirinuki_processor/steps/step5_generate_overlay.py) `OverlayConfig` class (lines 16-44):
- `chat_area_x`: Horizontal position
- `font_size`: Text size
- `max_visible_messages`: Number of simultaneous messages
- `text_color`: ASS color format (&HAABBGGRR)

### Customizing Video Encoding
Edit [step6_compose_video.py](../kirinuki_processor/steps/step6_compose_video.py) `compose_video()` default parameters (lines 18-22):
- `video_codec`: Default libx264 (H.264)
- `crf`: Quality (23 = good balance, lower = higher quality)
- `preset`: Encoding speed (medium, fast, slow, etc.)

## Error Handling

### FFmpeg Not Found
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg
```

### Whisper Memory Error
Use smaller model:
```bash
python main.py step1 -i clip.webm -o subs_clip.srt -m medium
```

### Chat Replay Not Available
- Some videos don't have chat replays
- Processing continues with subtitles only

### Subtitles Not Showing in Video
- Verify SRT format is correct
- Check FFmpeg command includes `-vf subtitles=...`
- Test with VLC or other players (some players don't show burned-in subs)
- Extract frame to verify: `ffmpeg -i final.mp4 -ss 00:00:01 -vframes 1 frame.png`

## Development Guidelines

### Code Style
- Python 3.8+ with type hints
- Docstrings for all public functions
- Use pathlib for cross-platform paths where possible
- Handle errors gracefully (continue processing when possible)

### Testing
- Add tests for new features in `kirinuki_processor/tests/`
- Run pytest before committing

### Git Workflow
- **IMPORTANT**: Never commit/push without explicit user approval
- User will request commits with "コミットプッシュして" (Japanese)
- Follow standard Git Safety Protocol

### File Management
- Keep `data/temp/` for intermediate files
- Clean up test files before finalizing changes
- Use `data/input/` for user-provided files
- Output final videos to `data/output/`

## User Preferences

- **Language**: Japanese (日本語) for communication
- **Commit Policy**: Explicit approval required before git commit/push
- **Documentation**: Keep README.md user-friendly, CLAUDE.md technical (both in Japanese)
- **Testing**: Test functionality before reporting completion

## Changelog

**2025-11-14**: Whisper-based system
- Replaced YouTube subtitle fetching with Whisper speech recognition
- Removed subtitle rebasing (step2_rebase_subtitles.py)
- Added 2-stage workflow (prepare/compose)
- Step renumbering: 7 steps → 6 steps

**2025-11-13**: Initial version
- Created basic pipeline with YouTube subtitle fetching
- Implemented chat overlay system
- Added yt-dlp video downloading

## Reference Documentation

- [README.md](../README.md) - User-facing documentation (Japanese)
- [CLAUDE.md](../CLAUDE.md) - Technical specification (Japanese)
- [OpenAI Whisper Documentation](https://github.com/openai/whisper)
- [FFmpeg Documentation](https://ffmpeg.org/documentation.html)
- [ASS Subtitle Format](http://www.tcax.org/docs/ass-specs.htm)
