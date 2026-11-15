# Critique

Who scores the work, against what, and how many rounds to run. For *how* to critique and refine, follow interface-craft's `design-critique.md`: its lenses, its "what I see → why it hurts → what it could be" format, and its way of fixing in small steps, looking again after each. This file adds the juries' criteria, the critic, and the number of rounds.

## The juries' criteria

**Websites**, the way Awwwards juries score them:

| Criterion | Weight | What the jury is asking |
|---|---|---|
| Design | 40% | Is the visual craft exceptional: type, color, layout, imagery, motion, and the consistency of all of it? |
| Usability | 30% | Is it fast, clear and easy to use on every device, with nothing broken, confusing or slow? |
| Creativity | 20% | Is there an idea here nobody has done this way, and does it surprise? |
| Content | 10% | Does every word, image and piece of media earn its place, and is it written well? |

Weighted score = 0.4 × Design + 0.3 × Usability + 0.2 × Creativity + 0.1 × Content.

**Apps**, by the Apple Design Award categories: Delight and Fun, Inclusivity, Innovation, Interaction, Social Impact, Visuals and Graphics. Pick the one or two categories the app should win in, and score those plus Interaction and Visuals and Graphics, which every app has to earn. The score is their average.

**Calibrate against real winners.** Before scoring, look up recent Awwwards Sites of the Day in a similar category (for apps, the latest Apple Design Award winners and finalists). Judge the work against those, not against average work.

This skill's scale, 1 to 10:

- **10:** Site of the Year or an Apple Design Award winner. People share it unprompted.
- **9:** Site of the Day, or an Apple Design Award finalist.
- **8:** an Honorable Mention. Polished, with a memorable moment or two.
- **7:** solid professional work that nobody will remember.
- **6 and below:** visible problems.

## The critic

Use a fresh agent with no conversation history and no stake in the work. In Claude Code, that's the Agent tool. In Codex, it's `spawn_agent` without forking the conversation. Give it only:

- the brief: what this is, who it's for, the platform, and the feeling it should create
- the captures: stills at each size and theme, contact sheets of the key motion, and the measurements
- this file

Use a new critic every round, so earlier scores don't anchor it. If you can't start another agent, critique it yourself from the captures alone, as if seeing it for the first time.

Prompt for the critic, filled in:

```
You're judging this for Awwwards Site of the Day [or: an Apple Design Award in <categories>].
Score harshly: solid professional work scores 7, and you've seen this year's winners.

Brief: <what it is, who it's for, platform, the feeling it should create>
Captures: <paths to stills, contact sheets, measurements>
Rubric and scale: <path to this file>

1. Score each criterion 1-10, with one line of evidence each, then the weighted score.
2. List every problem as "what I see → why it hurts → what it could be", biggest first.
3. Name the single most wrong note.
4. Name the moments, if any, that would make a juror say "wow".
5. Say what it would take to win.
No praise padding.
```

## One round

1. The critic scores the work.
2. Fix the biggest kind of problem first: wrong structure, then wrong behavior, then wrong looks.
3. Recapture and re-measure everything you changed, and everything that shares its components.
4. Log the round's scores and fixes in the design log.

## How many rounds

One, by default. Then stop and report what step 5 of SKILL.md lists, so the user can decide whether to go again.

Run more only when the user asks, and do what they asked:

- **A number of rounds** ("do three rounds"): run exactly that many, with a new critic each round.
- **A bar** ("keep going until it's a 9", "iterate until it's perfect"): keep going until a fresh critic's weighted score reaches it. If they don't name a number, the bar is 9 or more, with no criterion below 8.5. If three rounds in a row don't raise the score, stop and tell the user what's holding it back and what it would take.

Naming the award as the goal ("so it could win Site of the Day") isn't a request for more rounds; every job aims there.
