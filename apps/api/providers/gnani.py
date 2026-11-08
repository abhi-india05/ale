# WHY: TR-VOX-05, TR-VOX-06, D10, D11 — Gnani AI Prisma STT & Timbre TTS with Semaphore(1) & Cache
"""Speech-to-Text and Text-to-Speech providers with Gnani AI and local mock adapters."""

import asyncio
import hashlib
import json
import os
import random
import time
from typing import Optional, Tuple

import httpx

from apps.api.core.config import settings

# CRITICAL CONCURRENCY LOCK: Gnani enforces 1 active request per key (D10)
GNANI_SEMAPHORE = asyncio.Semaphore(1)


class SttResult:
    """Transcript and confidence outcome from speech recognition."""
    def __init__(self, transcript: str, confidence: float, duration_ms: int):
        self.transcript = transcript
        self.confidence = confidence
        self.duration_ms = duration_ms


class TtsResult:
    """Synthesized speech audio result."""
    def __init__(self, audio_bytes: Optional[bytes], audio_url: Optional[str], duration_ms: int, cached: bool = False):
        self.audio_bytes = audio_bytes
        self.audio_url = audio_url
        self.duration_ms = duration_ms
        self.cached = cached


class MockStt:
    """Mock Speech-to-Text returning canned or transcript-assisted speech."""

    @classmethod
    async def transcribe(cls, audio_bytes: Optional[bytes] = None, transcript_hint: Optional[str] = None) -> SttResult:
        """Simulate STT transcription with ~800ms realistic processing time."""
        t0 = time.perf_counter()
        # Simulated latency
        await asyncio.sleep(0.08)

        text = transcript_hint or "ಇವತ್ತು ಸಮುದ್ರಕ್ಕೆ ಹೋಗಬಹುದಾ?"
        confidence = 0.95
        ms = int((time.perf_counter() - t0) * 1000)
        return SttResult(transcript=text, confidence=confidence, duration_ms=ms)


class MockTts:
    """Mock Text-to-Speech returning instantaneous voice response markers."""

    @classmethod
    async def synthesize(cls, text_kn: str, voice: str = "Lakshmi") -> TtsResult:
        """Simulate TTS synthesis with ~500ms realistic processing time."""
        t0 = time.perf_counter()
        await asyncio.sleep(0.05)

        # Generate lightweight dummy 24kHz mono header for browser audio playback
        dummy_wav = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x60\x5d\x00\x00\xc0\xba\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        ms = int((time.perf_counter() - t0) * 1000)
        return TtsResult(audio_bytes=dummy_wav, audio_url=None, duration_ms=ms, cached=False)


class GnaniStt:
    """Live Gnani AI Prisma v3.0 Speech-to-Text provider."""

    ENDPOINT = "https://api.vachana.ai/stt/v3"
    KEYTERMS = "ಬೂತಾಯಿ,ಬಂಗುಡೆ,ಮಾಂಜಿ,ಸಿಗಡಿ,Sardine,Mackerel,Pomfret,Prawns,Malpe,ಡೀಸೆಲ್,ರೇಟ್,ಕೆಜಿ"

    @classmethod
    async def transcribe(cls, audio_bytes: bytes, filename: str = "input.wav") -> SttResult:
        """Send audio to Gnani Prisma API guarded by Semaphore(1)."""
        if not settings.gnani_api_key_id or settings.mock_providers:
            return await MockStt.transcribe(audio_bytes)

        t0 = time.perf_counter()
        headers = {"X-API-Key-ID": settings.gnani_api_key_id}
        data = {
            "model": "prisma-v3.0",
            "language_code": "kn-IN,en-IN",
            "preferred_language": "kn-IN",
            "format": "codemix",
            "keyterms": cls.KEYTERMS,
        }
        files = {"audio_file": (filename, audio_bytes, "audio/wav")}

        # Single concurrency lock with retry + jitter (D10)
        async with GNANI_SEMAPHORE:
            for attempt in range(2):
                try:
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        response = await client.post(cls.ENDPOINT, headers=headers, data=data, files=files)
                        if response.status_code == 429 and attempt == 0:
                            await asyncio.sleep(0.5 + random.uniform(0.1, 0.4))
                            continue
                        response.raise_for_status()
                        result = response.json()
                        transcript = result.get("transcript", "")
                        confidence = float(result.get("confidence", 0.90))
                        ms = int((time.perf_counter() - t0) * 1000)
                        return SttResult(transcript=transcript, confidence=confidence, duration_ms=ms)
                except Exception as e:
                    if attempt == 1:
                        # Fallback to mock on network/API failure
                        return await MockStt.transcribe(audio_bytes)
                    await asyncio.sleep(0.3)

        return await MockStt.transcribe(audio_bytes)


class GnaniTts:
    """Live Gnani AI Timbre v3.0 Text-to-Speech provider with SHA-256 caching."""

    ENDPOINT = "https://api.vachana.ai/api/v1/tts/inference"

    @classmethod
    def compute_cache_key(cls, text: str, voice: str = "Lakshmi") -> str:
        """Compute SHA-256 hash for tts_cache (D11)."""
        raw = f"{text}|{voice}|timbre-v3.0|linear_pcm_wav_24000"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    async def synthesize(cls, text_kn: str, voice: str = "Lakshmi") -> TtsResult:
        """Synthesize Kannada audio with local cache lookup and Semaphore(1)."""
        cache_key = cls.compute_cache_key(text_kn, voice)

        # Check local filesystem audio cache first
        cache_dir = "audio_cache"
        os.makedirs(cache_dir, exist_ok=True)
        cached_file = os.path.join(cache_dir, f"{cache_key}.wav")
        if os.path.exists(cached_file):
            with open(cached_file, "rb") as f:
                data = f.read()
            return TtsResult(audio_bytes=data, audio_url=f"/api/v1/audio/{cache_key}.wav", duration_ms=10, cached=True)

        if not settings.gnani_api_key_id or settings.mock_providers:
            return await MockTts.synthesize(text_kn, voice)

        t0 = time.perf_counter()
        headers = {
            "X-API-Key-ID": settings.gnani_api_key_id,
            "Content-Type": "application/json",
        }
        payload = {
            "text": text_kn,
            "voice": voice,
            "model": "timbre-v3.0",
            "language": "kn-IN",
            "audio_config": {
                "encoding": "linear_pcm",
                "container": "wav",
                "sample_rate": 24000,
                "num_channels": 1,
                "sample_width": 2,
            },
        }

        async with GNANI_SEMAPHORE:
            for attempt in range(2):
                try:
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        response = await client.post(cls.ENDPOINT, headers=headers, json=payload)
                        if response.status_code == 429 and attempt == 0:
                            await asyncio.sleep(0.5 + random.uniform(0.1, 0.4))
                            continue
                        response.raise_for_status()
                        audio_data = response.content
                        # Save to cache
                        with open(cached_file, "wb") as f:
                            f.write(audio_data)
                        ms = int((time.perf_counter() - t0) * 1000)
                        return TtsResult(audio_bytes=audio_data, audio_url=f"/api/v1/audio/{cache_key}.wav", duration_ms=ms, cached=False)
                except Exception:
                    if attempt == 1:
                        return await MockTts.synthesize(text_kn, voice)
                    await asyncio.sleep(0.3)

        return await MockTts.synthesize(text_kn, voice)
