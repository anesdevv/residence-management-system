# Assets

How to find keys without exposing them, pick today's best model, art-direct what it makes, and ship it light.

## Find the keys (names only)

Look in this project's env files. This prints the file and the variable *name*, never the value:

```bash
grep -oE '^(export )?[A-Z0-9_]*(FAL|GEMINI|GOOGLE_AI|GOOGLE_GENAI|GOOGLE_API|ELEVEN|OPENAI|REPLICATE|RUNWAY|LUMA|STABILITY|IDEOGRAM|RECRAFT|BFL|KLING|MINIMAX)[A-Z0-9_]*=' \
  .env* 2>/dev/null | grep -v '\.example:' | sort -u
```

To use a key, load it into the environment of the command that needs it, without printing it.

## Pick the model

Model lineups change every few weeks, so never pick one from memory.

1. Check today's date.
2. Check what each provider offers right now, in its model list or docs. If that doesn't settle it, search the web for the best model for this asset type as of this month.
3. Use the best model for the job (quality first, not price), and record the model and the date in the design log.

## Art-direct it

- Brief every generation from the system: palette, light, lens, materials, mood, composition, and the space the layout needs (where text will sit).
- Generate several variations, compare them side by side, and keep only what meets the bar.
- Reject the AI tells: garbled text, wrong hands, plastic skin, impossible light, stock-photo staging, the same face everywhere.
- Keep a series consistent: the same light, grade and style across every image. Reuse seeds or reference images when the model supports them.
- Edit, inpaint and upscale the keepers instead of settling for a near miss.
- Time sound to the motion you measured. Keep it subtle and optional, and respect mute.

## Ship it light

- **Images:** AVIF or WebP with a fallback, `srcset` and `sizes` for each breakpoint, explicit width and height so nothing shifts, lazy loading below the fold, and a preloaded hero.
- **Video:** H.264 (plus HEVC or AV1 where they help) with a poster frame. Autoplay only when it's muted decoration, and never play sound without a tap.
- **Native:** asset catalogs at @2x and @3x, and vectors where they hold up.

## Keep it honest

Don't present generated people as real customers, staff or reviewers, and don't use a real person's likeness without permission.
