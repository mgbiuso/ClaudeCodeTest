---
name: guide
description: Build an easy-to-follow, ADHD-friendly step-by-step guide (one self-contained HTML file with tick boxes, progress bar, "Where was I?", pictures) for any project. Use when Mike asks for a guide, how-to, walkthrough or instructions for a program or process.
---

# /guide: build a step-by-step guide

Template lives in `~/ClaudeCodeTest/guide-template/` (build_guide.py, steps.starter.json, README.md). Finished example: `~/ClaudeCodeTest/field-cut/guide/`. Read the README there first for the writing rules and the steps.json field table.

Mike is new to coding: explain in plain words, no em dashes, back up before editing existing files, never commit without an explicit yes.

## Steps
1. Ask numbered questions first: what is the guide for, who reads it, which tasks in what order, does an old guide exist to update, where should the file go.
2. Copy `steps.starter.json` to `<project>/guide/steps.json`. If a guide already exists, back it up first into the project's `_backup_before_changes/`.
3. Write the steps using the README rules: one action per line, 15 words or fewer, WHERE then WHAT then WHAT YOU WILL SEE, a time on each step (under 3 minutes), buttons in **bold**, keys as [[Cmd + S]], a `stuck` list, and a friendly finish message.
4. Verify every feature named in a step really exists in the app. Drop or flag any that do not.
5. Screenshots: serve the project with `python3 -m http.server <port> --bind 127.0.0.1`, drive it in Chrome, circle the target in orange, save to `<project>/guide/images/`. Keep them small (JPG).
6. Build: `python3 ~/ClaudeCodeTest/guide-template/build_guide.py <project>/guide/steps.json <project>/guide/<name>.html`
7. Open the result and check it renders: progress bar, ticks, pictures. Say what you ran and what you could not check.
8. Offer a copy in ~/Downloads. Ask before committing. Change the `id` in steps.json when the guide changes a lot so old ticks reset.
