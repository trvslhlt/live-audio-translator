.PHONY: install dev run clean clean-models clean-all test lint format help

# Default target
help:
	@echo "Live Audio Translator - Development Commands"
	@echo ""
	@echo "  make install      - Install dependencies (first time setup)"
	@echo "  make dev          - Install with dev dependencies (ruff)"
	@echo "  make run          - Run the application"
	@echo "  make clean        - Remove Python cache files"
	@echo "  make clean-models - Remove downloaded AI models"
	@echo "  make clean-all    - Full clean (venv, cache, models)"
	@echo "  make test         - Run component tests"
	@echo "  make lint         - Check code style (ruff)"
	@echo "  make format       - Auto-format code (ruff)"
	@echo ""

# Install dependencies
install:
	./install.sh

# Install with dev dependencies
dev: install
	uv pip install -e ".[dev]"

# Run the application
run:
	.venv/bin/python -m src.main

# Run component tests
test:
	.venv/bin/python -c "\
from src.audio.capture import AudioCapture; \
from src.transcription.whisper_stt import WhisperTranscriber; \
from src.translation.argos_translator import ArgosTranslator; \
print('✓ All imports successful'); \
ac = AudioCapture(); \
devices = ac.list_devices(); \
print(f'✓ Found {len(devices)} audio device(s)'); \
ac.cleanup(); \
"

# Clean Python cache files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Cleaned Python cache files"

# Clean downloaded AI models (will re-download on next run)
clean-models:
	rm -rf ~/.cache/whisper
	rm -rf ~/.local/share/argos-translate
	@echo "✓ Cleaned AI models (will re-download on next run)"

# Full clean - removes everything including venv
clean-all: clean clean-models
	rm -rf .venv
	@echo "✓ Full clean complete. Run 'make install' to set up again."

# Lint code
lint:
	.venv/bin/ruff check src/

# Format code
format:
	.venv/bin/ruff format src/
	.venv/bin/ruff check --fix src/
