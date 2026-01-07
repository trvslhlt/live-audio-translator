"""Whisper speech-to-text module."""

import numpy as np

try:
    import whisper
except ImportError:
    whisper = None


class WhisperTranscriber:
    """Transcribes audio to text using OpenAI Whisper."""

    SUPPORTED_LANGUAGES = {"en": "english", "fr": "french"}

    def __init__(self, model_name: str = "small"):
        """
        Initialize Whisper transcriber.

        Args:
            model_name: Whisper model to use ('tiny', 'base', 'small', 'medium', 'large').
        """
        if whisper is None:
            raise ImportError("whisper is required. Install with: pip install openai-whisper")

        self.model_name = model_name
        self._model = None

    def load_model(self):
        """Load the Whisper model. Call this before transcribing."""
        if self._model is None:
            self._model = whisper.load_model(self.model_name)

    def is_loaded(self) -> bool:
        """Check if the model is loaded."""
        return self._model is not None

    def transcribe(
        self, audio: np.ndarray, language: str | None = None, task: str = "transcribe"
    ) -> dict:
        """
        Transcribe or translate audio to text.

        Args:
            audio: Numpy array of audio samples (float32, normalized to [-1, 1]).
            language: Language code ('en', 'fr') or None for auto-detection.
            task: 'transcribe' for same-language transcription,
                  'translate' for direct translation to English.

        Returns:
            Dictionary with:
                - 'text': Transcribed/translated text
                - 'language': Detected or specified source language code
                - 'task': The task performed ('transcribe' or 'translate')
        """
        if not self.is_loaded():
            self.load_model()

        # Ensure audio is float32
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # Whisper transcription options
        options = {
            "fp16": False,  # Use FP32 for CPU compatibility
            "task": task,  # 'transcribe' or 'translate' (translate always outputs English)
        }

        if language:
            options["language"] = language

        result = self._model.transcribe(audio, **options)

        return {
            "text": result["text"].strip(),
            "language": result.get("language", language or "unknown"),
            "task": task,
            "segments": result.get("segments", []),
        }

    def detect_language(self, audio: np.ndarray) -> str:
        """
        Detect the language of the audio.

        Args:
            audio: Numpy array of audio samples.

        Returns:
            Language code (e.g., 'en', 'fr').
        """
        if not self.is_loaded():
            self.load_model()

        # Pad or trim audio to 30 seconds for language detection
        audio = whisper.pad_or_trim(audio)

        # Make log-Mel spectrogram
        mel = whisper.log_mel_spectrogram(audio).to(self._model.device)

        # Detect language
        _, probs = self._model.detect_language(mel)

        detected_lang = max(probs, key=probs.get)
        return detected_lang

    def unload_model(self):
        """Unload the model to free memory."""
        self._model = None
