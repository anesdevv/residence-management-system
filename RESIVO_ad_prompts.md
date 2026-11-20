# RÉSIVO — 20s Ad · Shot-by-Shot Prompt Package

**Spec:** 20 s · 24 fps · 1080p · master 16:9 + 9:16 cutdown · model generates no audio.
**Rule for every prompt:** append the GLOBAL NEGATIVE string. Never ask for readable text; all text, UI, logo and captions are added in post.

---

## 0. Character blocks — paste verbatim for consistency

> **STUDENT** — young Algerian woman, 21, dark wavy hair under a light beige headscarf, navy knit cardigan over a white top, small gold stud earrings, dark jeans, canvas backpack.

> **DIRECTOR** — Algerian man in his fifties, short gray beard, thin metal glasses, light-blue button-up shirt with rolled sleeves, dark trousers, calm confident bearing.

> **TECHNICIAN** — Algerian man in his thirties, short black hair, light stubble, teal work vest over a gray t-shirt, dark work trousers, black toolbox.

> **STAFF** — Algerian woman in her thirties, dark hair in a low bun, white blouse, thin gold necklace, plain lanyard without any text.

**GLOBAL NEGATIVE (append to all shots):**
`readable text, signs, signage, logos, watermarks, captions, subtitles, gibberish lettering, real brand marks, university crest, distorted hands, extra fingers, deformed faces, warped anatomy, flicker, morphing, frame-to-frame instability, stereotypes, caricature, violence, branded cars, mixed-gender intimacy, oversaturated HDR, cgi look`

---

## SHOT 1 — HOOK / pain · 0.0–3.0 s · **3 s**

**(a) Prompt**
Slow cinematic push-in on a long queue of young Algerian women students in a covered walkway outside a residence administration office, each holding a worn paper folder, tired patient expressions, minimal movement, nobody speaking. Behind them a pale concrete façade and a shaded counter where a clerk stamps forms over leaning stacks of binders. 35mm lens, eye level, f/2.8, shallow focus, gentle handheld drift. Late-morning Mediterranean light, soft window shadows, slightly desaturated warm grade. Overcrowded, ordinary, real.

**(b) Negative**
`readable text, legible forms, Arabic or Latin lettering, digital screens, smartphones, modern glass building, aggressive or distressed faces, chaotic crowd pushing, tourists, western dorm stock-photo look, extra fingers, deformed hands, flicker, morphing`

**(c) 3.0 s** (generate 5 s, trim head 1 s / tail 1 s)

**(d) Continuity** — STUDENT block, seen mid-queue in profile (she reappears in shots 3 and 5 in the same cardigan + beige scarf). No men in frame. Wardrobe palette: navy/grey/white only.

---

## SHOT 2 — PAIN 2 · 3.0–6.0 s · **3 s** (2 beats, cut on the beat)

**(a) Prompt — beat 2A (primary, 2 s)**
Extreme close-up of a chrome tap dripping into a stained enamel basin in a shared female student room, one slow drop falling, water beads on the metal. A young woman's hand enters and presses a small paper note onto the mirror edge with two fingers, the writing deliberately illegible. 85mm macro, f/2.8, near-static with a whisper of handheld. Cool side window light, warm skin, muted grade. Quiet neglect.

**(b) Negative**
`legible handwriting, readable text, letters, numbers, labels, brand engraving on the tap, horror grime, mold, deformed hand, too many fingers, dripping blood, flicker, morphing, watermark`

**(c) 2.0 s** · beat 2B (desk) runs 1.0 s, see §3.

**(d) Continuity** — hand only: STUDENT's skin tone and cardigan cuff. Basin/tile palette stays desaturated teal-grey so the 6 s turn reads as a jump in brightness.

---

## SHOT 3 — TURN · 6.0–9.0 s · **3 s**

**(a) Prompt**
Medium close-up of the student sitting cross-legged on her bed in a bright female dormitory, thumb tapping a phone, a flat even teal glow lighting her face and navy cardigan. Her tired expression softens into relief and a small private smile. 50mm, f/2, slow slider move right to left, bright window daylight plus one teal bounce. Clean, noticeably brighter and more saturated than before, warm skin tones, teal shadows. Tidy shared room, several made beds blurred behind.

**(b) Negative**
`readable phone screen, app interface, UI elements, text on screen, white or blue screen glow, reflections of a screen in the glass, men in the room, distorted hands, extra fingers, flicker, morphing, watermark`

**(c) 3.0 s** (generate 5 s, use middle 3 s for the steadiest glow)

**(d) Continuity** — STUDENT identical: beige scarf, navy cardigan, white top, gold studs. Room must match beat 2A (same window side, same bedding). This is the grade pivot shot: everything after is 10 % brighter, +teal shadows.

