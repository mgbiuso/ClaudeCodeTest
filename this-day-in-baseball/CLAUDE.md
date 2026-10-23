# This Day in Baseball: project rules

Claude reads this file at the start of every session. Follow it.

## What this project is
A static website. Plain HTML, CSS and vanilla JavaScript. No server, no database, no login.
Python scripts in `scripts/` build one JSON file per calendar day into `data/days/`. The page (`app.js`) loads those files.
A GitHub Actions workflow (`.github/workflows/build.yml`) rebuilds today's file each night. It only runs from the `main` branch.
The look is a 1999 newspaper sports section. Keep that look.

## About the owner
Mike is new to coding and does not know what he does not know. So:
- Act as a teacher and director. Explain ideas in plain words, like to a 12-year-old.
- Always give the exact menu, button or file location for any step he must do.
- Flag common beginner mistakes before they happen, and say why they matter.
- Never use em dashes in anything you write for him or put on the site.
- When you finish, say what changed, what you tested, and what you could not test.

## Safety rules (never skip)
1. Back up before editing. Copy any file you will change into `_backup_before_changes/` first.
2. Never commit, push or merge unless Mike says yes in this conversation. Show him the changed files first.
3. Never print, copy or commit a secret. API keys live in `.env` (ignored by git) and in GitHub Secrets. Never put a key in a page, a script that ships to the browser, or a data file.
4. Keep the site static. Do not add a server, database, login or paid service. If you think a small layer would help, pitch it first (see the `static-site-layers` skill) and wait for a yes.
5. Do not add outside scripts, fonts or CDNs to a page without asking. Every outside file is a risk and a slowdown.
6. Put outside text on the page with `textContent`, never `innerHTML`. Only allow `https://` links from hosts we expect (for example `www.loc.gov`).
7. Do not delete data files. Do not rewrite `data/days/*.json` in bulk without a backup and a dry run first.

## Quality rules
- New fields in the data are optional. Old days without them must still render.
- Every `fetch` needs error handling. If data is missing, show nothing or a plain message, never a broken page.
- When `app.js` or `style.css` changes, bump the `?v=` number in `index.html` so browsers get the new file.
- Accessibility: real `<button>` and `<a>` elements, alt text on images, text contrast of at least 4.5 to 1, everything usable with the keyboard.
- Keep pages fast: lazy-load images, keep each day file small, no huge libraries.
- Make small changes. Do not rewrite working code to be tidy.

## Check before saying "done"
- Run `bash scripts/check.sh` from the `this-day-in-baseball` folder. One command checks JavaScript, Python, HTML and CSS. Fix every error it reports. Warnings can stay, but mention them.
- `python3 scripts/extras.py --selftest` when you touched career or newspaper code
- Test the page in a browser or jsdom with an old day, a new day and a day with missing data
- Say plainly which of these you ran and which you could not
- `app.js` and `more.js` share some function names (index.html loads `more.js` first). If you add a new shared name, add it to the matching list in `eslint.config.mjs`.
- Never loosen a check's settings just to make it pass. Tell Mike first.

## Data rules
- Retrosheet: the credit line must stay visible: "The information used here was obtained free of charge from and is copyrighted by Retrosheet."
- Credit Lahman/SABR, Chadwick Bureau, Library of Congress, Wikimedia and Wikipedia where used.
- Be polite to outside sites: cache results, pace requests, never hammer an API.
- MLB data (Stats API, Baseball Savant) allows only individual, non-commercial, non-bulk use. Keep it light and cached.
- Do not copy data from sites whose terms bar it (Baseball-Reference, FanGraphs). Link to them instead.
- Newspapers from the Library of Congress are link-out only.

## Video rules
- YouTube's "embeddable" flag is not reliable here. MLB and club videos fail with error 150 in the real player.
- Only embed a video that passes the real-browser test saved in `data/video_playable.json`. Everything else keeps the thumbnail that opens YouTube.
- Never put a referrer policy on the page that strips the referrer.
