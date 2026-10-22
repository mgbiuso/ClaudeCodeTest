# Setup: API keys and permissions

You need three free (or nearly free) keys and one GitHub permission. **Never paste a key into chat or commit it.** Keys go in `this-day-in-baseball/.env`, which is git-ignored.

## 1. YouTube Data API key (for video)

1. Go to **console.cloud.google.com** and sign in with a Google account.
2. Click the **project picker** at the top, choose **New Project**, name it `this-day-in-baseball`, and click **Create**.
3. Open **APIs & Services**, then **Library**. Search for **YouTube Data API v3** and click **Enable**.
4. Open **APIs & Services**, then **Credentials**. Click **Create credentials**, then **API key**, and copy the key.
5. Click the key's name. Under **Application restrictions**, choose **None**. The other options do not fit:
   - *Websites* only works for calls made from a visitor's browser. Our scripts send no referrer, so every request would fail.
   - *IP addresses* would break the daily GitHub build, because GitHub's machines use changing IPs.
   - *Android apps* and *iOS apps* are for mobile apps.
6. On the same page, under **API restrictions**, choose **Restrict key** and select only **YouTube Data API v3**. This is the real protection: a leaked key then cannot be used for anything else on your account.
7. **Do not turn on billing.** The free quota is about 10,000 units a day, and a search costs 100 units. You can check it under the API's **Quotas** tab.

## 2. Flickr API key (for extra photos)

1. Go to **flickr.com/services/apps/create** and sign in.
2. Choose **Apply for a non-commercial key** and enter a name and a short description. A free site with no ads and no sales is generally non-commercial, but read Flickr's terms yourself. Ads or sales would need a commercial key.
3. Copy the **Key**. You do not need the Secret.

## 3. Anthropic API key (for headlines)

1. Go to **console.anthropic.com** and sign in.
2. Under **Billing**, add a small amount of credit and set a monthly spending limit. About $10 is plenty to start.
3. Open **API Keys**, create a key, and copy it. It is shown only once, so copy the whole thing with the copy button.

## 4. GitHub permission (to turn on the daily build)

Run this in the **Terminal app** (the in-session `!` mode is not fully interactive):

```
gh auth refresh -h github.com -s workflow
```

Press Enter to open the browser, then enter the one-time code and approve. Afterward, move `this-day-in-baseball/workflow/build.yml` to `.github/workflows/build.yml`.

## 5. No setup needed

Library of Congress photos and Openverse photos need no key.

## Where the keys go

Open `/Users/mgbiuso/ClaudeCodeTest/this-day-in-baseball/.env` (it already exists). On a Mac:

```
open -e /Users/mgbiuso/ClaudeCodeTest/this-day-in-baseball/.env
```

Or in Finder press **Cmd+Shift+G**, paste the folder path, and press **Cmd+Shift+.** to show hidden files. Paste each key after its `=` sign, with no quotes or spaces, then save as plain text:

```
ANTHROPIC_API_KEY=
YOUTUBE_API_KEY=
FLICKR_API_KEY=
```

`.env` is listed in `.gitignore`, so it never reaches GitHub. For the daily GitHub build, also add the same three names as repository secrets: **Settings**, then **Secrets and variables**, then **Actions**.

## 6. New data (career lines and old newspapers): no keys needed

Career lines use the free Lahman Baseball Database. Old newspaper pages use the free Library of Congress collection. Neither needs a key.

On your own computer (Terminal), from the `this-day-in-baseball` folder:

1. Download the Lahman files once: `python3 scripts/extras.py --fetch-lahman`
   (If that fails, download the CSV version from sabr.org/lahman-database, unzip it, and run `python3 scripts/extras.py --fetch-lahman --source ~/Downloads/the-folder-name`.)
2. Check that everything works: `python3 scripts/extras.py --check`
3. Add career lines to the days you already built: `python3 scripts/enrich_days.py`
4. Add old newspaper pages (slow, about 30 seconds a day, and saved so it only happens once): `python3 scripts/enrich_days.py --papers`

## 7. Turning on the daily build on GitHub

1. Open your repo on github.com and click the **Settings** tab (top row of the page, far right).
2. In the left sidebar click **Secrets and variables**, then **Actions**.
3. On the **Secrets** tab click **New repository secret**. Add one called `ANTHROPIC_API_KEY` and one called `YOUTUBE_API_KEY` (paste each key as the value). Without them the daily build still runs, but skips headlines, photo checks and videos.
4. Click the **Variables** tab, then **New repository variable**. Name it `SITE_URL` and set the value to your site address (for example `https://yourname.github.io/ClaudeCodeTest/this-day-in-baseball/`). This fixes the links in the RSS file, which say `localhost` until you do.
5. GitHub only shows and runs this daily build from your default branch (usually `main`), so nothing happens until this work is merged into `main`. After that, you can test it by hand: click the **Actions** tab, click **Build This Day in Baseball** in the left list, then click **Run workflow**.

Note: the Flickr key in step 2 above and the Openverse photos in step 5 are not used by any script right now, so you can skip them.
