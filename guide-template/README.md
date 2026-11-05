# Guide template

Turns a plain list of steps (`steps.json`) into ONE easy-to-follow guide file (`.html`).
Pictures and fonts are packed inside, so it works offline and you can send it as a single file.
You need Python 3 and nothing else. No packages.

## Make a guide
1. Copy `steps.starter.json` to your project (for example `my-project/guide/steps.json`).
2. Edit the words. Put screenshots in an `images` folder next to it.
3. Build it:

       python3 ~/ClaudeCodeTest/guide-template/build_guide.py my-project/guide/steps.json my-project/guide/guide.html

4. Double-click `guide.html`.

A finished example lives in `~/ClaudeCodeTest/field-cut/guide/` (steps.json, images, built html).

## What the guide does for you (the ADHD-friendly parts)
- Shows "3 of 16 done" and a progress bar at the top, always.
- Every step has a big green **I did this step** button. Ticks are saved in the browser, so closing the page loses nothing.
- **Where was I?** jumps to the next step you have not done.
- Each step shows a time ("About 1 min"), where to look, one action per line, and a green **You will see** box so you know it worked.
- **Stuck? Start here.** box at the bottom with plain-word fixes.
- Tap a picture to make it bigger. Esc closes it.
- Light and dark mode follow your Mac. Print hides the buttons.

## Rules for writing good steps
1. One action per line. Two actions means two lines.
2. Fifteen words or fewer per line. Plain words. No jargon.
3. Say WHERE first, then WHAT to do, then WHAT YOU WILL SEE.
4. Every step gets a picture with the thing circled in orange, when a picture helps.
5. Put a time on every step. Keep each step under 3 minutes. Split it if it is longer.
6. Same layout every step. No surprises, no animation.
7. Name buttons exactly as they appear on screen, in **bold**.
8. Keys go in double square brackets: `[[Cmd + S]]`.
9. Mark new steps with `"new": true` so returning readers can spot what changed.
10. Put the first fix for each common problem in the `stuck` list.
11. End with a finish message. Finishing deserves a pat on the back.

## steps.json fields
| Field | What it is |
|---|---|
| `id` | A short unique name. Ticks are saved under it. Change it when you change the guide a lot. |
| `eyebrow`, `title`, `lede` | Small label, big title, one friendly sentence |
| `flow` | The big picture as 4 to 8 one-word chips |
| `keys` | A "keys to remember" card (`key`, `does`) |
| `fonts` | Optional. Fonts to pack inside (`family`, `weight`, `path` to a .woff2). Leave out to use system fonts. |
| `steps[]` | `title`, `minutes`, `where`, `do` (list), `see`, `tip`, `image`, `caption`, `alt`, `new` |
| `stuck[]` | `problem`, `fix` |
| `finish_title`, `finish_text`, `footer` | The end message and the footer line |

## Taking the screenshots with orange circles
In a browser, draw an orange ring around the button with a small script, then screenshot. Field Cut's guide did it this way. Ask Claude to do it for you.
