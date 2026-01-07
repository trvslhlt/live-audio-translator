"""Main entry point for Live Audio Translator."""

import sys
import signal
import logging
import atexit

from PyQt6.QtWidgets import QApplication, QLabel
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger(__name__)

# Global reference for cleanup
_app_window = None
_audio_capture = None


def show_loading_message(app: QApplication) -> QLabel:
    """Show a loading message while models are loading."""
    splash = QLabel("Loading models...\nThis may take a moment on first run.")
    splash.setFont(QFont("", 14))
    splash.setAlignment(Qt.AlignmentFlag.AlignCenter)
    splash.setWindowFlags(Qt.WindowType.SplashScreen)
    splash.setFixedSize(400, 150)
    splash.setStyleSheet("""
        QLabel {
            background-color: #333;
            color: white;
            border-radius: 10px;
            padding: 20px;
        }
    """)
    splash.show()
    app.processEvents()
    return splash


def _cleanup():
    """Clean up resources on exit."""
    global _audio_capture, _app_window
    log.info("Cleaning up resources...")

    if _app_window:
        try:
            _app_window._stop_listening()
        except Exception:
            pass

    if _audio_capture:
        try:
            _audio_capture.cleanup()
            log.info("Audio capture cleaned up")
        except Exception:
            pass


def _signal_handler(signum, frame):
    """Handle interrupt signals gracefully."""
    log.info("Interrupt received, shutting down...")
    # Schedule app quit through the event loop for clean shutdown
    app = QApplication.instance()
    if app:
        # Use a timer to quit after current events are processed
        QTimer.singleShot(0, app.quit)


def main():
    """Main application entry point."""
    global _audio_capture, _app_window

    log.info("=" * 50)
    log.info("Live Audio Translator starting...")
    log.info("=" * 50)

    # Register cleanup for normal exit
    atexit.register(_cleanup)

    app = QApplication(sys.argv)
    app.setApplicationName("Live Audio Translator")

    # Handle Ctrl+C gracefully through the Qt event loop
    signal.signal(signal.SIGINT, _signal_handler)

    # Create a timer that periodically runs Python code to allow signal handling
    # (Qt's event loop blocks Python signal handlers otherwise)
    signal_timer = QTimer()
    signal_timer.timeout.connect(lambda: None)
    signal_timer.start(100)

    # Show loading screen
    splash = show_loading_message(app)

    try:
        # Import components
        log.info("Importing components...")
        from src.audio.capture import AudioCapture
        from src.transcription.whisper_stt import WhisperTranscriber
        from src.translation.argos_translator import ArgosTranslator
        from src.gui.main_window import MainWindow

        # Initialize audio capture
        log.info("Initializing audio capture...")
        splash.setText("Initializing audio capture...")
        app.processEvents()
        audio_capture = AudioCapture(
            min_chunk_duration=5.0,
            max_chunk_duration=15.0,
            silence_threshold=0.01,
            silence_duration=0.8,
        )
        _audio_capture = audio_capture  # Store global reference for cleanup
        devices = audio_capture.list_devices()
        log.info(f"Found {len(devices)} audio input device(s):")
        for d in devices:
            log.info(f"  - {d['name']}")

        # Load Whisper model
        log.info("Loading Whisper model (small)...")
        splash.setText("Loading Whisper model (small)...\nThis may take a minute on first run.")
        app.processEvents()
        transcriber = WhisperTranscriber(model_name='small')
        transcriber.load_model()
        log.info("Whisper model loaded successfully")

        # Load translation models
        log.info("Loading Argos translation models...")
        splash.setText("Loading translation models...")
        app.processEvents()
        translator = ArgosTranslator()
        translator.ensure_packages_installed()
        log.info("Translation models loaded successfully")

        # Create main window
        log.info("Creating main window...")
        splash.setText("Starting application...")
        app.processEvents()
        window = MainWindow()
        window.initialize_components(audio_capture, transcriber, translator)
        _app_window = window  # Store global reference for cleanup

        # Close splash and show main window
        splash.close()
        window.show()

        log.info("Application ready!")
        log.info("-" * 50)

        sys.exit(app.exec())

    except ImportError as e:
        log.error(f"Missing dependencies: {e}")
        splash.close()
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(
            None,
            "Missing Dependencies",
            f"Required packages are missing:\n\n{str(e)}\n\n"
            "Please run the install script first."
        )
        sys.exit(1)

    except Exception as e:
        log.error(f"Initialization error: {e}")
        splash.close()
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(
            None,
            "Initialization Error",
            f"Failed to start the application:\n\n{str(e)}"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
