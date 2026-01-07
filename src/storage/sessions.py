"""Session storage for saving transcription sessions."""

import json
import logging
import re
import shutil
import tempfile
import wave
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

# Default sessions directory
SESSIONS_DIR = Path.home() / ".live-audio-translator" / "sessions"

# File names within a session folder
SESSION_METADATA_FILE = "session.json"
SESSION_AUDIO_FILE = "audio.wav"
SESSION_TRANSCRIPT_FILE = "transcript.txt"

# Audio settings
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1
AUDIO_SAMPLE_WIDTH = 2  # 16-bit


class StreamingAudioWriter:
    """
    Streams audio chunks directly to a temporary WAV file during recording.
    This avoids memory buildup for long recordings.
    """

    def __init__(self):
        self._temp_file: tempfile.NamedTemporaryFile | None = None
        self._wav_file: wave.Wave_write | None = None
        self._total_frames = 0
        self._is_open = False

    def start(self):
        """Start a new audio recording stream."""
        if self._is_open:
            self.close()

        # Create temp file that persists after closing
        self._temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_path = self._temp_file.name
        self._temp_file.close()  # Close so wave can open it

        # Open as WAV for writing
        self._wav_file = wave.open(temp_path, "wb")
        self._wav_file.setnchannels(AUDIO_CHANNELS)
        self._wav_file.setsampwidth(AUDIO_SAMPLE_WIDTH)
        self._wav_file.setframerate(AUDIO_SAMPLE_RATE)

        self._total_frames = 0
        self._is_open = True
        log.info(f"Started streaming audio to: {temp_path}")

    def write_chunk(self, audio_chunk: np.ndarray):
        """
        Write an audio chunk to the stream.

        Args:
            audio_chunk: numpy array of float32 audio data normalized to [-1, 1]
        """
        if not self._is_open or self._wav_file is None:
            log.warning("Attempted to write to closed audio stream")
            return

        # Convert float32 [-1, 1] to int16
        audio_int16 = (audio_chunk * 32767).astype(np.int16)
        self._wav_file.writeframes(audio_int16.tobytes())
        self._total_frames += len(audio_chunk)

    @property
    def duration_seconds(self) -> float:
        """Get the current recording duration in seconds."""
        return self._total_frames / AUDIO_SAMPLE_RATE

    @property
    def temp_path(self) -> Path | None:
        """Get the path to the temporary audio file."""
        if self._temp_file:
            return Path(self._temp_file.name)
        return None

    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._is_open

    def close(self) -> Path | None:
        """
        Close the audio stream and return the temp file path.

        Returns:
            Path to the temporary WAV file, or None if nothing was recorded.
        """
        if not self._is_open:
            return None

        temp_path = None
        if self._wav_file:
            temp_path = Path(self._wav_file._file.name)
            self._wav_file.close()
            self._wav_file = None

        self._is_open = False

        if self._total_frames == 0 and temp_path and temp_path.exists():
            # No audio recorded, clean up empty file
            temp_path.unlink()
            log.info("No audio recorded, removed empty temp file")
            return None

        log.info(f"Closed audio stream: {self.duration_seconds:.1f}s recorded")
        return temp_path

    def discard(self):
        """Discard the recording and clean up the temp file."""
        temp_path = self.close()
        if temp_path and temp_path.exists():
            temp_path.unlink()
            log.info("Discarded audio recording")

    def move_to(self, destination: Path) -> bool:
        """
        Move the temp audio file to the final destination.

        Args:
            destination: Final path for the audio file.

        Returns:
            True if successful, False if no audio or error.
        """
        temp_path = self.close()
        if not temp_path or not temp_path.exists():
            return False

        try:
            shutil.move(str(temp_path), str(destination))
            log.info(f"Moved audio to: {destination}")
            return True
        except Exception as e:
            log.error(f"Failed to move audio file: {e}")
            return False


def sanitize_filename(name: str) -> str:
    """Convert a string to a safe filename."""
    # Replace spaces with underscores, remove unsafe characters
    safe = re.sub(r"[^\w\s-]", "", name)
    safe = re.sub(r"\s+", "_", safe)
    return safe[:50]  # Limit length


@dataclass
class TranscriptEntry:
    """A single transcript entry with original and translated text."""

    timestamp: str
    source_lang: str
    original_text: str
    translated_text: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TranscriptEntry":
        return cls(**data)


