"""
Greek TTS — GreekTTS-1.5 (Moira Labs) via Orpheus 3B + SNAC vocoder.

Runs locally on Apple Silicon (MPS) or CPU via llama-cpp-python.
No CUDA required. No API costs.

Architecture:
  Text → Orpheus 3B (GGUF, quantized) → audio tokens → SNAC vocoder → WAV

Models:
  - Base: orpheus-3b-0.1-ft (GGUF Q4_K_M, ~2.3 GB)
  - Greek LoRA: moiralabs/GreekTTS-1.5
  - Vocoder: hubertsiuzdak/snac_24khz

Usage:
    tts = GreekTTS()
    wav_bytes = tts.synthesize("Καλημέρα, πώς είσαι;")
"""

from __future__ import annotations

import io
import logging
import os
import struct
import time
from pathlib import Path

logger = logging.getLogger('daimonion.greek_tts')

SAMPLE_RATE = 24000
MODELS_DIR = os.path.expanduser('~/.daimonion/models')

# Orpheus special tokens
START_TOKEN_ID = 128259
END_TOKEN_IDS = {128009, 128260, 128261, 128257}
CUSTOM_TOKEN_PREFIX = '<custom_token_'

# SNAC processes 7 tokens per audio frame
TOKENS_PER_FRAME = 7
# Buffer 4 frames before first decode
INITIAL_BUFFER = TOKENS_PER_FRAME * 4  # 28 tokens

# Optional heavy dependencies
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    np = None
    HAS_NUMPY = False

try:
    import torch
    HAS_TORCH = True
except ImportError:
    torch = None
    HAS_TORCH = False

try:
    from snac import SNAC
    HAS_SNAC = True
except ImportError:
    SNAC = None
    HAS_SNAC = False

try:
    from llama_cpp import Llama
    HAS_LLAMA_CPP = True
except ImportError:
    Llama = None
    HAS_LLAMA_CPP = False


def _get_device() -> str:
    """Select best available device for SNAC vocoder."""
    if not HAS_TORCH:
        return 'cpu'
    if torch.backends.mps.is_available():
        return 'mps'
    if torch.cuda.is_available():
        return 'cuda'
    return 'cpu'


def _turn_token_into_id(token_str: str, index: int) -> int | None:
    """Convert a custom token string to a SNAC codebook index.

    Token format: <custom_token_N> where N is an integer.
    The index within the 7-token frame determines the offset.
    """
    if not token_str.startswith(CUSTOM_TOKEN_PREFIX):
        return None
    try:
        num = int(token_str[len(CUSTOM_TOKEN_PREFIX):-1])  # strip < > and prefix
        code_id = num - 10 - ((index % TOKENS_PER_FRAME) * 4096)
        if 0 <= code_id < 4096:
            return code_id
        return None
    except (ValueError, IndexError):
        return None


def _redistribute_codes(buffer: list[int]) -> tuple[list[int], list[int], list[int]]:
    """Organize flat buffer into SNAC's 3 codebook levels.

    Each 7-token frame maps to:
      codes_0: 1 token  (index 0)
      codes_1: 2 tokens (indices 1, 4)
      codes_2: 4 tokens (indices 2, 3, 5, 6)
    """
    codes_0, codes_1, codes_2 = [], [], []
    for i in range(0, len(buffer), TOKENS_PER_FRAME):
        if i + TOKENS_PER_FRAME > len(buffer):
            break
        frame = buffer[i:i + TOKENS_PER_FRAME]
        codes_0.append(frame[0])
        codes_1.extend([frame[1], frame[4]])
        codes_2.extend([frame[2], frame[3], frame[5], frame[6]])
    return codes_0, codes_1, codes_2


