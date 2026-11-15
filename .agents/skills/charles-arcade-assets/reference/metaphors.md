# What to show for what is said

The whole style rests on one move: take the words being spoken and draw them **literally, as a moment from a
video game**: the mascot doing it, the product doing it, or the real thing itself. Not a diagram of the idea,
not an icon: the thing itself, happening. A muted viewer should still get the joke.

## Cast for the topic

The cast is decided per video, before the beat sheet. Keep it small: a host and one to three others.

- **Claude, Claude Code and AI-tool videos:** the host is the code-drawn Claude critter (`critter.js`), flat
  coral with square eyes, the mascot viewers know. It plays a different role for every idea by holding or
  wearing a prop (a magnifier for research, a hard hat and hammer for building, binoculars for tracking, a visor
  and calculator for budgets). Two Claude sessions or jobs are two coral critters told apart by props and
  costume (a mail cap and satchel for outreach, a tie and clipboard for the manager), never by colour; another
  company's agent may be a recoloured critter. ChatGPT is the `gpt` sprite.
- **Any other topic:** keep a host, then make characters for the topic's ideas with `tools/cast.py new` (about
  $0.45 each, same pixel style). The host is the pal (`shape: "pal"` in `critter.js`: the critter's neutral
  cousin, free, every role and prop works on it), recoloured to the topic, or Charles himself as a pixel
  character (`cast.py new ... --photo <his photo>`). The others are the ideas the video argues about:
  - **the enemy**, the problem made into a creature: "AI slop" as a purple goo blob dripping gradients with
    sparkle-emoji eyes; "the algorithm" as a boss; "burnout" as a storm cloud;
  - **the goal**, what the viewer becomes: "god tier" as a crowned wizard, a trophy, a level-up aura;
  - **the rival**: the other product, the competitor, the old way.
- Every blueprint that features the host takes `HOST`: "critter", "pal", or the folder of a cast.py character
  (Charles from his photo hosts the whole video, crowned at the end; reference/cast.md).
- **Two-sided stories** (an app and its users, a seller and a buyer, a creator and a viewer): the host plays the
  product, or the creator's side, and causes the mistakes and the fixes; a `cast.py` character plays the user, the
  player who walks through it; the crowd plays users in bulk. Either of the two acting counts as the mascot acting.
- Pick the two to four worlds the video returns to (a design studio, a library, a trading floor, a museum) and
  generate them as plates in the card's shape.

Two worked casts for topics outside AI:
- **"Your website looks like AI slop: three fixes"**: the critter as a designer (beret and paint roller); Slop,
  the purple goo monster; worlds: a pixel design studio, a browser showing real sites (`source.py page`), a
  slop-detector machine. Kill the purple gradient: the critter rolls one brand colour over a violet gradient
  while Slop shrinks. Stop centering everything: a grid snaps the hero left and one headline grows. Delete the
  emoji feature grid: rocket, sparkle and lightning tiles drop into a bin and real product screenshots slide in.
  "Template to ten out of ten": a compare slider and a score counter landing on 10/10, stamped.
