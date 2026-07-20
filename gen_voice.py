#!/usr/bin/env python3
"""
Hero's Proof · Speaking Quest voice batch generator (ElevenLabs)
================================================================
Reads sq_voice_manifest.csv and generates every missing mp3 into ./voice/,
using the exact filenames Speaking Quest already looks for. Safe to re-run:
existing files are skipped, so you can stop anytime and resume later
(useful for spreading generation across billing months).

Setup (one time):
    pip install requests
    export ELEVEN_API_KEY="sk_..."          # from elevenlabs.io → Profile → API Keys
    export ELEVEN_VOICE_ID="..."            # the voice you choose for the practice voice

Run:
    python3 gen_sq_voice.py                 # generate everything missing
    python3 gen_sq_voice.py --only spell    # spells only (164 files)
    python3 gen_sq_voice.py --only word     # words only  (410 files)
    python3 gen_sq_voice.py --dry-run       # show what would be generated + char cost

Then copy the resulting voice/ folder into the speaking-quest repo root and push.
The app needs zero code changes — it already tries each file before TTS fallback.
"""
import csv, os, sys, time, pathlib

import requests

API_KEY  = os.environ.get("ELEVEN_API_KEY", "")
VOICE_ID = os.environ.get("ELEVEN_VOICE_ID", "")
MODEL    = os.environ.get("ELEVEN_MODEL", "eleven_turbo_v2_5")  # 0.5 credits/char; use eleven_multilingual_v2 for max quality (1/char)
FMT      = "mp3_44100_64"   # small files, plenty for single words/sentences on phone speakers
MANIFEST = os.environ.get("VOICE_MANIFEST", "sq_voice_manifest.csv")  # point at any manifest (e.g. intro_voice_manifest.csv)

VOICE_SETTINGS = {          # tuned for a clear, friendly teaching voice
    "stability": 0.55,       # consistent across 574 short clips
    "similarity_boost": 0.75,
    "style": 0.20,           # a little liveliness, not theatrical
    "use_speaker_boost": True,
}

def main():
    dry  = "--dry-run" in sys.argv
    only = sys.argv[sys.argv.index("--only")+1] if "--only" in sys.argv else None
    rows = list(csv.DictReader(open(MANIFEST, encoding="utf-8")))
    if only: rows = [r for r in rows if r["type"] == only]
    todo = [r for r in rows if not pathlib.Path(r["filename"]).exists()]
    chars = sum(len(r["text"]) for r in todo)
    mult  = 0.5 if "turbo" in MODEL or "flash" in MODEL else 1.0
    print(f"{len(rows)} in scope · {len(todo)} missing · {chars} chars ≈ {int(chars*mult)} credits ({MODEL})")
    if dry:
        for r in todo[:15]: print("  would generate:", r["filename"], "←", r["text"])
        if len(todo) > 15: print(f"  … and {len(todo)-15} more")
        return
    if not API_KEY or not VOICE_ID:
        sys.exit("Set ELEVEN_API_KEY and ELEVEN_VOICE_ID environment variables first.")
    # create whatever folder each file needs (voice/, assets/intro/voice/en/, ...)
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}?output_format={FMT}"
    for i, r in enumerate(todo, 1):
        for attempt in range(4):
            resp = requests.post(url,
                headers={"xi-api-key": API_KEY, "Content-Type": "application/json"},
                json={"text": r["text"], "model_id": MODEL, "voice_settings": VOICE_SETTINGS},
                timeout=60)
            if resp.status_code == 200:
                p = pathlib.Path(r["filename"]); p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(resp.content)
                print(f"[{i}/{len(todo)}] ✅ {r['filename']}")
                break
            if resp.status_code == 429:            # rate limited → back off and retry
                wait = 5 * (attempt + 1)
                print(f"[{i}/{len(todo)}] ⏳ rate limited, waiting {wait}s…")
                time.sleep(wait)
            else:
                print(f"[{i}/{len(todo)}] ❌ {resp.status_code} {resp.text[:200]} — skipping {r['filename']}")
                break
        time.sleep(0.35)                            # be gentle; ~3 req/s keeps free of 429s
    print("Done. Re-run to retry any ❌ skips (existing files are never re-billed).")

if __name__ == "__main__":
    main()