class GreekTTS:
    """Greek text-to-speech via GreekTTS-1.5 (Orpheus 3B + SNAC).

    Lazy-loads models on first use. If dependencies are missing,
    returns empty bytes gracefully.
    """

    def __init__(
        self,
        gguf_path: str | None = None,
        lora_path: str | None = None,
        sample_rate: int = SAMPLE_RATE,
        n_ctx: int = 2048,
        temperature: float = 0.6,
        top_p: float = 0.95,
        repetition_penalty: float = 1.1,
    ):
        self.sample_rate = sample_rate
        self.n_ctx = n_ctx
        self.temperature = temperature
        self.top_p = top_p
        self.repetition_penalty = repetition_penalty

        self._gguf_path = gguf_path
        self._lora_path = lora_path
        self._llm = None
        self._snac = None
        self._device = _get_device()

        self._available = HAS_NUMPY and HAS_TORCH and HAS_SNAC and HAS_LLAMA_CPP

    @property
    def available(self) -> bool:
        return self._available

    @property
    def models_downloaded(self) -> bool:
        """Check if GGUF model exists on disk."""
        path = self._gguf_path or self._default_gguf_path()
        return os.path.exists(path)

    def _default_gguf_path(self) -> str:
        return os.path.join(MODELS_DIR, 'orpheus-3b-0.1-ft-Q4_K_M.gguf')

    def _load_llm(self):
        """Load the Orpheus GGUF model via llama-cpp-python."""
        if self._llm is not None:
            return self._llm

        gguf_path = self._gguf_path or self._default_gguf_path()
        if not os.path.exists(gguf_path):
            logger.error('GGUF model not found at %s — run download_models() first', gguf_path)
            return None

        logger.info('Loading Orpheus GGUF model from %s...', gguf_path)
        t = time.time()

        kwargs = {
            'model_path': gguf_path,
            'n_ctx': self.n_ctx,
            'n_threads': 4,
            'verbose': False,
        }

        # Apply LoRA adapter if available
        if self._lora_path and os.path.exists(self._lora_path):
            kwargs['lora_path'] = self._lora_path
            logger.info('Applying GreekTTS LoRA from %s', self._lora_path)

        self._llm = Llama(**kwargs)
        logger.info('Orpheus loaded in %.1fs', time.time() - t)
        return self._llm

    def _load_snac(self):
        """Load the SNAC vocoder."""
        if self._snac is not None:
            return self._snac

        logger.info('Loading SNAC vocoder on %s...', self._device)
        t = time.time()
        self._snac = SNAC.from_pretrained('hubertsiuzdak/snac_24khz')
        if self._device != 'cpu':
            self._snac = self._snac.to(self._device)
        self._snac.eval()
        logger.info('SNAC loaded in %.1fs', time.time() - t)
        return self._snac

    def _format_prompt(self, text: str, voice: str | None = None) -> str:
        """Format text for Orpheus model input.

        For GreekTTS-1.5 (single-speaker), voice can be None.
        For base Orpheus, use voice name prefix.
        """
        if voice:
            return f'{voice}: {text}'
        return text

    def _generate_tokens(self, text: str, voice: str | None = None) -> list[str]:
        """Generate audio token strings from the Orpheus model."""
        llm = self._load_llm()
        if llm is None:
            return []

        prompt = self._format_prompt(text, voice)

        output = llm(
            prompt,
            max_tokens=1200,
            temperature=self.temperature,
            top_p=self.top_p,
            repeat_penalty=self.repetition_penalty,
            stop=['<|eot_id|>'],
        )

        # Extract generated text and split into tokens
        generated = output.get('choices', [{}])[0].get('text', '')
        tokens = []
        for part in generated.split('>'):
            part = part.strip()
            if part.startswith('<custom_token_'):
                tokens.append(part + '>')
        return tokens

    def _tokens_to_audio(self, token_strings: list[str]) -> bytes:
        """Convert audio token strings to WAV bytes via SNAC."""
        snac = self._load_snac()
        if snac is None:
            return b''

        # Convert token strings to code IDs
        code_ids = []
        for i, tok in enumerate(token_strings):
            cid = _turn_token_into_id(tok, i)
            if cid is not None:
                code_ids.append(cid)

        if len(code_ids) < INITIAL_BUFFER:
            logger.warning('Too few audio tokens: %d (need >= %d)', len(code_ids), INITIAL_BUFFER)
            return b''

        # Redistribute into SNAC codebook levels
        codes_0, codes_1, codes_2 = _redistribute_codes(code_ids)

        if not codes_0:
            return b''

        # Decode via SNAC
        with torch.no_grad():
            c0 = torch.tensor([codes_0], dtype=torch.long, device=self._device)
            c1 = torch.tensor([codes_1], dtype=torch.long, device=self._device)
            c2 = torch.tensor([codes_2], dtype=torch.long, device=self._device)
            audio = snac.decode([c0, c1, c2])

        # Convert to int16 PCM
        audio_np = audio.squeeze().cpu().numpy()
        audio_int16 = (audio_np * 32767).clip(-32768, 32767).astype(np.int16)

        # Write WAV
        buf = io.BytesIO()
        _write_wav(buf, audio_int16, self.sample_rate)
        return buf.getvalue()

    def synthesize(self, text: str, voice: str | None = None) -> bytes:
        """Synthesize Greek text to WAV audio bytes.

        Args:
            text: Greek text to synthesize.
            voice: Voice name (None for GreekTTS-1.5 default).

        Returns:
            WAV audio bytes. Empty bytes if unavailable or failed.
        """
        if not self._available:
            logger.debug('Greek TTS dependencies not available')
            return b''

        if not self.models_downloaded:
            logger.error('Models not downloaded — call download_models() first')
            return b''

        t = time.time()
        try:
            tokens = self._generate_tokens(text, voice)
            if not tokens:
                logger.warning('No audio tokens generated for: %s', text[:50])
                return b''

            wav_bytes = self._tokens_to_audio(tokens)
            elapsed = time.time() - t
            logger.info('Greek TTS: %d chars → %d tokens → %d bytes in %.1fs',
                        len(text), len(tokens), len(wav_bytes), elapsed)
            return wav_bytes

        except Exception as e:
            logger.error('Greek TTS synthesis failed: %s', e, exc_info=True)
            return b''