- **"Five resources that took me to god tier marketing"**: the critter as a marketer (megaphone), crowned at the
  end; worlds: a pixel library, a tier-list board, a loot screen. Each resource is the real thing (the real
  *Influence* cover from `source.py book`, the real Lenny's Newsletter page, the real *$100M Offers* cover)
  dropping into the S row with a stamp, or opened like legendary loot with a gold glow; an XP bar fills a
  level per resource; the crown lands on "god tier".

## The library

| When the voiceover says... | Show |
|---|---|
| X vs Y, compare, debate, "fight", "battle" | fighting-game VS select screen, then the two fighting in an arena with health bars and ROUND 1 |
| a product, feature or skill name ("it's called X") | title card: the mascot in that role's costume on a sand mound, the name landing big, "A Claude skill pack" under it |
| "it's free" | the real repo or site page settles, a green FREE stamp slams onto it and the page bumps |
| "biggest update", new version, launch | a wooden crate stamped with the version number drops into a pixel town square, its download bar fills |
| a list, "three ways", "here are N", options | one beat per item; items as game cartridges, inventory slots or loot cards; the count on screen |
| N of something ("11 skills", "5 agents") | the lone mascot in one role, then it shrinks into slot 1 while the other N-1 role variants pop into a grid; tiles with their names rise |
| ranking, "10/10", "S tier", "god tier", "the best" | a tier list (S/A/B/C rows; the item drops into S with a stamp); a score counting to 10/10; a legendary item card glowing gold (blueprint `tier-list`: items drop into their row with a stamp, the head tile rockets to the top, a crown lands) |
| resources: books, newsletters, courses, tools | the real thing: the real cover rising out of a treasure chest with its title and author plates (`book-reveal`), dropped into a tier row (`tier-list`), or flying into the loot bar (`loot-bar`) |
| "by X", the author, the person behind it | their credited photo in a gold frame, the nameplate slamming on the name (`author-card`) |
| a mistake, bad practice, "slop", "bad answers" | the topic's enemy or the bad version on screen getting crossed out with a marker X, kicked into a bin, or GAME OVER |
| the fix, good practice | the mascot fixing it with a tool prop (a roller painting over, a hammer, a wrench); the scene changes as it works |
| before/after, "from X to Y", "template to 10/10" | a before/after slider pushed across by the mascot while a % or score climbs, then a stamp |
| "killed", "dead", "replaced" | the mascot pulls the plug on the old thing: screens die one by one, an RIP tombstone slams down with dust and a shake |
| "clone", "copy" | a photocopier fed with the real icons; copies pop out wearing a badge |
| "steal", "take" | a museum heist: the mascot lifts the real things out of gold frames and carries them off |
| "copy any expert/investor" | a portrait gallery of the real people (credited photos); their picks copy across on a rail while the portrait flips through more names |
| a secret, trick, shortcut, "cheat code", hack | cheat-code entry: ↑↑↓↓←→←→BA typed into slots, CHEAT ACTIVATED, the payoff counter |
| powerful, best, strongest, upgrade | RPG stat bars (POWER, CLASS) filling; LEVEL UP; a power-up item |
| saving money, credits, cheap, subscriptions | a receipt: a pixel marker strikes each line as the total counts down to $0.00, circled |
| making money, sales, revenue | a lock screen stacking real-looking Stripe or Shopify notifications; a chart line drawing with the mascot riding the tip; coins stacking |
| research, finding, searching, scanning | the mascot sweeps a magnifier whose lens magnifies the real content; a scanner grid counting thousands; a pixel library |
| tracking, monitoring, "breaking news" | binoculars from a rooftop; dark screens switching on one by one; a notification sliding down |
| "until you approve", permission, safety | a guard at a velvet rope holds the order chip; the permission dialog; the cursor clicks Allow |
| competitors, "their weak points" | a scout critter peeks over a bush with binoculars at the rival's real App Store page; cut to a binocular view of their 1-star reviews, a red marker circle, a luggage tag stamped "FEES · 106 of 341 bad reviews" |
| sending outreach, emails | a Gmail compose with the personal line typing in highlighted; the Sent list filling row by row; a snackbar counting "40 emails sent" |
| replies, conversations | a pixel mail room: letters fly into labelled pigeonholes whose counters tick; speech bubbles trade the question and the answer |
| "books the call", meetings | a calendar slot turning into a solid event as the camera pushes onto it; then the mascot pops into its seat in a video-call tile |
| raising money, funding, a deal closing | a seed watered into a money tree while the camera pulls back and a tag counts to the raise; a cheque settling with the amount filled in |
| suppliers, factories, "who makes it" | a detective critter's flashlight x-rays a shipping container full of the product; customs rows populate and a red box lands on the cryptic line; a container ship crossing a pixel map to a pinned factory |
| margins, pricing, "what it costs" | a balance scale with a price tag on each pan, both counting up, the beam tipping; a receipt printing line by line down to "left per unit" |
| stuck, confused, guessing | the mascot sinking in mud with "?" marks popping above it |
| "you're handed a plan" | the mascot pushes a big binder toward the camera |
| lying, wrong, hallucinating | a lie detector stamping LIE; GAME OVER; a health bar draining; the mascot hurt or sad |
| a question, a test, getting it wrong | a game-show podium: the question on a pixel board, the wrong answer buzzed with big red X's |
| attack, expose, criticise | a turn-based RPG battle: HP boxes, "X used EXPOSE!", the hit lands, the HP drains |
| a team, agents, several sessions | a party of coral critters, each in its own costume and props, at desks in a pixel office, speech bubbles between them |
| sessions or agents talking to each other | two desks joined by a tin-can phone, "40 leads ready" in a speech bubble; then two real chat windows, one messaging the other while a courier critter carries the envelope between them |
| "most people don't know", confusion | a crowd of small pixel people, "?" bubbles popping over each in a stagger, the critter sweating |
| choosing the cheapest model, routing tasks | task cards fly in arcs to critters of four sizes (Fable, Opus, Sonnet, Haiku); price tags pop ($50 / $20 / $10 / $0.50); the cheapest gets a green badge; a receipt strikes the expensive prices |
| customizing, reskinning, themes | a painter critter rolls paint across the actual app and the UI changes under the roller |
| "everyone can tell", "everyone knows" | a crowd of pixel townsfolk raising paddles (AI, ?, a logo) one by one, then all pumping them; the host sweats (blueprint `crowd-signs`) |
| "nobody trusts", "nobody wants it" | the same crowd raising X paddles while a TRUST meter drains to 0% (`crowd-signs` with `METER`) |
| N fixes, tips, mistakes, rules | an RPG battle: the problem is a monster with an HP bar; on "number one" the menu cursor picks the move, the hit lands, HP drops a third, SUPER EFFECTIVE; the last fix KOs it (blueprint `rpg-battle`, one beat per round) |
| a list of named things said fast ("rocket, sparkles, lightning bolt") | a police lineup: a camera flash on each word, each thing against the height chart holding its placard (blueprint `lineup`) |
| "stop doing X" | a referee host blows a whistle, a STOP sign slams on, a red X over the offending element (`referee` role, `AR.crit.blow`, the `stopsign` prop, a `redcard`) |
| "pick one", choose | a fan of options (paint chips, cards, cartridges); the host pulls out the chosen one and it pops big with a check (`paintchips` + `AR.fan`) |
| "make one thing big", emphasise | the element is selected in a design tool and dragged huge by its corner handle, the host riding the handle (`AR.wbSelect` + `AR.wbResize`) |
| a design or layout fix | the running example's page in a design tool: guides draw, a 12-column grid unrolls, elements snap into place (`.wb-figma` with `AR.wbLanding`, `wbGuides`, `wbGrid`, `wbSnap`); "looks like every other site" is the `slop` skin turning `editorial` with `AR.wbSkin` |
| automation, speed, "instantly", "while you sleep" | a big button the mascot slams; FILLED stamps cascading down a list; a stopwatch spinning; ×1 bursting into ×100 |
| setting up, installing, "paste this link into Claude" | the real repo page, readable; the cursor clicks Code and copy, "Copied!"; the link flies as a chip into Claude's input, "install skill" types, send, "Skill installed" (blueprint `setup-flow`; never a repo shrunk to a thumbnail) |
| the winner, "only the best is left" | last one standing, victory pose, crown or trophy, confetti |
| a number or percentage | a counter in the scene with real formatting (5,259 · $1,250 · 99.2%), landing on the word |
| anything shown on a screen | the rebuilt or captured UI doing exactly that, with the mascot acting on it |
| "follow me and comment X" | the CTA card (blueprint cta-follow) |
| onboarding, "the first screen", "the first 60 seconds" | the first level of a game (World 1-1 with a USERS / TIME HUD): the new user is the player, the app's screens are the level, a stopwatch races down; the home screen, the finger taps the app and it zooms open to its first screen (`AR.wbLaunch`) |
| losing users, churn, drop-off | users walking off a ledge into a pit while a USERS counter ticks down; a funnel leaking pixel people; "-1 USER" as one walks out of the level |
| friction: a sign-up wall, a long form, a forced step | a literal brick wall with the form on it slamming down in the user's path; the user bonks into it; then the rebuilt wall (`.wb-signup`: Continue with Apple / Google / email, no Skip) with a red loop round the buttons |
| permission prompts, "asking for notifications" | the exact iOS alert popping over the app ("Would Like to Send You Notifications", `.wb-alert data-alert="notif"` with `AR.wbAlert`; also `att` and `location`), the finger tapping Don’t Allow; the host as a stranger in sunglasses and a fedora ringing a bell in the user's face; a crowd raising NO paddles |
| a paywall, "show the price" | a toll gate with the price board ($/yr) in front of the treasure chest the user can't reach; the rebuilt paywall (`.wb-paywall`) sliding up as a sheet, the price rolling in on "price" (`AR.wbPrice`), the trial switch flipping (`AR.wbToggle`) |
| the aha moment, the first win, value | the chest opening or a bulb lighting over the user; FIRST WIN! with a trophy; then the alert flips to Allow and the paddles to YES |
| retention, day one, growth | the product's retention chart flat, then the line climbing past a "new onboarding" marker with the host on its tip, a +N pts badge |
| N mistakes in one product or journey | an overworld map: the route from START to the goal with one numbered trap per mistake; each "number N" hops the user onto its node; "fix them" flips every X to a check (blueprint `quest-map`: an intro beat, one hop beat per number, then `fix`) |
| "save your progress", a prompt mid-flow | a bottom sheet sliding up over the app (`AR.wbSheet`), the finger tapping its button |

When a phrase has no entry, ask: if this sentence were a cutscene in a cute 16-bit game, what would the mascot
be doing? Choose a concrete object or action, never an abstract symbol.

## The rules that make it work

- **Frame 0 is the hook.** The first line as a visual joke, already on screen at frame 0, usually the mascot
  causing it (pulling the plug, feeding the copier, lifting the painting). Inside jokes the audience knows land
  hardest.
- **About one beat per second, and motion inside it.** Median beat 0.8-1.0 s (Jake's reels: 0.80-1.02 s,
  28-42 beats in 30-39 s). Inside a beat something changes every 0.2-0.4 s. Nothing holds still for more than a
  second except a page being read or the final card.
- **Land on the word.** The key change in a beat (the hit, the stamp, the title, the number) lands on the frame
  the stressed word starts. Entrances start 2-4 frames before it.
- **The mascot is the actor.** It causes every change it can: pulls, presses, throws, stamps, carries, rides
  the chart, pushes the slider, rings the bell, and the scene reacts. In about two thirds of the beats. A mascot
  that only stands beside the content is wasted.
- **One body, many roles.** Give the mascot a prop or costume per idea (a costume can fall onto it on the word)
  instead of adding characters. Claude's own sessions and jobs stay coral and differ by props; a recoloured critter
  is only another company's agent.
- **Real things beat drawn things.** The real page, icon, logo, book cover and photo, fetched with `source.py`.
  Draw only what doesn't exist: the mascot, the metaphor, the game world. Real people are credited photos,
  never generated.
- **Bad examples are invented.** When the voiceover criticises a pattern ("AI slop", a bad landing page, a scam),
  show it on an invented product or page (a made-up café app, a made-up brand), never a real company branded as
  the bad example, unless Charles names it himself. Real things are for good examples and neutral facts.
- **Puns and physical comedy.** When a word has a literal second meaning, show it, short and on the word:
  "service" rings a desk bell, "steal" is a heist, "killed" pulls a plug. Props are for doing things to: crumple
  the script and kick it in the bin, throw darts at the board, hop key to key onto Enter.
- **Physical comedy with the real UI.** The best beats have the cast doing something physical to the
  interface: the critter hauls ChatGPT into the Claude chat on a rope ("pulls ChatGPT into your conversation"),
  fighters rip the claim bubbles in half ("tear apart each other's arguments"), a magnifier reveals the fine
  print ("expose weak logic"), a painter rolls new paint across the actual app and it changes under the roller
  ("customize the way Claude looks"), a courier carries the envelope from one chat window into the other.
- **Metaphor, then the product.** Show an idea twice in a row: first as the game moment, then the real product
  doing it (a tin-can phone between two desks, then two real Claude chats messaging; a cartridge clicking into a
  console, then the Usage page; critters of four sizes, then the price tags, then the receipt).
- **Inside jokes in the hook.** Cycle the memes the audience knows: a Claude-branded magic 8-ball answering
  STRAWBERRY HAS 2 R'S, 9.11 > 9.9 and YOU'RE ABSOLUTELY RIGHT! every half second as the critter head-butts it.
- **Art direction from the name.** Let the product's name or the hook's verb choose the worlds: a skill called
  "Seed" opens on a grave being watered into a money tree and its title-card mascot carries a sapling pot; one
  called "Blueprint" opens and closes on white-line blueprint drawings. The pun is planted before the name lands.
- **A new scene for most beats.** Jake's reels use 10-22 different pixel scenes in 30-40 s. Reuse a world by
  re-framing it (a wider shot, a cut-in on a detail), never by holding the same frame for a new line.
- **Callbacks and gags across cuts.** The role grid from "N of them" comes back at "the craziest part" (others
  dim, the one grows out of its tile); the whole cast marches before the CTA; sunglasses fly up off the mascot in
  one shot and drop back onto it in the next.
- **Alternate worlds.** Swing between pixel scenes, rebuilt product UI and real pages. Never two beats in a
  row with the same framing and blueprint.
- **One running example, told as a story.** Pick one concrete case and carry it through every beat that can
  show it, with the same exact numbers, names and dates from `FACTS` (TSLA's breakout at $362.18, entry
  $364.18, target $370.04, stop $358.32; Calendly cloned into "Slotted": 23 screens, 146 files, 214 tests, 99.2%
  match, 1,241 reviews, 7 fixes, $5/mo). When the example is an invented company, give it a small brand kit
  (a logo drawn as SVG, a tagline, the people with initial avatars) and let cause lead to effect: find the
  investor, email her, she asks a question, the call is booked, the cheque arrives.
- **Real names.** Nameplates, tabs and chats use the names the audience knows: the product, its current model,
  the real repo path and handle when given.
- **Specific beats generic.** Fake data is plausible and specific ($212 round trip, 46% used, 3 of 5 claims);
  any number the voiceover says appears exactly as said.
- **The UI is the real product.** When the words describe doing something in an app, show that app (captured or
  rebuilt to look real) doing it, step by step on the words, with the camera pushing onto what matters.

## Segment format for a tool or skill launch

Jake's launch reels share one structure; use it when the video introduces a tool, skill or product:

1. **Hook gag** (0-2 s): the headline verb acted out in a pixel scene ("killed day traders": the plug is pulled).
2. **"You can now X"**: the product doing X (a monitor in the scene, pushed into until the app fills the card).
3. **"It's called X"**: the title card.
4. **"Completely free"**: the real repo page with a FREE stamp.
5. **"Not one skill, N of them"**: the lone mascot, the grid of N role variants, tiles with names.
6. **One beat per item**: each item's mascot variant acting on its UI, with the running example's numbers.
7. **"But the craziest part"**: spotlight on one tile (others dim, outline), it scales out toward the camera.
8. **The payoff**: the biggest world change of the reel (a full pixel world, a data reveal, the real person).
9. **"To set it up"**: blueprint `setup-flow`: the repo page (readable, never a thumbnail), Code → copy →
   "Copied!", the link flies into Claude's input, "install skill" types, send, "Skill installed".
10. **CTA**: Follow flips to Following, the keyword types into the comment box.

## Format for an education or listicle video

"Three fixes", "five resources", "the mistakes everyone makes": the structure that works.

1. **Hook:** the problem acted out on the viewer's own thing (their website under a magnifier, stamped AI SLOP)
   and the crowd's reaction ("everyone can tell": townsfolk raising paddles).
2. **"Here are N":** an inventory with N empty slots (`loot-bar`, and `AR.loot.bar` as a HUD in later beats) that
   the host fills with one item per number, or the RPG battle against the problem as a monster (`rpg-battle`), or
   the overworld map of N traps (`quest-map`).
3. **One stretch per item:** name it (the menu cursor picks the move on "number one"), show the bad version
   (crossed out, binned, in a lineup), then the fix done to the running example: the same invented page or
   product improves item by item, and the monster's HP drops.
4. **Payoff:** the inventory's checks tick; a before/after slider while the score climbs to 10/10; the crowd flips
   10 paddles; a crown drops on the host.
5. **CTA.**

For resources (books, newsletters, courses): each resource is a `book-reveal` (the cover out of the chest, the title
and author landing), its author an `author-card`, the ranking a `tier-list`; the loot bar fills one slot per item
(`FACTS.loot` and `FACTS.lootAt` keep it in step across beats and sizes).

## Worked examples (Jake's reels, measured frame by frame)

The visuals sit in a 2:1 card above his face most of the time, switching by hard cut to a tall card or a full
screen for the big moments. Use them to calibrate density, pacing and how literal to be.

### "Claude just killed day traders" (35 s, 35 beats, median 0.97 s)

| s | Words | Visual |
|---|---|---|
| 0.0-1.4 | Claude just killed day traders | pixel battlestation, 6 monitors with live candle charts; the critter yanks the plug, every screen dies in a random stagger, an RIP tombstone with candles slams down with dust and a shake |
| 1.4-4.1 | You can now make winning trades automatically inside of Claude | the critter in the gaming chair; push into the monitor showing the Claude app; punch-in on "placed a paper order", BUY TSLA rises, a blue PAPER stamp lands; zoom out of the app with parallax |
| 4.1-6.0 | It's called the Trader skill, and it's completely free | title card (critter in shirt and tie with a phone handset on a sand mound, "Trader"); the GitHub About panel, FREE stamp, page bump |
| 6.0-9.8 | And it's not one skill, it's 11 of them, every one does a different job | the lone critter with a chart board; it shrinks into slot 1 while 10 role variants pop in; white tiles rise, the critters hop along arcs into them, labels fade in |
| 9.8-13.2 | One scans thousands of charts for setups; another tracks breaking news | scanner grid counting 0 → 5,259 with ticks; zoom out to thousands of tiles; the hits fly into place; a news feed with a live insert; an iPhone notification, pushed into |
| 13.2-18.3 | ...finds the perfect time to get in, when to get out, how to make the most money | tall card: the candle chart with the range box; push onto the breakout candle, "Get in · 10:15 AM · $364.18"; target and stop lines draw; the critter jumps onto the target line |
| 18.3-21.6 | But the craziest part is the time machine skill | six tiles, the others dim, the time-machine critter scales out of its tile; a pixel steampunk time machine, the critter pulls the lever, its screen lights up, push into the clock |
| 21.6-26.5 | ...before you risk a dollar it replays every possible outcome, then gives you the statistics | the wallet chained, "$0 AT RISK"; 10,000 replays counted while paths fan out and recolour green or red; bars and a histogram with the running example's prices |
| 26.5-29.0 | It's the same type of software Bloomberg charges thousands for | a real, credited Bloomberg Terminal photo; a receipt ($31,980 a year) the critter strikes with a marker; "TRADER SKILL $0" |
| 29.0-35.0 | To set it up... follow me and comment TRADE | the install flow; a room of all 11 critters; the CTA |

### "Clone any app with Claude" (32 s, 31 beats, median 0.94 s)

| s | Words | Visual |
|---|---|---|
| 0.0-3.4 | You can now clone any app with Claude so you never pay for a subscription again | a pixel copier: the critter tosses the real Photoshop, Canva, Spotify and Notion icons in, Claude-badged copies pop out; cut to the copier's panel "CLONING..." on "Claude"; a receipt, each subscription struck, the total counting to $0.00, circled on "again" |
| 3.4-5.5 | It's called the Replica skill, and it's completely free | the real GitHub repo page, FREE pill |
| 5.5-8.9 | not one skill, 11 of them, each a different job | lone critter with a magnifier, then 11 roles (blueprint roll, hard hat and hammer, bug net, briefcase...), names fade in |
| 8.9-13.0 | One reverse-engineers the app, another rebuilds it, one tests it for bugs | Calendly's booking page with numbered red callouts in sync with a component legend, then an isometric exploded view; Claude Code recon output counting 23 screens; the builder critter hammers while the page assembles and a signpost counts 146 files; bugs caught with a net, 214 tests, 7/7 fixed |
| 13.0-15.0 | So you get a perfect clone of any app every time | the critter pushes a before/after slider while PIXEL MATCH climbs to 99.2%, ✓ PERFECT stamps on "perfect"; a deck of real app screenshots, each with its clone |
| 15.0-23.0 | But the craziest part is the entrepreneur skill: it researches the app, reads user feedback, finds missing features | spotlight on the suited critter; the real SKILL.md with a cursor; a search with real results; the real App Store page under a magnifier sweep; Reddit scrolling while a counter reaches 1,241 reviews; sticky notes and red ellipses on the real pricing page |
| 23.0-26.7 | Then solves all of those problems in your app, so you have an actual app you can sell | a terminal checklist ticking 7 fixes; the critter tears the "powered by Calendly" ribbon off; the clone's landing page "$5/mo flat"; Stripe payment notifications |
| 26.7-32.1 | To set it up... comment CLONE | install flow; CTA |

Patterns worth copying from both: every list item is its own beat; every number gets a counter with real
formatting; every "go here, click this" gets the UI doing exactly that; the critter causes the change in most
beats; real pages and logos carry a third of the beats; the biggest world change arrives on "the craziest part".
