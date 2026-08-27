# book-audify

**English** | [日本語](README.ja.md) | [繁體中文](README.zh-TW.md)

> Turn an owned e-book into a personal audiobook — `.m4b` with chapter
> bookmarks, synthesized with free Microsoft neural voices (edge-tts).

Takes `book-extract`'s per-chapter Markdown and runs:
clean → **validated hard gate** → per-chapter TTS → ffmpeg m4b merge.

- Cleaning strips everything a TTS engine would mispronounce (markup,
  footnote anchors, translator notes, decorative chapter frames) and skips
  front/back matter; `validate_tts.py` refuses to synthesize a dirty folder.
- Voice/rate are user choices — the skill A/B samples a short chapter
  instead of arguing taste. Sped-up listeners (1.5x) get a slower base rate
  so prosody survives.
- Foreign-language books: full-text translate-for-listening (per-book
  glossary, no English parentheticals) with a one-chapter listen gate before
  committing to the whole book.

Requires `pip install edge-tts` and `ffmpeg`. Personal use of books you own;
do not distribute the audio.
