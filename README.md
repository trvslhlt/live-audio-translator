# Live Audio Translator

Real-time speech-to-text transcription with automatic translation between English and French.

## For Users

### Requirements

- macOS (Apple Silicon or Intel)
- A working microphone

### Installation

1. Download this project: Click the green **Code** button above, then **Download ZIP**
2. Unzip the downloaded file and open the folder
3. Double-click `install.sh`
   - If macOS asks "Are you sure you want to open it?", click **Open**
   - A Terminal window will appear showing progress
   - Wait for it to finish (this takes a few minutes the first time as it downloads AI models)
   - You can close Terminal when it says "Setup complete"

### Running the App

Double-click `run.sh` to start the app.

If macOS won't open the scripts, right-click → **Open With** → **Terminal**.

### How to Use

1. Select a translation mode:
   - **Auto-detect → English**: Speaks any language, translates to English
   - **French → English (Best)**: Optimized for French speakers
   - **English → French**: For English speakers wanting French translation

2. Check **Save session** if you want to keep the audio and transcript

3. Click **Start Listening** and speak into your microphone

4. The app shows your original speech and the translation in real-time

5. Click **Stop Listening** when done. If saving was enabled, you'll be prompted to choose where to save.

### Saved Sessions

Sessions are saved as folders containing:
- `audio.wav` - Your recording
- `transcript.txt` - Human-readable transcript
- `session.json` - For reloading into the app

Use **Load Session** to review previous recordings.

---

## For Contributors

### Quick Start

```bash
make install
make run
```

### Architecture

- `src/audio/` - PyAudio capture with VAD-based chunking
- `src/transcription/` - Whisper STT (small model)
- `src/translation/` - Argos Translate (offline)
- `src/storage/` - Session persistence with streaming audio
- `src/gui/` - PyQt6 interface

### Key Design Decisions

- Audio streams directly to disk during recording to handle long sessions
- Whisper's translate task is used for X→EN (better quality than Argos for this direction)
- Argos handles EN→FR translation
- Signal handling ensures clean PyAudio shutdown on Ctrl+C

### Make Targets

```
make install      # Set up venv and dependencies
make run          # Run the app
make test         # Quick import/device check
make lint         # Run ruff
make clean        # Remove __pycache__
make clean-all    # Full reset including venv
```