@dataclass
class Session:
    """A transcription session containing multiple entries."""

    id: str
    title: str
    created_at: str
    updated_at: str
    language_mode: str
    entries: list[TranscriptEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "language_mode": self.language_mode,
            "entries": [e.to_dict() for e in self.entries],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        entries = [TranscriptEntry.from_dict(e) for e in data.get("entries", [])]
        return cls(
            id=data["id"],
            title=data["title"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            language_mode=data.get("language_mode", "auto"),
            entries=entries,
        )

    def add_entry(self, timestamp: str, source_lang: str, original: str, translated: str):
        """Add a new transcript entry to the session."""
        entry = TranscriptEntry(
            timestamp=timestamp,
            source_lang=source_lang,
            original_text=original,
            translated_text=translated,
        )
        self.entries.append(entry)
        self.updated_at = datetime.now().isoformat()

    def to_text(self) -> str:
        """Export session as plain text."""
        lines = [
            f"Session: {self.title}",
            f"Created: {self.created_at}",
            f"Language Mode: {self.language_mode}",
            "-" * 50,
            "",
        ]
        for entry in self.entries:
            lines.append(f"[{entry.timestamp}]")
            source_label = entry.source_lang.upper()[:2]
            target_label = "EN" if source_label == "FR" else "FR"
            lines.append(f"[{source_label}] {entry.original_text}")
            if entry.translated_text != entry.original_text:
                lines.append(f"[{target_label}] {entry.translated_text}")
            lines.append("")
        return "\n".join(lines)


class SessionManager:
    """Manages saving and loading transcription sessions."""

    def __init__(self, sessions_dir: Path | None = None):
        self.sessions_dir = sessions_dir or SESSIONS_DIR
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._current_session: Session | None = None

    def new_session(self, title: str | None = None, language_mode: str = "auto") -> Session:
        """Create a new session."""
        now = datetime.now()
        session_id = now.strftime("%Y%m%d_%H%M%S")
        default_title = now.strftime("Session %Y-%m-%d %H:%M")

        self._current_session = Session(
            id=session_id,
            title=title or default_title,
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            language_mode=language_mode,
            entries=[],
        )
        log.info(f"New session created: {self._current_session.title}")
        return self._current_session

    @property
    def current_session(self) -> Session | None:
        return self._current_session

    def add_entry(self, timestamp: str, source_lang: str, original: str, translated: str):
        """Add an entry to the current session."""
        if self._current_session is None:
            self.new_session()
        self._current_session.add_entry(timestamp, source_lang, original, translated)

    def save_session_folder(
        self,
        session: Session | None = None,
        audio_chunks: list[np.ndarray] | None = None,
        audio_temp_path: Path | None = None,
        parent_dir: Path | None = None,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> Path:
        """
        Save a session as a folder containing all files.

        Creates a folder structure:
            {title}_{id}/
                session.json    - Machine-readable metadata (for reloading)
                transcript.txt  - Human-readable transcript
                audio.wav       - Audio recording (if available)

        Args:
            session: Session to save (uses current session if None).
            audio_chunks: List of audio numpy arrays to save (legacy, memory-based).
            audio_temp_path: Path to streaming audio temp file (preferred).
            parent_dir: Parent directory for the session folder.
            progress_callback: Optional callback(percent, status_message).

        Returns:
            Path to the created session folder.
        """
        session = session or self._current_session
        if session is None:
            raise ValueError("No session to save")

        def report_progress(percent: int, message: str):
            if progress_callback:
                progress_callback(percent, message)

        report_progress(0, "Creating session folder...")

        target_parent = parent_dir or self.sessions_dir
        target_parent.mkdir(parents=True, exist_ok=True)

        # Create folder name from title and ID
        folder_name = f"{sanitize_filename(session.title)}_{session.id}"
        session_folder = target_parent / folder_name
        session_folder.mkdir(parents=True, exist_ok=True)

        report_progress(10, "Saving session metadata...")

        # Save session.json (machine-readable, for reloading)
        metadata_path = session_folder / SESSION_METADATA_FILE
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)
        log.info(f"Session metadata saved: {metadata_path}")

        report_progress(20, "Saving transcript...")

        # Save transcript.txt (human-readable)
        transcript_path = session_folder / SESSION_TRANSCRIPT_FILE
        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(session.to_text())
        log.info(f"Transcript saved: {transcript_path}")

        report_progress(30, "Saving audio...")

        # Save audio - prefer streaming temp file, fall back to chunks
        audio_path = session_folder / SESSION_AUDIO_FILE

        if audio_temp_path and audio_temp_path.exists():
            # Move streaming audio file (instant, no memory usage)
            report_progress(50, "Moving audio file...")
            shutil.move(str(audio_temp_path), str(audio_path))
            log.info(f"Audio moved to: {audio_path}")
            report_progress(90, "Audio saved")

        elif audio_chunks:
            # Legacy: concatenate chunks in memory (for backward compatibility)
            report_progress(40, "Processing audio chunks...")
            combined = np.concatenate(audio_chunks)

            report_progress(60, "Converting audio format...")
            audio_int16 = (combined * 32767).astype(np.int16)

            report_progress(70, "Writing audio file...")
            with wave.open(str(audio_path), "wb") as wav_file:
                wav_file.setnchannels(AUDIO_CHANNELS)
                wav_file.setsampwidth(AUDIO_SAMPLE_WIDTH)
                wav_file.setframerate(AUDIO_SAMPLE_RATE)
                wav_file.writeframes(audio_int16.tobytes())

            duration = len(combined) / AUDIO_SAMPLE_RATE
            log.info(f"Audio saved: {audio_path} ({duration:.1f}s)")
            report_progress(90, "Audio saved")

        report_progress(100, "Complete!")
        return session_folder

    def load_session_folder(self, folder_path: Path) -> Session:
        """
        Load a session from a folder.

        Args:
            folder_path: Path to the session folder.

        Returns:
            The loaded Session object.
        """
        metadata_path = folder_path / SESSION_METADATA_FILE
        if not metadata_path.exists():
            raise FileNotFoundError(f"No session.json found in: {folder_path}")

        with open(metadata_path, encoding="utf-8") as f:
            data = json.load(f)

        session = Session.from_dict(data)
        log.info(f"Session loaded from folder: {session.title}")
        return session

    def get_folder_audio_path(self, folder_path: Path) -> Path | None:
        """Get the audio file path from a session folder, if it exists."""
        audio_path = folder_path / SESSION_AUDIO_FILE
        return audio_path if audio_path.exists() else None

    # Legacy methods for backward compatibility with internal session storage

    def save_session(self, session: Session | None = None, save_dir: Path | None = None) -> Path:
        """Save a session to disk (legacy format - single JSON file)."""
        session = session or self._current_session
        if session is None:
            raise ValueError("No session to save")

        target_dir = save_dir or self.sessions_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        filepath = target_dir / f"{session.id}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)

        log.info(f"Session saved: {filepath}")
        return filepath

    def load_session(self, session_id: str) -> Session:
        """Load a session from disk (legacy format)."""
        filepath = self.sessions_dir / f"{session_id}.json"
        if not filepath.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")

        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        session = Session.from_dict(data)
        log.info(f"Session loaded: {session.title}")
        return session

    def list_sessions(self) -> list[dict]:
        """List all saved sessions in internal storage (metadata only)."""
        sessions = []
        for filepath in sorted(self.sessions_dir.glob("*.json"), reverse=True):
            try:
                with open(filepath, encoding="utf-8") as f:
                    data = json.load(f)
                session_id = data["id"]
                audio_path = self.sessions_dir / f"{session_id}.wav"
                sessions.append(
                    {
                        "id": session_id,
                        "title": data["title"],
                        "created_at": data["created_at"],
                        "entry_count": len(data.get("entries", [])),
                        "has_audio": audio_path.exists(),
                    }
                )
            except (json.JSONDecodeError, KeyError) as e:
                log.warning(f"Failed to read session {filepath}: {e}")
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and its audio file if present."""
        filepath = self.sessions_dir / f"{session_id}.json"
        audio_path = self.sessions_dir / f"{session_id}.wav"

        deleted = False
        if filepath.exists():
            filepath.unlink()
            deleted = True
        if audio_path.exists():
            audio_path.unlink()

        if deleted:
            log.info(f"Session deleted: {session_id}")
        return deleted

    def export_session_text(self, session_id: str) -> str:
        """Export a session as plain text."""
        session = self.load_session(session_id)
        return session.to_text()

    def rename_session(self, session_id: str, new_title: str):
        """Rename a session."""
        session = self.load_session(session_id)
        session.title = new_title
        session.updated_at = datetime.now().isoformat()
        self.save_session(session)
        log.info(f"Session renamed to: {new_title}")

    def save_session_audio(
        self, session_id: str, audio_chunks: list[np.ndarray], save_dir: Path | None = None
    ) -> Path:
        """Save audio chunks as a WAV file (legacy format)."""
        if not audio_chunks:
            raise ValueError("No audio chunks to save")

        target_dir = save_dir or self.sessions_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        combined = np.concatenate(audio_chunks)
        audio_int16 = (combined * 32767).astype(np.int16)

        audio_path = target_dir / f"{session_id}.wav"
        with wave.open(str(audio_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(audio_int16.tobytes())

        log.info(f"Session audio saved: {audio_path} ({len(combined) / 16000:.1f}s)")
        return audio_path

    def get_audio_path(self, session_id: str) -> Path | None:
        """Get the path to a session's audio file, if it exists."""
        audio_path = self.sessions_dir / f"{session_id}.wav"
        return audio_path if audio_path.exists() else None

    def has_audio(self, session_id: str) -> bool:
        """Check if a session has an audio recording."""
        return self.get_audio_path(session_id) is not None
