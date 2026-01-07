"""Main application window for Live Audio Translator."""

import logging
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QTextEdit, QLabel, QFrame,
    QMessageBox, QApplication, QInputDialog, QFileDialog,
    QCheckBox, QProgressDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QSettings
from PyQt6.QtGui import QFont, QTextCursor

log = logging.getLogger(__name__)


class TranscriptionWorker(QThread):
    """Worker thread for audio capture, transcription, and translation."""

    # Signals to communicate with main thread
    # original, translated, source_lang, timestamp, audio_chunk
    text_ready = pyqtSignal(str, str, str, str, object)
    error_occurred = pyqtSignal(str)
    status_changed = pyqtSignal(str)

    def __init__(self, audio_capture, transcriber, translator):
        super().__init__()
        self.audio_capture = audio_capture
        self.transcriber = transcriber
        self.translator = translator
        self._running = False
        self._language_mode = 'auto'  # 'auto', 'en', 'fr'
        self._target_language = None  # None for auto, or 'en'/'fr'
        self._use_whisper_translate = False  # Use Whisper's direct translation for FR->EN

    def set_language_mode(self, mode: str, target: str | None = None, use_whisper_translate: bool = False):
        """Set the language detection/translation mode."""
        self._language_mode = mode
        self._target_language = target
        self._use_whisper_translate = use_whisper_translate

    def run(self):
        """Main worker loop."""
        self._running = True
        self.status_changed.emit("Listening...")
        log.info("Worker started - listening for audio...")

        while self._running:
            try:
                # Get audio chunk
                audio_chunk = self.audio_capture.get_chunk(timeout=0.5)
                if audio_chunk is None:
                    continue

                chunk_duration = len(audio_chunk) / 16000  # 16kHz sample rate
                log.info(f"Processing audio chunk ({chunk_duration:.1f}s)...")
                self.status_changed.emit("Processing...")
                timestamp = datetime.now().strftime("%H:%M:%S")

                # For FR->EN, use Whisper's direct translation (better quality)
                # But also get the original transcription for display
                if self._use_whisper_translate and self._target_language == 'en':
                    # First, transcribe to get original text in source language
                    log.info("  Transcribing (source language)...")
                    transcribe_result = self.transcriber.transcribe(
                        audio_chunk,
                        language=self._language_mode if self._language_mode != 'auto' else None,
                        task='transcribe'
                    )
                    original_text = transcribe_result['text']
                    detected_lang = transcribe_result['language']

                    if not original_text.strip():
                        log.info("  (silence/no speech detected)")
                        self.status_changed.emit("Listening...")
                        continue

                    log.info(f"  Detected: [{detected_lang.upper()}] {original_text[:60]}{'...' if len(original_text) > 60 else ''}")

                    # If source is already English, no translation needed
                    if detected_lang.startswith('en'):
                        log.info("  (source is English, no translation needed)")
                        self.text_ready.emit(original_text, original_text, detected_lang, timestamp, audio_chunk)
                    else:
                        # Now translate using Whisper's translate task
                        log.info("  Translating to English (Whisper)...")
                        translate_result = self.transcriber.transcribe(
                            audio_chunk,
                            language=detected_lang,
                            task='translate'
                        )
                        translated_text = translate_result['text']
                        log.info(f"  Translated: [EN] {translated_text[:60]}{'...' if len(translated_text) > 60 else ''}")
                        self.text_ready.emit(original_text, translated_text, detected_lang, timestamp, audio_chunk)

                else:
                    # Standard transcribe -> translate pipeline (for EN->FR)
                    log.info("  Transcribing...")
                    if self._language_mode == 'auto':
                        result = self.transcriber.transcribe(audio_chunk, language=None)
                    else:
                        result = self.transcriber.transcribe(audio_chunk, language=self._language_mode)

                    original_text = result['text']
                    detected_lang = result['language']

                    if not original_text.strip():
                        log.info("  (silence/no speech detected)")
                        self.status_changed.emit("Listening...")
                        continue

                    log.info(f"  Detected: [{detected_lang.upper()}] {original_text[:60]}{'...' if len(original_text) > 60 else ''}")

                    # Translate using Argos (for EN->FR or when not using Whisper translate)
                    log.info("  Translating (Argos)...")
                    translated_text, target_lang = self.translator.translate_auto(
                        original_text,
                        detected_lang,
                        self._target_language
                    )
                    log.info(f"  Translated: [{target_lang.upper()}] {translated_text[:60]}{'...' if len(translated_text) > 60 else ''}")

                    self.text_ready.emit(original_text, translated_text, detected_lang, timestamp, audio_chunk)

                self.status_changed.emit("Listening...")

            except Exception as e:
                log.error(f"Worker error: {e}")
                self.error_occurred.emit(str(e))
                self.status_changed.emit("Error - check console")

    def stop(self):
        """Stop the worker."""
        log.info("Worker stopping...")
        self._running = False


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Live Audio Translator")
        self.setMinimumSize(600, 500)

        # Components (initialized later)
        self.audio_capture = None
        self.transcriber = None
        self.translator = None
        self.worker = None

        # Session management
        from src.storage.sessions import SessionManager, StreamingAudioWriter
        self.session_manager = SessionManager()
        self._recording_session = False
        self._audio_writer = StreamingAudioWriter()  # Streams audio to disk

        # Settings for remembering last save location
        self._settings = QSettings("LiveAudioTranslator", "LiveAudioTranslator")

        self._setup_ui()

    def _setup_ui(self):
        """Set up the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header with title
        title_label = QLabel("Live Audio Translator")
        title_label.setFont(QFont("", 18, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Control panel
        control_frame = QFrame()
        control_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        control_layout = QHBoxLayout(control_frame)

        # Language selector
        lang_label = QLabel("Mode:")
        self.language_combo = QComboBox()
        self.language_combo.addItem("Auto-detect \u2192 English", "auto")
        self.language_combo.addItem("French \u2192 English (Best)", "fr_to_en")
        self.language_combo.addItem("English \u2192 French", "en_to_fr")
        self.language_combo.setMinimumWidth(180)
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)

        control_layout.addWidget(lang_label)
        control_layout.addWidget(self.language_combo)
        control_layout.addStretch()

        # Save session checkbox
        self.save_session_checkbox = QCheckBox("Save session")
        self.save_session_checkbox.setToolTip(
            "When enabled, audio and transcript will be saved\n"
            "when you stop listening. You can review saved\n"
            "sessions later using 'Load Session'."
        )
        control_layout.addWidget(self.save_session_checkbox)

        control_layout.addSpacing(10)

        # Start/Stop button
        self.start_button = QPushButton("Start Listening")
        self.start_button.setMinimumSize(150, 40)
        self.start_button.setFont(QFont("", 12, QFont.Weight.Bold))
        self.start_button.clicked.connect(self._toggle_listening)
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        control_layout.addWidget(self.start_button)

        layout.addWidget(control_frame)

        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.status_label)

        # Transcript area
        transcript_label = QLabel("Transcript:")
        transcript_label.setFont(QFont("", 11, QFont.Weight.Bold))
        layout.addWidget(transcript_label)

        self.transcript_area = QTextEdit()
        self.transcript_area.setReadOnly(True)
        self.transcript_area.setFont(QFont("", 11))
        self.transcript_area.setPlaceholderText(
            "Transcribed and translated text will appear here...\n\n"
            "Original text is shown in regular format.\n"
            "Translated text is shown in blue.\n\n"
            "Tip: Check 'Save session' to record audio and transcript."
        )
        layout.addWidget(self.transcript_area, 1)

        # Bottom buttons
        button_layout = QHBoxLayout()

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self._clear_transcript)
        button_layout.addWidget(self.clear_button)

        self.copy_button = QPushButton("Copy All")
        self.copy_button.clicked.connect(self._copy_transcript)
        button_layout.addWidget(self.copy_button)

        button_layout.addStretch()

        # Load session button
        self.load_session_button = QPushButton("Load Session...")
        self.load_session_button.clicked.connect(self._load_session_folder)
        button_layout.addWidget(self.load_session_button)

        layout.addLayout(button_layout)

    def _load_session_folder(self):
        """Load a previously saved session folder."""
        # Get last used directory
        default_dir = self._settings.value(
            "last_save_dir",
            str(Path.home() / "Documents")
        )

        # Prompt user to select a session folder
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select a session folder to load",
            default_dir,
            QFileDialog.Option.ShowDirsOnly
        )

        if not folder_path:
            return

        folder = Path(folder_path)

        # Check if this is a valid session folder
        session_file = folder / "session.json"
        if not session_file.exists():
            QMessageBox.warning(
                self,
                "Invalid Session Folder",
                "This folder doesn't contain a session.json file.\n\n"
                "Please select a folder that was saved by this app."
            )
            return

        try:
            # Load the session
            session = self.session_manager.load_session_folder(folder)

            # Clear current transcript and display loaded session
            self.transcript_area.clear()
            for entry in session.entries:
                self._display_entry(
                    entry.original_text,
                    entry.translated_text,
                    entry.source_lang,
                    entry.timestamp
                )

            # Check for audio
            audio_path = self.session_manager.get_folder_audio_path(folder)
            audio_info = ""
            if audio_path:
                audio_info = "\n\nAudio file available - open the folder to play it."

            self.status_label.setText(f"Loaded: {session.title}")

            QMessageBox.information(
                self,
                "Session Loaded",
                f"Loaded session: {session.title}\n"
                f"Entries: {len(session.entries)}\n"
                f"Created: {session.created_at[:10]}"
                f"{audio_info}"
            )

        except Exception as e:
            log.error(f"Failed to load session: {e}")
            QMessageBox.critical(
                self,
                "Load Error",
                f"Failed to load session:\n{e}"
            )

    def _display_entry(self, original: str, translated: str, source_lang: str, timestamp: str):
        """Display a transcript entry in the UI."""
        cursor = self.transcript_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        source_label = "EN" if source_lang.startswith('en') else "FR" if source_lang.startswith('fr') else source_lang.upper()
        target_label = "FR" if source_label == "EN" else "EN"

        cursor.insertHtml(f'<span style="color: #888; font-size: 10px;">{timestamp}</span><br>')
        cursor.insertHtml(f'<span style="color: #666;">[{source_label}]</span> {original}<br>')
        if translated != original:
            cursor.insertHtml(f'<span style="color: #2196F3;">[{target_label}] {translated}</span><br>')
        cursor.insertHtml('<br>')

        self.transcript_area.setTextCursor(cursor)
        self.transcript_area.ensureCursorVisible()

    def initialize_components(self, audio_capture, transcriber, translator):
        """Initialize the audio/ML components."""
        self.audio_capture = audio_capture
        self.transcriber = transcriber
        self.translator = translator

    def _toggle_listening(self):
        """Toggle audio capture on/off."""
        if self.worker and self.worker.isRunning():
            self._stop_listening()
        else:
            self._start_listening()

    def _start_listening(self):
        """Start capturing and translating audio."""
        if not all([self.audio_capture, self.transcriber, self.translator]):
            QMessageBox.warning(
                self,
                "Not Ready",
                "The application is still initializing. Please wait."
            )
            return

        try:
            # Start session recording if checkbox is checked
            if self.save_session_checkbox.isChecked():
                self._recording_session = True
                language_mode = self.language_combo.currentData()
                self.session_manager.new_session(language_mode=language_mode)
                # Start streaming audio to temp file
                self._audio_writer.start()
                log.info("Session recording started (streaming to temp file)")

            # Start audio capture
            self.audio_capture.start()

            # Create and start worker
            self.worker = TranscriptionWorker(
                self.audio_capture,
                self.transcriber,
                self.translator
            )
            self.worker.text_ready.connect(self._on_text_ready)
            self.worker.error_occurred.connect(self._on_error)
            self.worker.status_changed.connect(self._on_status_changed)

            # Apply current language setting
            self._on_language_changed(self.language_combo.currentIndex())

            self.worker.start()

            # Update UI
            self.start_button.setText("Stop Listening")
            self.start_button.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #da190b;
                }
                QPushButton:pressed {
                    background-color: #c41a0d;
                }
            """)
            self.language_combo.setEnabled(False)
            self.save_session_checkbox.setEnabled(False)

            if self._recording_session:
                self.status_label.setText("Recording session...")

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to start audio capture:\n{str(e)}"
            )

    def _stop_listening(self):
        """Stop capturing audio."""
        if self.worker:
            self.worker.stop()
            self.worker.wait()
            self.worker = None

        if self.audio_capture:
            self.audio_capture.stop()

        # Handle session saving
        if self._recording_session:
            self._finish_session()

        # Update UI
        self.start_button.setText("Start Listening")
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        self.language_combo.setEnabled(True)
        self.save_session_checkbox.setEnabled(True)
        self.status_label.setText("Stopped")

    def _finish_session(self):
        """Finish and save the current session."""
        self._recording_session = False

        session = self.session_manager.current_session
        if not session or not session.entries:
            log.info("No content to save in session")
            self._audio_writer.discard()
            return

        # Close the audio stream and get the temp file path
        audio_temp_path = self._audio_writer.close()
        audio_duration = self._audio_writer.duration_seconds

        # Get last used save directory, default to Documents
        default_dir = self._settings.value(
            "last_save_dir",
            str(Path.home() / "Documents")
        )

        # Build info string
        duration_str = ""
        if audio_duration > 0:
            mins = int(audio_duration // 60)
            secs = int(audio_duration % 60)
            duration_str = f", {mins}:{secs:02d} audio"

        # Prompt user for save location
        save_dir = QFileDialog.getExistingDirectory(
            self,
            f"Choose where to save session ({len(session.entries)} entries{duration_str})",
            default_dir,
            QFileDialog.Option.ShowDirsOnly
        )

        if not save_dir:
            # User cancelled - ask if they want to discard
            reply = QMessageBox.question(
                self,
                "Discard Session?",
                "No save location selected. Discard this recording session?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                # Try again - but we need to restore the audio temp path
                self._recording_session = True
                # Note: audio is already closed, so re-store temp path for next attempt
                self._pending_audio_temp_path = audio_temp_path
                self._finish_session_with_audio(audio_temp_path)
                return
            else:
                log.info("Session discarded by user")
                # Clean up temp audio file
                if audio_temp_path and audio_temp_path.exists():
                    audio_temp_path.unlink()
                return

        # Remember this location for next time
        self._settings.setValue("last_save_dir", save_dir)
        save_path = Path(save_dir)

        # Ask for session title
        default_title = datetime.now().strftime("Session %Y-%m-%d %H:%M")
        title, ok = QInputDialog.getText(
            self,
            "Session Title",
            "Enter a title for this session:",
            text=default_title
        )

        if not ok:
            # User cancelled title - use default
            title = default_title

        # Update session title
        session.title = title if title else default_title

        # Create and show progress dialog
        progress = QProgressDialog("Saving session...", None, 0, 100, self)
        progress.setWindowTitle("Saving")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()
        QApplication.processEvents()

        def update_progress(percent: int, message: str):
            progress.setValue(percent)
            progress.setLabelText(message)
            QApplication.processEvents()

        try:
            # Save the session as a folder containing all files
            session_folder = self.session_manager.save_session_folder(
                session=session,
                audio_temp_path=audio_temp_path,
                parent_dir=save_path,
                progress_callback=update_progress
            )

            progress.close()

            self.status_label.setText(f"Session saved: {session.title}")
            log.info(f"Session saved to folder: {session_folder}")

            # Build file list for message
            files = ["session.json (for reloading)", "transcript.txt (readable)"]
            if audio_temp_path:
                files.append(f"audio.wav ({mins}:{secs:02d} recording)")

            QMessageBox.information(
                self,
                "Session Saved",
                f"Session saved to:\n{session_folder}\n\n"
                f"Contains:\n" + "\n".join(f"  - {f}" for f in files)
            )

        except Exception as e:
            progress.close()
            log.error(f"Failed to save session: {e}")
            QMessageBox.warning(
                self,
                "Save Error",
                f"Failed to save session:\n{e}"
            )
            # Clean up temp file on error
            if audio_temp_path and audio_temp_path.exists():
                audio_temp_path.unlink()

    def _finish_session_with_audio(self, audio_temp_path):
        """Continue finishing session with existing audio temp file."""
        self._recording_session = False

        session = self.session_manager.current_session
        if not session or not session.entries:
            log.info("No content to save in session")
            if audio_temp_path and audio_temp_path.exists():
                audio_temp_path.unlink()
            return

        # Get last used save directory
        default_dir = self._settings.value(
            "last_save_dir",
            str(Path.home() / "Documents")
        )

        # Prompt user for save location
        save_dir = QFileDialog.getExistingDirectory(
            self,
            f"Choose where to save session ({len(session.entries)} entries)",
            default_dir,
            QFileDialog.Option.ShowDirsOnly
        )

        if not save_dir:
            reply = QMessageBox.question(
                self,
                "Discard Session?",
                "No save location selected. Discard this recording session?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                self._recording_session = True
                self._finish_session_with_audio(audio_temp_path)
                return
            else:
                if audio_temp_path and audio_temp_path.exists():
                    audio_temp_path.unlink()
                return

        self._settings.setValue("last_save_dir", save_dir)
        save_path = Path(save_dir)

        default_title = datetime.now().strftime("Session %Y-%m-%d %H:%M")
        title, ok = QInputDialog.getText(
            self, "Session Title", "Enter a title:", text=default_title
        )
        session.title = title if (ok and title) else default_title

        progress = QProgressDialog("Saving session...", None, 0, 100, self)
        progress.setWindowTitle("Saving")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()

        def update_progress(percent: int, message: str):
            progress.setValue(percent)
            progress.setLabelText(message)
            QApplication.processEvents()

        try:
            session_folder = self.session_manager.save_session_folder(
                session=session,
                audio_temp_path=audio_temp_path,
                parent_dir=save_path,
                progress_callback=update_progress
            )
            progress.close()
            self.status_label.setText(f"Session saved: {session.title}")
            QMessageBox.information(self, "Session Saved", f"Saved to:\n{session_folder}")
        except Exception as e:
            progress.close()
            log.error(f"Failed to save session: {e}")
            QMessageBox.warning(self, "Save Error", f"Failed to save:\n{e}")
            if audio_temp_path and audio_temp_path.exists():
                audio_temp_path.unlink()

    def _on_language_changed(self, index):
        """Handle language mode change."""
        mode_data = self.language_combo.currentData()

        if self.worker:
            if mode_data == "auto":
                # Auto mode: use Whisper translate when non-English is detected
                self.worker.set_language_mode('auto', 'en', use_whisper_translate=True)
            elif mode_data == "fr_to_en":
                # French to English: use Whisper's direct translation (better quality)
                self.worker.set_language_mode('fr', 'en', use_whisper_translate=True)
            elif mode_data == "en_to_fr":
                # English to French: use Argos (Whisper can only translate TO English)
                self.worker.set_language_mode('en', 'fr', use_whisper_translate=False)

    @pyqtSlot(str, str, str, str, object)
    def _on_text_ready(self, original: str, translated: str, source_lang: str, timestamp: str, audio_chunk):
        """Handle new transcription/translation."""
        # Display the entry in the UI
        self._display_entry(original, translated, source_lang, timestamp)

        # Add to current session if recording
        if self._recording_session and self.session_manager.current_session:
            self.session_manager.add_entry(timestamp, source_lang, original, translated)
            # Stream audio chunk to temp file (no memory buildup)
            if audio_chunk is not None and self._audio_writer.is_recording:
                self._audio_writer.write_chunk(audio_chunk)

    @pyqtSlot(str)
    def _on_error(self, error_message: str):
        """Handle errors from worker."""
        print(f"Error: {error_message}")

    @pyqtSlot(str)
    def _on_status_changed(self, status: str):
        """Update status label."""
        if self._recording_session:
            entries = len(self.session_manager.current_session.entries) if self.session_manager.current_session else 0
            duration = self._audio_writer.duration_seconds
            mins = int(duration // 60)
            secs = int(duration % 60)
            self.status_label.setText(f"{status} (Recording: {entries} entries, {mins}:{secs:02d})")
        else:
            self.status_label.setText(status)

    def _clear_transcript(self):
        """Clear the transcript area."""
        self.transcript_area.clear()

    def _copy_transcript(self):
        """Copy transcript to clipboard."""
        text = self.transcript_area.toPlainText()
        if text:
            clipboard = QApplication.clipboard()
            clipboard.setText(text)
            self.status_label.setText("Copied to clipboard!")

    def closeEvent(self, event):
        """Handle window close."""
        # If recording, ask about saving
        if self._recording_session and self.session_manager.current_session:
            if self.session_manager.current_session.entries:
                reply = QMessageBox.question(
                    self,
                    "Session in Progress",
                    "You have a recording session in progress. Save it before closing?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
                )
                if reply == QMessageBox.StandardButton.Cancel:
                    event.ignore()
                    return
                if reply == QMessageBox.StandardButton.Yes:
                    self._stop_listening()
                else:
                    # Discard audio
                    self._audio_writer.discard()

        self._stop_listening()
        if self.audio_capture:
            self.audio_capture.cleanup()
        event.accept()