def _write_wav(buf: io.BytesIO, audio: 'np.ndarray', sample_rate: int):
    """Write a minimal WAV file to a BytesIO buffer."""
    n_samples = len(audio)
    data_size = n_samples * 2  # int16 = 2 bytes per sample

    # WAV header
    buf.write(b'RIFF')
    buf.write(struct.pack('<I', 36 + data_size))
    buf.write(b'WAVE')
    buf.write(b'fmt ')
    buf.write(struct.pack('<I', 16))       # chunk size
    buf.write(struct.pack('<H', 1))        # PCM format
    buf.write(struct.pack('<H', 1))        # mono
    buf.write(struct.pack('<I', sample_rate))
    buf.write(struct.pack('<I', sample_rate * 2))  # byte rate
    buf.write(struct.pack('<H', 2))        # block align
    buf.write(struct.pack('<H', 16))       # bits per sample
    buf.write(b'data')
    buf.write(struct.pack('<I', data_size))
    buf.write(audio.tobytes())


def download_models():
    """Download Orpheus GGUF + GreekTTS-1.5 LoRA + SNAC to ~/.daimonion/models/.

    Call this once before first use.
    """
    os.makedirs(MODELS_DIR, exist_ok=True)

    gguf_path = os.path.join(MODELS_DIR, 'orpheus-3b-0.1-ft-Q4_K_M.gguf')
    lora_dir = os.path.join(MODELS_DIR, 'greektts-1.5-lora')

    print('Downloading Orpheus 3B GGUF (Q4_K_M, ~2.3 GB)...')
    if not os.path.exists(gguf_path):
        try:
            from huggingface_hub import hf_hub_download
            hf_hub_download(
                repo_id='isaiahbjork/orpheus-3b-0.1-ft-Q4_K_M-GGUF',
                filename='orpheus-3b-0.1-ft-q4_k_m.gguf',
                local_dir=MODELS_DIR,
                local_dir_use_symlinks=False,
            )
            # Normalize filename
            downloaded = os.path.join(MODELS_DIR, 'orpheus-3b-0.1-ft-q4_k_m.gguf')
            if os.path.exists(downloaded) and not os.path.exists(gguf_path):
                os.rename(downloaded, gguf_path)
            print(f'  Saved: {gguf_path}')
        except Exception as e:
            print(f'  Download failed: {e}')
            print(f'  Manual: download from HuggingFace and place at {gguf_path}')
    else:
        print(f'  Already exists: {gguf_path}')

    print('Downloading GreekTTS-1.5 LoRA adapters...')
    if not os.path.exists(lora_dir):
        try:
            from huggingface_hub import snapshot_download
            snapshot_download(
                repo_id='moiralabs/GreekTTS-1.5',
                local_dir=lora_dir,
                local_dir_use_symlinks=False,
            )
            print(f'  Saved: {lora_dir}')
        except Exception as e:
            print(f'  Download failed: {e}')
            print(f'  Manual: git clone https://huggingface.co/moiralabs/GreekTTS-1.5 {lora_dir}')
    else:
        print(f'  Already exists: {lora_dir}')

    print('SNAC vocoder will be auto-downloaded on first use via PyTorch Hub.')
    print('Done.')
