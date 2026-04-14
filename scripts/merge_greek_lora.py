#!/usr/bin/env python3
"""
Merge GreekTTS-1.5 LoRA into Orpheus base model and convert to GGUF.

This is a ONE-TIME operation. After merging, the GGUF model runs fast
via llama-cpp-python without needing transformers/unsloth at inference.

Steps:
  1. Load Orpheus base model (unsloth/orpheus-3b-0.1-ft)
  2. Apply GreekTTS-1.5 LoRA adapter
  3. Merge weights
  4. Save merged model
  5. Convert to GGUF Q4_K_M

Requirements:
  pip install unsloth transformers peft

Output:
  ~/.daimonion/models/greektts-1.5-merged.gguf
"""

import os
import sys

MODELS_DIR = os.path.expanduser('~/.daimonion/models')
BASE_MODEL = 'unsloth/orpheus-3b-0.1-ft'
LORA_DIR = os.path.join(MODELS_DIR, 'greektts-1.5-lora', 'checkpoint-264000')
MERGED_DIR = os.path.join(MODELS_DIR, 'greektts-1.5-merged')
GGUF_OUTPUT = os.path.join(MODELS_DIR, 'greektts-1.5-merged.gguf')


def merge():
    """Merge LoRA into base model."""
    print('Step 1: Loading Orpheus base model...')

    try:
        from unsloth import FastLanguageModel
    except ImportError:
        print('ERROR: unsloth not installed. Run: pip install unsloth')
        sys.exit(1)

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=2048,
        dtype=None,
        load_in_4bit=True,  # 4-bit to fit in 8GB RAM
    )

    print(f'Step 2: Loading LoRA from {LORA_DIR}...')
    if not os.path.exists(LORA_DIR):
        print(f'ERROR: LoRA not found at {LORA_DIR}')
        print('Run the model download first.')
        sys.exit(1)

    model.load_adapter(LORA_DIR)

    print('Step 3: Merging weights...')
    model = model.merge_and_unload()

    print(f'Step 4: Saving merged model to {MERGED_DIR}...')
    os.makedirs(MERGED_DIR, exist_ok=True)
    model.save_pretrained(MERGED_DIR)
    tokenizer.save_pretrained(MERGED_DIR)

    print(f'Step 5: Converting to GGUF...')
    print('NOTE: GGUF conversion requires llama.cpp\'s convert script.')
    print(f'  Manual step:')
    print(f'    python llama.cpp/convert_hf_to_gguf.py {MERGED_DIR} --outfile {GGUF_OUTPUT} --outtype q4_k_m')
    print()
    print(f'Or use the pre-built Orpheus GGUF and apply LoRA at runtime (if supported).')

    print('\nMerge complete.')
    print(f'Merged model: {MERGED_DIR}')


def check_status():
    """Check what's available."""
    print('=== Model Status ===')
    print(f'Base GGUF: {"EXISTS" if os.path.exists(os.path.join(MODELS_DIR, "orpheus-3b-0.1-ft-Q4_K_M.gguf")) else "MISSING"}')
    print(f'LoRA dir:  {"EXISTS" if os.path.exists(LORA_DIR) else "MISSING"}')
    print(f'Merged:    {"EXISTS" if os.path.exists(MERGED_DIR) else "NOT YET"}')
    print(f'GGUF:      {"EXISTS" if os.path.exists(GGUF_OUTPUT) else "NOT YET"}')

    if os.path.exists(LORA_DIR):
        files = os.listdir(LORA_DIR)
        safetensors = [f for f in files if f.endswith('.safetensors')]
        print(f'\nLoRA files: {len(files)} total, {len(safetensors)} safetensors')
        for f in sorted(files):
            size = os.path.getsize(os.path.join(LORA_DIR, f))
            print(f'  {f}: {size / 1e6:.1f} MB')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'status':
        check_status()
    else:
        merge()
