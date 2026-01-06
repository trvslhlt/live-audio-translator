# Live Audio Translation Application - Project Definition

## Overview
An application that listens to live audio and translates it in real-time.

---

## Clarifying Questions

### Audio Input
1. What audio source(s) should be supported?
   - [x] Microphone input (local device)
   - [ ] System audio (e.g., from video calls, media players)
   - [ ] Audio stream URL (e.g., radio, podcast)
   - [ ] Other: _______________

2. Should the app support multiple audio input devices simultaneously?
   - [ ] Yes
   - [x] No

### Languages
3. What source languages need to be supported?
   - [ ] Single language (specify): _______________
   - [x] Multiple languages (list): english, french
   - [x] Auto-detect source language

4. What target languages for translation?
   - [ ] Single language (specify): _______________
   - [x] Multiple languages (list): french, english

5. Should the app support switching languages on-the-fly?
   - [x] Yes
   - [ ] No

### Output
6. How should translations be displayed/delivered?
   - [x] On-screen text (subtitles/captions)
   - [ ] Text-to-speech (spoken translation)
   - [x] Log file / transcript
   - [ ] API/webhook output
   - [ ] Other: _______________

7. What latency is acceptable for translations?
   - [ ] Real-time (< 1 second)
   - [ ] Near real-time (1-3 seconds)
   - [x] Slight delay acceptable (3-5 seconds)
   - [ ] No strict requirement

### Platform
8. What platform(s) should this run on?
   - [x] Desktop (macOS)
   - [ ] Desktop (Windows)
   - [ ] Desktop (Linux)
   - [ ] Web browser
   - [ ] Mobile (iOS)
   - [ ] Mobile (Android)
   - [ ] CLI tool

9. Should this be a standalone application or integrate with other tools?
   - [x] Standalone
   - [ ] Integration with: _______________

### Technology Preferences
10. Do you have preferences for speech-to-text services?
    - [x] OpenAI Whisper (local or API)
    - [ ] Google Cloud Speech-to-Text
    - [ ] Azure Speech Services
    - [ ] AWS Transcribe
    - [ ] Deepgram
    - [ ] No preference / recommend one

11. Do you have preferences for translation services?
    - [ ] OpenAI GPT
    - [ ] Google Translate API
    - [ ] DeepL
    - [ ] Azure Translator
    - [ ] AWS Translate
    - [x] (zero cost)
    - [ ] No preference / recommend one

12. Local processing vs cloud-based?
    - [ ] Fully local (privacy-focused, no internet required)
    - [ ] Cloud-based (better accuracy, requires internet)
    - [x] Hybrid (local when possible, cloud fallback)

### User Interface
13. What type of UI is preferred?
    - [x] Graphical UI (window-based)
    - [ ] System tray / menu bar app
    - [ ] Command-line interface
    - [ ] Overlay (always on top, like game overlays)
    - [ ] No UI (background service)

---

## Additional Requirements

### Functional Requirements
<!-- Add specific features and functionality requirements here -->
- this application is intended for non-technical users, so all user-facing controls should be easily understandable

### Non-Functional Requirements
<!-- Add performance, security, scalability requirements here -->
-
-
-

### Constraints
<!-- Add any technical, budget, or timeline constraints here -->
- there is no money available for this project
-
-

### Nice-to-Have Features
<!-- Add features that would be good but aren't essential -->
- allow users store sessions: audio, input text, and translated text. tag these pieces of content with timestamps and allow the user to title the session
-
-

---

## Use Cases

### Primary Use Case
- this will be used by a law student that primarily speaks english, but is also proficient in French. They would like to be able to check their understanding of French lectures in neasr real-time.


### Secondary Use Cases
<!-- List other scenarios where this would be useful -->
-
-

---

## Success Criteria
<!-- How will we know the project is successful? -->
- The project can successfully be set up on a non-technical user's computer
- The user is able to see live translations
-

---

## Notes
<!-- Any additional notes, references, or context -->


---

## Technical Decisions (Finalized)

### Speech-to-Text
- **Engine:** OpenAI Whisper (local)
- **Model:** `small` (~465 MB, ~2 GB RAM)
- **Rationale:** Good accuracy for clear lecture audio, fits within 3-5 second latency budget

### Translation
- **Engine:** Argos Translate
- **Rationale:** Fully offline, free, excellent EN↔FR support, no API costs

### User Interface
- **Framework:** Python + PyQt6
- **Rationale:** Modern appearance, good macOS support, easier distribution

### Distribution
- **Method:** Shell install script (`install.sh`)
- **What it does:**
  1. Checks for Python 3.9+ (prompts to install via Homebrew if missing)
  2. Creates isolated virtual environment
  3. Installs Python dependencies
  4. Downloads Whisper `small` model
  5. Downloads Argos EN↔FR language packages
  6. Creates desktop launcher

---

## Technical Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                        PyQt6 GUI                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Controls    │  │ Live Text   │  │ Session Manager     │  │
│  │ - Start/Stop│  │ - Original  │  │ - Save/Load/Export  │  │
│  │ - Language  │  │ - Translated│  │                     │  │
│  │ - Mic Select│  │             │  │                     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Audio Pipeline                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Mic Input   │─▶│ Audio Buffer│─▶│ Whisper STT         │  │
│  │ (PyAudio)   │  │ (chunks)    │  │ (local, small)      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Translation Pipeline                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Language    │─▶│ Argos       │─▶│ Output Queue        │  │
│  │ Detection   │  │ Translate   │  │ (to GUI)            │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Storage (Nice-to-Have)                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ SQLite Database                                     │    │
│  │ - Sessions (title, created_at)                      │    │
│  │ - Segments (timestamp, original, translated, audio) │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Key Dependencies

| Package | Purpose |
|---------|---------|
| `openai-whisper` | Speech-to-text |
| `argostranslate` | Translation |
| `PyQt6` | GUI framework |
| `pyaudio` | Microphone input |
| `numpy` | Audio processing |
| `sqlite3` | Session storage (built-in) |

### File Structure

```
live-audio-translator/
├── install.sh              # One-command installer
├── run.sh                  # Launch script
├── requirements.txt        # Python dependencies
├── src/
│   ├── main.py            # Entry point
│   ├── gui/
│   │   ├── main_window.py # Main application window
│   │   └── widgets.py     # Custom UI components
│   ├── audio/
│   │   ├── capture.py     # Microphone input handling
│   │   └── buffer.py      # Audio chunk management
│   ├── transcription/
│   │   └── whisper.py     # Whisper integration
│   ├── translation/
│   │   └── argos.py       # Argos Translate integration
│   └── storage/
│       └── sessions.py    # Session save/load (nice-to-have)
└── data/
    ├── models/            # Downloaded models
    └── sessions/          # Saved session data
```

---

## Implementation Phases

### Phase 1: Core Functionality (MVP)
- [ ] Audio capture from microphone
- [ ] Whisper transcription pipeline
- [ ] Argos translation pipeline
- [ ] Basic GUI with start/stop and live text display
- [ ] Language selection (EN→FR, FR→EN)

### Phase 2: User Experience
- [ ] Microphone device selection
- [ ] Auto-detect source language
- [ ] Transcript export (copy/save as text file)
- [ ] Error handling and user-friendly messages

### Phase 3: Nice-to-Have
- [ ] Session storage with timestamps
- [ ] Session naming and management
- [ ] Audio recording alongside transcript