---

## SHOT 4 — SOLUTION · 9.0–14.0 s · **5 s** (3 beats, fast cuts)

**(a) Prompt — beat 4A (primary, 2 s)**
Medium shot of the director at a modern desk in a bright administration office, hand raised toward a large monitor, explaining to the staff member who nods in understanding. Clean desk, one small olive plant, faint zellige tile detail on the far wall. 35mm, f/2.5, slow push-in, eye level, light handheld. Daylight from frame left, warm skin, navy and teal accents, small gold lamp glow. Calm, competent, optimistic, no speech.

**(b) Negative**
`screen content, UI, dashboards, readable text, logos, watermarks, captions, speech mouth shapes, exaggerated acting, corporate stock stiffness, distorted hands, extra fingers, flicker, morphing`

**(c) 2.0 s** · beats 4B and 4C at 1.5 s each — see §3.

**(d) Continuity** — DIRECTOR and STAFF blocks verbatim. Monitor is a flat neutral dark-grey rectangle (composited later). Same office geography as beat 2B so the two cuts feel like one location, five minutes apart.

---

## SHOT 5 — BENEFITS MONTAGE · 14.0–17.0 s · **3 s** (4 beats)

**(a) Prompt — beat 5A (primary, 1.2 s)**
Wide-medium shot of the residence courtyard in bright light, the student walking with two female friends along a pale concrete path between olive and palm trees, calm unhurried pace, dappled shade, arched façade detail in the background. 50mm, f/2.8 shallow, slow lateral slider following them, late-afternoon sun, light anamorphic flare, warm optimistic grade, teal shadows, gold highlights. Clean, calm, premium.

**(b) Negative**
`readable text, signage on the buildings, university name, logos, crowded chaos, hurried or stressed students, fashion shoot posing, tourists, men in the frame, deformed hands or faces, flicker, morphing`

**(c) 1.2 s** · beats 5B/5C/5D at 0.6 s each — see §3.

**(d) Continuity** — STUDENT in the same cardigan and backpack. Courtyard dressing (olive + palm, pale concrete, arches) identical to shot 6. The director's smile at the end of 5D must match shot 4 lighting direction.

---

## SHOT 6 — END CARD · 17.0–20.0 s · **3 s**

**(a) Prompt**
Smooth crane rise over the residence courtyard at golden hour, camera drifting up and back across olive trees and pale concrete blocks as low sun flares across the lens, a few students reduced to small silhouettes. 24mm, f/4, slow steady rise, gentle film grain. Golden light, long shadows, warm skin tones, teal shadows, soft haze. As the camera clears the treeline the sky dissolves into smooth out-of-focus wash, keeping the center of the frame clean and empty for a later graphic. Peaceful, resolved, premium.

**(b) Negative**
`text, logo, watermark, captions, signage, modern glass towers, kitsch orange sunset, heavy HDR, visible drone, flicker, morphing, empty CGI plaza look`

**(c) 3.0 s** (generate 5 s, crop the last 3 s of the rise)

**(d) Continuity** — Same courtyard as shot 5, same time of day progressed warmer. The last 0.5 s is graded in post to the navy→teal gradient and the end card takes over on a 6-frame cross-dissolve.

---

## 1. Post-production checklist

**Edit conform**
- [ ] Assemble at 24 fps, 1080p, Rec.709 timeline. Master 16:9 first; build the 9:16 as a separate sequence.
- [ ] Shot lengths: 1 = 3.0 s, 2 = 3.0 s, 3 = 3.0 s, 4 = 5.0 s, 5 = 3.0 s, 6 = 3.0 s. Total 20.0 s.
- [ ] Beat cuts land on 24-frame boundaries; beat 4 cuts every ~36 frames (1.5 s) to build speed.

