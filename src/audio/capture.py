"""Audio capture module for microphone input with voice activity detection."""

import queue
import threading

import numpy as np

try:
    import pyaudio
except ImportError:
    pyaudio = None


class AudioCapture:
    """Captures audio from microphone with smart chunking based on speech pauses."""

    # Audio settings optimized for Whisper
    SAMPLE_RATE = 16000  # Whisper expects 16kHz
    CHANNELS = 1  # Mono
    CHUNK_SIZE = 1024  # Samples per buffer (~64ms at 16kHz)
    FORMAT = pyaudio.paInt16 if pyaudio else None

    def __init__(
        self,
        min_chunk_duration: float = 5.0,
        max_chunk_duration: float = 15.0,
        silence_threshold: float = 0.01,
        silence_duration: float = 0.8,
    ):
        """
        Initialize audio capture with voice activity detection.

        Args:
            min_chunk_duration: Minimum seconds before considering a chunk ready.
            max_chunk_duration: Maximum seconds before forcing a chunk (even mid-speech).
            silence_threshold: RMS threshold below which audio is considered silence (0-1).
            silence_duration: Seconds of silence needed to trigger chunk emission.
        """
        if pyaudio is None:
            raise ImportError("pyaudio is required. Install with: pip install pyaudio")

        self.min_chunk_duration = min_chunk_duration
        self.max_chunk_duration = max_chunk_duration
        self.silence_threshold = silence_threshold
        self.silence_duration = silence_duration

        self.min_samples = int(self.SAMPLE_RATE * min_chunk_duration)
        self.max_samples = int(self.SAMPLE_RATE * max_chunk_duration)
        self.silence_samples = int(self.SAMPLE_RATE * silence_duration)

        self._audio = pyaudio.PyAudio()
        self._stream = None
        self._buffer = []
        self._buffer_lock = threading.Lock()
        self._running = False
        self._capture_thread = None
        self._audio_queue = queue.Queue()
        self._silence_counter = 0
        self._has_speech = False

    def list_devices(self) -> list[dict]:
        """List available audio input devices."""
        devices = []
        for i in range(self._audio.get_device_count()):
            info = self._audio.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                devices.append(
                    {
                        "index": i,
                        "name": info["name"],
                        "channels": info["maxInputChannels"],
                        "sample_rate": int(info["defaultSampleRate"]),
                    }
                )
        return devices

    def get_default_device(self) -> int | None:
        """Get the default input device index."""
        try:
            info = self._audio.get_default_input_device_info()
            return info["index"]
        except OSError:
            return None

    def start(self, device_index: int | None = None):
        """
        Start capturing audio.

        Args:
            device_index: Specific device to use, or None for default.
        """
        if self._running:
            return

        self._running = True
        self._buffer = []

        # Clear any old items in the queue
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

        self._stream = self._audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.SAMPLE_RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=self.CHUNK_SIZE,
            stream_callback=self._audio_callback,
        )

        self._stream.start_stream()

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback for receiving audio data with voice activity detection."""
        if not self._running:
            return (None, pyaudio.paComplete)

        # Convert bytes to numpy array
        audio_data = np.frombuffer(in_data, dtype=np.int16)

        # Calculate RMS (root mean square) for this chunk to detect speech
        audio_float = audio_data.astype(np.float32) / 32768.0
        rms = np.sqrt(np.mean(audio_float**2))
        is_silence = rms < self.silence_threshold

        with self._buffer_lock:
            self._buffer.extend(audio_data)
            buffer_len = len(self._buffer)

            # Track if we've detected speech in this buffer
            if not is_silence:
                self._has_speech = True
                self._silence_counter = 0
            else:
                self._silence_counter += len(audio_data)

            # Determine if we should emit a chunk
            should_emit = False

            # Case 1: Max duration reached - force emit to avoid too much latency
            if buffer_len >= self.max_samples:
                should_emit = True

            # Case 2: We have minimum audio AND detected a speech pause
            elif buffer_len >= self.min_samples and self._has_speech:
                if self._silence_counter >= self.silence_samples:
                    should_emit = True

            if should_emit:
                chunk = np.array(self._buffer, dtype=np.float32)
                # Normalize to [-1, 1] for Whisper
                chunk = chunk / 32768.0
                self._audio_queue.put(chunk)
                # Reset buffer and state
                self._buffer = []
                self._silence_counter = 0
                self._has_speech = False

        return (None, pyaudio.paContinue)

    def get_chunk(self, timeout: float = 0.1) -> np.ndarray | None:
        """
        Get the next audio chunk if available.

        Args:
            timeout: How long to wait for a chunk in seconds.

        Returns:
            Numpy array of audio samples normalized to [-1, 1], or None if no chunk ready.
        """
        try:
            return self._audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def stop(self):
        """Stop capturing audio."""
        self._running = False

        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
            self._stream = None

        with self._buffer_lock:
            self._buffer = []
            self._silence_counter = 0
            self._has_speech = False

    def is_running(self) -> bool:
        """Check if capture is currently running."""
        return self._running

    def cleanup(self):
        """Clean up audio resources."""
        self.stop()
        if self._audio:
            self._audio.terminate()
            self._audio = None
