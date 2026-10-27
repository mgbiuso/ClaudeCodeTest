# Free data sources for This Day in Baseball

Checked October 22, 2026. Terms can change, so read each site's current terms before building on it.

## Already in the project

| Source | What we use | Terms |
| --- | --- | --- |
| Retrosheet | Game facts, debuts, feats, postseason | Free. Must show: "The information used here was obtained free of charge from and is copyrighted by Retrosheet." |
| Lahman Baseball Database (SABR) | Career stat lines | Free. Credit Lahman and SABR. Confirm the licence on the Lahman page before launch. |
| Wikipedia, Wikidata, Wikimedia Commons | Stories, people, photos | Free licences. Credit the photo author and licence. |
| Library of Congress | Old newspaper pages (link out only) | Says it knows of no copyright restrictions for most items. You check each one. |

## Best next additions

| Source | What it gives | How to get it | Terms and notes |
| --- | --- | --- | --- |
| Retrosheet Negro Leagues files (retrosheet.org/NegroLeagues/downloads.html) | 8,215 games: players, game info, team stats, batting, pitching, fielding, plays. Box scores for 4,653 games, play by play for 2,192 (Summer 2026 release) | Seven CSV files in one zip, plus a 319 MB zip with everything | Same Retrosheet credit line, shown prominently. Stats carry a `stattype` column (value, lower, upper) that marks uncertainty. Same format family as the data we already use. Best pick. |
| Chadwick Bureau Register (github.com/chadwickbureau/register) | One master list of person IDs linking Retrosheet, MLB, Baseball-Reference, FanGraphs and Wikidata | CSV files data/people-0.csv to people-f.csv | Open Data Commons Attribution licence. Credit Chadwick Bureau. Public copy lags the full one. Helps match the same person across sources. |

## Possible, with limits

| Source | What it gives | Limit |
| --- | --- | --- |
| MLB Stats API (statsapi.mlb.com, unofficial) | Schedules, scores, rosters, box scores, standings | MLB's notice at gdx.mlb.com/components/copyright.txt allows only "individual, non-commercial, non-bulk use". Keep calls few and cache them. No key needed. |
| Baseball Savant / Statcast (baseballsavant.mlb.com) | Pitch and hit tracking since 2015, CSV export | Same MLB terms. I could not find a separate terms page. Fine for a few modern feats. |
| Python `pybaseball` and `MLB-StatsAPI` | Helpers that wrap the sources above | The wrapped sites' terms still apply. They are not affiliated with MLB. |

## Link out only (do not copy data)

- SABR BioProject (sabr.org/bioproject): player biographies. Use as a "read more" link.
- Baseball-Reference and FanGraphs: best stats, but their terms limit scraping.
- Seamheads Negro Leagues Database (seamheads.com/NegroLgs): the site shows a notice "All data, copyright 2011-2023 Agate Type Research LLC" and no download or reuse terms. Use the Retrosheet Negro Leagues files above instead, or ask Seamheads for permission.

## Other sports (not baseball)

| Source | Notes |
| --- | --- |
| nflverse (NFL) | Play by play, player stats, rosters. Code is MIT. The data "belongs to its respective owners" under their terms. Files live in GitHub repositories. |
| balldontlie (NBA only) | No key needed, 7 read-only endpoints. No stated rate limit, so ask for little and cache. Its own terms page was not confirmed. |
| NHL web API (api-web.nhle.com) | Unofficial. Terms not confirmed. |

## Video

YouTube embeds of MLB and club videos fail with error 150 even when YouTube's data says "embeddable". Keep link-outs for those. Embed only videos that pass the real-browser test (data/video_playable.json). Better sources for playable old footage: National Archives, Library of Congress, Internet Archive, Wikimedia Commons. Check each item.

## Researched October 26, 2026 (tested with small samples, not built yet)

| Idea | What I found | Limits and next step |
| --- | --- | --- |
| Weather from Retrosheet | `gameinfo.csv` in the yearly zips (retrosheet.org/downloads/YYYY/YYYYcsvs.zip, 1897 to 2025, about 8 MB per year) has temperature, sky, precipitation, wind and field condition. Coverage in samples: 1925 temp 4 of 1,277 games; 1950 temp 43 of 1,244; 1975 temp 643 of 1,948; 1990 temp 1,429 of 2,120; 2015 temp 2,466 of 2,466. | Good for 1990 and later, thin before 1975. Use only where a value exists and skip the line otherwise. Same Retrosheet credit line. Our cached files do not include it yet, so a fetch step is needed. |
| Ballpark coordinates | Wikidata property P625 had coordinates for 14 of 14 test parks (Polo Grounds, Ebbets Field, Forbes Field, Fenway and others). Retrosheet `ballparks0.csv` and Lahman `Parks.csv` have names and cities but no coordinates. | Match by park name needs a hand-checked list. A name search for "Tiger Stadium" returned the LSU football stadium, so every match must be checked. About 520 Retrosheet park codes. Wikidata data is CC0. |
| Lahman tables we do not use | The full Lahman zip also has All-Star games, World Series results, Salaries (1985 on), Managers and more. Our cache keeps only 10 tables. | Download the zip again from sabr.org/lahman-database. The old GitHub address is gone. |
| Wikipedia "On this day" feed | `api.wikimedia.org/feed/v1/wikipedia/en/onthisday/events/MM/DD` returned 48 world events for Oct. 4. No key. | Text is CC BY-SA, so credit Wikipedia. Cache it, one call per day. |
| Old films and newsreels (Internet Archive) | A search for baseball movies dated 1900 to 1965 returned 110 items, including "1934 World Series", "1957 World Series Game 1", "Casey at the Bat (1927)" and Sacramento newsreels. The embed address (archive.org/embed/ID) answered with no frame block. | Licences vary per item and many say nothing. Check each item. Embed only after the real-browser test. Otherwise link out to the item page. |
| Newspaper front pages (Library of Congress) | Chronicling America pages can be shown at any size through tile.loc.gov image links, and the front page of any issue is `?sp=1`. | Mike approved on Oct. 26, 2026: papers from before 1929 may show a small page or article picture with a credit and a link to the loc.gov page. 1929 and later stay link-out only. The search API gives no rights field. |
| MLB Stats API and Statcast | See above. Statcast starts in 2015. | Skip the pybaseball and baseballr packages. They also scrape Baseball-Reference and FanGraphs, which our rules do not allow. |