**Screen composites (real recordings, never generated)**
- [ ] Login screen — clean, no credentials visible.
- [ ] Staff dashboard with live counters (occupied beds, open tickets, pending applications).
- [ ] Pending application with the roster-match badge.
- [ ] Maintenance ticket with photo.
- [ ] Notification toast (upper third of an office scene — avoid shot 4's blank monitor being covered twice).
- [ ] Student's room + status page.
- [ ] Track the recorder at 2× the screen size and scale down 50 % for crisp edges; add 2 px inner shadow + 6 % screen reflection over the UI.
- [ ] Retime to 24 fps with optical-flow, no frame blending artefacts on scrolling lists.
- [ ] Shot 3's teal phone glow stays as-is; the app is only readable in the composited insert, not in the generated hand.

**Type, logo, brand**
- [ ] Burn captions in the editor (not in the prompt): sentence case, 3–6 words per line, safe margins 10 % / 5 % for 16:9.
- [ ] End card: place `resivo_logo_transparent.png` dead center, max width 38 % of frame; tagline directly below; CTA "resivo.dz" or the real URL at 5 % safe margin.
- [ ] Brand hexes applied in the grade only: navy #0A2F5A, teal #0D7180 / #109D9A, gold #E5A853, white. Never ask the generator for hex — describe colours in words and match in post.
- [ ] Gradient: build a linear navy→teal ramp in the editor over the final 12 frames; keep any generator haze underneath at 30 % opacity.

**Sound**
- [ ] Voiceover from the separate script, laid in after picture lock, ducked music.
- [ ] Royalty-free music bed, instrumental only, no lyrics, licensed for commercial + paid social. 20 s, edit to end on a resolved chord at 19.7 s.
- [ ] 4 SFX: (1) paper stamp thud-lean at 1.8 s, (2) notification ping at 7.2 s, (3) tap-water stopping / valve squeak at 12.4 s, (4) soft whoosh on the shot 5→6 transition at 16.9 s. Keep all SFX below −18 LUFS except the stamp (−14).
- [ ] Loudness: −14 LUFS integrated for online, true peak −1 dBTP.

**Delivery**
- [ ] 16:9 master: H.265, 1080p, 24 fps, 12–16 Mbps.
- [ ] 9:16: 1080×1920, re-frame (see §4), captions re-laid above the bottom 250 px UI zone.
- [ ] Export one textless version for localisation and one with burned-in captions per platform.

---

## 2. Consistency checklist

**Characters (lock before generating shot 2)**
- [ ] Generate a 4-panel character sheet per person at the top of the session; use it as a reference/init image for every shot.
- [ ] Paste STUDENT / DIRECTOR / TECHNICIAN / STAFF blocks verbatim — never paraphrase wardrobe between shots.
- [ ] Wardrobe never changes: student beige scarf + navy cardigan + white top + backpack; director light-blue shirt rolled sleeves + gray beard + metal glasses; technician teal vest + gray tee + black toolbox.
- [ ] Age and build stay fixed; nobody gains/loses glasses, beard, or jewellery.
- [ ] Single-gender dorm scenes; no male face inside the room in shots 2 and 3.

**Colour**
- [ ] Three-state grade: A (shots 1–2) desaturated, warm-neutral; B (shots 3–5) +10 % saturation, teal shadows, warm skin; C (shot 6) golden, softer contrast.
- [ ] Teal appears as light, never as a flat wash: bounce on the student's face, lamp glow, vest, wall tiles.
- [ ] Gold only in shot 4 lamp and shot 6 sun — it is the accent, not a base.
- [ ] One LUT applied to all clips at the end of the grade; check navy values don't clip to black.

**Lighting / camera**
- [ ] Light direction per location: office = window at frame left; dorm = window camera-left, teal bounce camera-right; courtyard = sun back-left in both 5 and 6.
- [ ] Lens language fixed: 35 mm (1, 4), 50 mm (3, 5), 85 mm macro (2A), 24 mm (6). No zoom, no whip pans, no drone acrobatics.
- [ ] Move types limited to slow push-in, slider, light handheld, one crane rise. Every move starts and ends calm.
- [ ] Shallow DOF everywhere except shot 1's deep queue and shot 6's wide.

**Continuity of objects**
- [ ] Same folder set, binder stacks, desk plant, monitor bezel, toolbox, and office wall tile across their appearances.
- [ ] Hair, scarf folds, and rolled sleeves match at every cut where a character reappears.
- [ ] No text anywhere in any generated frame — check at 200 % before the edit.

**Text & safety**
- [ ] Global negatives applied to every generation, plus the per-shot list.
- [ ] No lip-sync anywhere: mouths closed or smiling, VO added later.
- [ ] Dignified, non-stereotypical framing: real architecture, ordinary light, no "exotic" grading, no orientalist props.

---

## 3. If the generator only makes 5-second clips

Every shot is under 5 s already, so the rule is: **generate one 5 s clip per beat, then trim in the edit.** Never ask one generation to contain two locations or a cut — models morph instead of cutting.

| Beat | Shot / time | Generate | Use | Prompt tweak |
|---|---|---|---|---|
| 1 | Shot 1 · 0–3 s | 5 s | 1.0–4.0 s | Add "camera already moving at the first frame" so trim-in isn't static |
| 2A | Shot 2 · 3–5 s | 5 s | 0.0–2.0 s | Prompt as written |
| 2B | Shot 2 · 5–6 s | 5 s | 2.0–3.0 s (1 s) | **"Close-up of the director's hand flicking through a thick stack of paper files on a desk, folders fanned out, wristwatch, other hands waiting at the edge of frame. 50mm, f/2, static, hard side light, dust in the air. Overloaded, tired, desaturated."** |
| 3 | Shot 3 · 6–9 s | 5 s | 1.0–4.0 s | Best 3 s = steadiest glow; check the thumb doesn't teleport |
| 4A | Shot 4 · 9–11 s | 5 s | 0.0–2.0 s | Prompt as written |
| 4B | Shot 4 · 11–12.5 s | 5 s | 1.0–2.5 s | **"Close-up of the technician in a teal work vest photographing a freshly repaired chrome tap with his phone, thumbs framing the shot, bright tiled bathroom, toolbox at his feet. 50mm, f/2.2, slight handheld, cool daylight, clean and bright, satisfied."** |
| 4C | Shot 4 · 12.5–14 s | 5 s | 1.5–3.0 s | **"Medium close-up of the student sitting on her bed, phone at her chest, smiling at someone off-camera, teal glow fading, bright dorm, several made beds. 50mm, f/2, tiny push-in, warm window light, optimistic."** |
| 5A | Shot 5 · 14–15.2 s | 5 s | 1.0–2.2 s | Prompt as written |
| 5B | Shot 5 · 15.2–15.8 s | 5 s | 0.0–0.6 s | **"Close-up of hands at a light wood front desk, a key on a brass fob sliding across, another hand receiving it, no text on any tag. 50mm, f/2, static, warm interior light, smooth and helpful."** |
| 5C | Shot 5 · 15.8–16.4 s | 5 s | 0.0–0.6 s | **"Close-up of the technician closing his black toolbox, latch clicking down, teal vest sleeve, tiled floor, bright daylight. 50mm macro, f/2.8, static, clean and finished."** |
| 5D | Shot 5 · 16.4–17 s | 5 s | 1.0–1.6 s | **"Medium close-up of the director looking straight at camera with a calm warm smile, glasses catching light, office bokeh behind. 50mm, f/2, static, soft daylight, confident, no mouth movement."** |
| 6 | Shot 6 · 17–20 s | 5 s | 1.0–4.0 s | Prompt as written; use the cleanest rise |

Practical notes:
- Keep the **same seed** per character and per location across beats; re-seed only when a beat needs a different framing.
- Request 5 s even for 0.6 s beats — extra frames give you handles for the trim and the cross-dissolve.
- For 4B/4C/5B/5C/5D, generate 3 takes and pick for hand quality; hands are the main failure mode.
- If a beat costs too much, drop 5B and hold 5A longer — the montage still reads.
- Upscale with a video upscaler, not by re-generating: re-generation breaks continuity.

---

## 4. 9:16 vertical framing notes

Method: keep all action inside the **central 60 % of the 16:9 width** (x = 20 %→80 %) and the central 80 % of height. Then crop or scale to 1080×1920. Where the model supports native 9:16, generate natively and use the 16:9 take only if it beats it.

| Shot | 9:16 note |
|---|---|
| 1 | Push-in must be **vertical-safe**: compose the queue in the middle band, clerk and binder stack centered. Vertical version: crop to the clerk plus two students — the line can leave frame bottom. |
| 2A | Macro reads perfectly vertical; keep the drip column centered, basin mouth at 60 % height. 2B: crop to the hand + folder stack only. |
| 3 | The strongest vertical shot — face on the upper third, phone and teal glow at center, beds as background only. Room for a caption band at 20 % height. |
| 4A | Monitor is the portrait's weak point: reframe to a **vertical medium** — director on left third, blank monitor at center-right, staff shoulder in the foreground bokeh. Monitor must still read as a screen at a glance. |
| 4B | Phone and tap central, hands at 55 % height, toolbox at bottom edge. |
| 4C | Face upper third, phone at center; leads naturally into Reels' first-frame banner zone. |
| 5A | Walking group centered in the band, path leading to frame bottom; doors/arch keep top clean. |
| 5B–5D | All three are close-ups — they crop natively. Keep the key object within the central 60 %: key fob, toolbox latch, director's eyes. |
| 6 | Crane rise must end with **empty sky in the top 55 %** for logo + tagline. In 9:16 build the gradient in the editor and stack: logo at 42 % height, tagline under it, CTA at 72 %. |
| Captions | 9:16: burn at 62–72 % height, above the bottom 250 px platform UI. Max 2 lines, 34–40 pt at 1080 width. |
| Safe zone | Never place the student's face, the app recording, or the end-card logo inside the outer 8 % of the vertical frame. |
