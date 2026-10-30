# Ballpark drawings: the recipe

Every park picture on the site is made the same way, so they all match.

## 1. Find a real photo (free and legal)
- Search Wikimedia Commons (commons.wikimedia.org) or the Library of Congress (loc.gov) for the park.
- Use only photos marked **Public domain** or **No known restrictions**.
- Save the photo's page link. You will need it for the credit line.

## 2. Redraw it in a free AI tool
Upload the photo and paste this prompt. Use the same words every time. Changing them changes the look.

```
Redraw this photograph as a clean architectural line drawing of the ballpark,
like an engineer's hand-inked drawing. Black ink lines on plain white paper.
Keep the real shape of the grandstands, roof, columns, walls and field exactly
as they are in the photo. Use thin, even, precise lines. Show seat rows as
simple parallel lines. No people, no crowd, no players, no text, no logos,
no color, no shading, no border. Wide 16:9 picture.
```

Save the result in `art/ballparks/source/` named by the park code, for example `NYC14.png`.

## 3. Add the matching frame
```
python3 scripts/park_art.py NYC14 art/ballparks/source/NYC14.png --note "Drawn from a 1913 photograph, Library of Congress"
```
The finished picture lands in `images/ballparks/NYC14.webp`.

## Rules
- Never ask the AI to copy a company's posters, and never ask for team logos.
- Check the drawing against the real photo. If the AI added or removed big parts, try again.
- No photo of the park exists? Leave it out for now. Do not let the AI invent one.
