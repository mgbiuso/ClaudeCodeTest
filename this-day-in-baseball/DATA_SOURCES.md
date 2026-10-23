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
