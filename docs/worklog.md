# Work log and plan

What is done, what is next, and what is still open. Updated as the work moves, so a session
can be picked up without re-reading the whole history.

## Phases

| Phase | State |
| --- | --- |
| 1. Config flow, field model, diary storage | done |
| 2. Coordinator, weather sources, ET and water balance, entities | done |
| 3. Knowledge base, rules, forecast skill, adaptation, services | done |
| 4. Panel and local preview | in progress, being refined against screenshots |
| 5. Diagnostics, README, first beta on the user's instance | not started |

## Algorithm, answered on 6 September

- **One long watering, not several short ones.** The engine waters when the root zone has
  dried to the readily available limit and then refills it completely. That is what grows
  deep roots; a little every day keeps them at the surface.
- **Split only when the soil cannot take it.** A refill deeper than about an hour of
  infiltration is divided into runs with a 45 minute soak, ending at sunrise. Sand takes
  20 mm in one run, loam 12, clay 6, so the number of runs follows the soil.
- **The season sets the depth, not the rule.** The deficit is larger in July than in
  October, so the same rule gives a deeper, less frequent watering in summer and a shallow,
  rare one in autumn. Dormant lawns are left alone unless a long drought threatens the
  crowns.
- **Overseeding waters twice over.** The established turf keeps its deep dawn cycle; the
  seed gets short waterings at 11:00, 14:00 and 17:00 for a fortnight. A lawn sown from bare
  soil gets only the light regime.
- **Syringing is suggested**, and only for what it is: 1.5 mm at one in the afternoon on a
  day of heat stress or a forecast above 32 °C, to cool the canopy. It is not counted as
  irrigation in the balance.

## What a real lawn taught the engine, 6 September

Sod laid in June that nearly died, revived by daily watering. Replaying the station's real
weather through the engine found three ways it would have got this lawn wrong, all fixed:

1. It assumed mature roots. This lawn has about 13 cm, holding 20 mm rather than 45, so it
   needs watering twice as often. Rooting depth now grows with the lawn.
2. It asked for half the reserve before watering. A lawn in its first year, in a heat wave,
   or rated poorly now gives up only a third.
3. It believed a sheltered station. The pyranometer reads 53 % of clear sky and the
   anemometer 0.4 m/s; together they understated water use by a quarter. Both are now
   checked against what the temperature range implies, with FAO-56's defaults as the
   fallback.

`make replay STATS=stats.json` runs any lawn's real history through the engine and reports
how dry it would have let the grass get. That is the test that matters before this is let
near somebody's lawn.

## The duplication that caused most of the bugs, removed 6 September

The preview computed with the engine but assembled the engine's input itself, so the lawn's
age, its grass, its shade and its forecast existed twice. Every one of those copies was
wrong at some point, and each showed up as a wrong answer on screen: aeration proposed on
three-month-old turf, a starter feed where the autumn feed belonged, leaf clearing on a
garden with no trees, a different forecast for two lawns twenty metres apart.

`engine/assess.py` now holds the whole judgement — balance, season, disease, plan, agenda,
advice — and both the coordinator and the preview call it. The coordinator does only what
Home Assistant alone can do: read the sensors, publish the result. `frontend/merge.js` does
the same for the panel's event merging, which the tests had also been re-implementing.

## Open

- [ ] Confirm on the next screenshots: the watering times, the phone layout of the glance,
      and the header.
- [ ] The overview looks two months ahead (`NEXT_ACTIONS_HORIZON_DAYS`). If that proves
      short in winter, when nothing falls due for weeks, it is one constant.
- [ ] Phase 5: diagnostics, the README for users, first install on the real instance.

## Round of 6 September, from the screenshots

| Reported | State |
| --- | --- |
| Overview completely empty | fixed: a name was out of scope in the lawn badge |
| At a glance columns not aligned | fixed: the strip is a table, columns measured once |
| Lawn badge behind the name on phones | fixed: the phone rules were being outranked |
| Percentage misplaced on phones | fixed with the same rules |
| Accordion in the month plan | fixed: rows with a chevron, reasons as chips |
| "Why" as text in day, week, month | fixed: a chevron aligned with the title |
| Show and hide the numbers | fixed: the charts are always visible |
| Palette confusing jobs with lawns | fixed: two palettes, lawns are lettered circles |
| Charts hard to read | fixed: water in the root zone, and what moved it |
| Charts stop at today | fixed: past and future around today, window per view |
| Next actions need a calendar date | fixed: a tear-off date block |
| Same job repeated per lawn | fixed: merged, with an "apply to" footer |
| Mowing suggested at 10:00 | fixed: the afternoon, or the evening when hot |
| No watering suggestion visible | data was right; the preview server was serving a
  snapshot built at startup. It now rebuilds per request. |
| Filtering a lawn still showed every watering row | fixed: the filter reaches the overview |
| Header untidy | fixed: arrows, date and Today as one control |
| Watering row too wordy | fixed: times and millimetres only; the reasoning stays in the
  event's chevron |
| Watering listed lawns with nothing to do | fixed: the section only lists lawns with a
  cycle, and disappears when none has one |
| No irrigation bars in the charts | fixed: the sample weather was too wet to ever irrigate,
  and tonight's planned cycle was dropped when past and future were joined |
| Meter shorter on the lawn with alert chips (phone) | fixed: the chips have their own row |
| "Seen: bare spots" badged as done | fixed: ratings and issues are observations, badged
  and styled as such |
| Every future feed prescribed as Pro Start | fixed: the plan now ages the lawn as it walks
  the months ahead, so a March feed a year out is judged on a lawn a year older. October and
  November 2026 are Autumn K; March 2027 is the starter |
| "Irrigate 3 mm" says nothing | fixed: the clock leads the action row, in the reader's own
  size, and the millimetres follow |
| Three light waterings shown as 11:00-17:00 | fixed: the seedbed line names its hours,
  11:00 - 14:00 - 17:00, and is one line on every day including the one already timed |
| A day number on a month-long job | fixed: such a row is dated by its month alone |
| Next actions reaching into next spring | fixed: "next" stops at two months; the rest is in
  the month view |
| Eleven sensors, none of them the one an automation wants | added `sensor.<lawn>_activity`:
  one enum saying what the lawn is busy with and whether a machine or a person is doing it,
  with the detail in attributes. A machine's run carries the time it ends, so a valve is held
  open exactly as long as that zone's cycle asks; a manual job stands until the diary says it
  was done. Every state names the lawn and the entity to act on under the same two keys, so
  one automation template covers watering, cutting and everything after them |
| Zones watering at the same minute | the dawn cycles chained across lawns; the seedbed's
  passes did not, so three lawns sown together would all have opened at eleven. Both halves
  queue now, in Home Assistant and in the preview, which had been assessing each lawn in
  isolation and so showed them colliding whatever the coordinator did |
| Glance columns moving as the date changed | the table was laid out from its contents, so a
  day with no dry spell to report, or a lawn with no watering time, moved every column on the
  strip. It is `table-layout: fixed` now, measured from the header alone, and a check keeps
  the header a cell per column |
| Glance above the week and the month | removed. It is about one day, so it belongs on the
  overview and the day |
| Old meter reappearing past the projection | for a date the balance cannot reach the row fell
  back to the bar, filled from today's deficit, which is today's reading under somebody else's
  date. It is an empty greyed frame now, so the rows still line up |
| Personal data in the repository | the real garden, the real weather and the station's entity
  ids are gone. `scripts/local/` is git-ignored and the preview reads it in preference, so a
  real setup can be tried without ever being committed. What ships is a made-up garden under a
  generated summer, and the docs no longer name a place or a person |
| Only proposed work could be recorded | a cut made on a whim, a treatment after a bad week
  and watering by hand had nowhere to go, and those are the entries the engine most needs
  because they are the ones it did not predict. Any kind can be recorded now, for one lawn or
  all of them. A feed carries the month's product and dose when the plan has one, since the
  nitrogen budget is summed from those grams |
| Seven booleans left beside the one sensor that replaced them | removed. They answered seven
  questions an automation does not ask; the one it does ask is the activity sensor. What they
  carried was kept: the whole irrigation plan moved onto the irrigation sensor, the disease
  models onto the season sensor, and any standing warning onto the activity sensor's `alerts`,
  so one entity says both what to do and what is wrong |
| Ratings pushed right, issues left | they shared the summary row's chip class, which carries a
  `margin-left: auto` so the chips sit after the lawn's name. In a dialog they are the answer
  to the question above them and start where it starts |
| No hour on the activity shown first | it was hidden for watering, which is the default, so
  nobody found it. The hour is on everything now, watering included |
| Seed mix as free text | a mix is a product name, so it cannot be a closed list, but nobody
  should type "perennial ryegrass" from memory. It is a datalist of the grasses the
  integration already names, prefilled with the lawn's own, and anything else can still be
  typed |
| A job could only be recorded as happening now | the hour is a field, starting at now, so the
  cut made at five can be recorded in the evening. It also decides which day's page the entry
  lands on, which matters either side of midnight |
| Done stopped to ask through a browser prompt | a grey box on a phone, and the wrong question:
  the row already says what was asked for, so Done means "that happened". A figure that came
  out differently is corrected in Tracking, which has a field for it |
| Tracking felt empty and unclear | it had become three headings and two buttons: it said what
  you may do and never what was already true, so there was no telling whether pressing
  anything was needed. Each section now states where every lawn stands first — rated or not,
  issues on record, what was logged today — and the button follows |
| Dialog opening halfway down and cut off | it sat inside the scrolling column, so it was laid
  out against the whole scroll height rather than the window. Dialogs are handed to the panel
  and mounted in a layer of their own |
| Recording a job asked for nothing but its name | a cut now asks its height, a feed its
  product and rate, a sowing its mix and rate. A feed goes through the same builder as the
  service, so the grams the yearly budget is summed from are worked out in one place |
| Tracking laid out as five sections | three now, in the order the work happens: today's work,
  how the lawn is, work you did. The last is a button and a dialog rather than two control
  rows per lawn, which on three lawns was six rows for the rarest thing anyone comes to do |
| Tracking wanted a tab of its own | added, between Overview and Day: the rating, the issues,
  and today's outstanding work with its Done buttons. The rating left the overview and the day
  view rather than being shown in three places, and the history section went the same way: the
  week and the month already show it, with the plan around it |
| "Today's work" wrapping every word onto its own line | the action row is a two-column grid
  reserving 58px for the tear-off date, and a row without one put its whole body in that
  column. `.action--static` now collapses it, and a check catches a dateless row that forgets
  to say so |
| Legend entries inconsistent | they were reusing headings, so "Soil water" sat beside
  "watering point" and a caption read as two. They have a table of their own now, lower case
  and a word or two each, with a check that keeps them that way |
| No panel way to log watering on a day nothing was planned | the last thing the removed
  number entity could do. The Tracking tab takes the day's total in minutes per lawn,
  prefilled with what is already recorded, so a wrong figure can always be corrected |
| Audit of what the entities did and the panel did not | three real losses. Confirming a feed
  wrote no `n_g_m2`, and that number is the whole yearly nitrogen budget, so a lawn fed from
  the panel counted as never fed. Scarifying and top dressing were both written as
  "aeration", so `days_since_scarifying` stayed at never. Preparing an overseeding was
  written as a sowing, which would have started the germination regime over ground with no
  seed in it. All three fixed |
| "thin" unreportable | the plan read it in three places and it was not on the list of what a
  person can report, so those branches could never fire. Added, along with a test that every
  issue offered is one the engine reads |
| No way to rate the lawn once the select was removed | the rating is the one thing no sensor
  can answer and the adaptation loop runs on it, so removing the entity without putting it in
  the panel left the engine unable to learn. Four answers per lawn, in the overview and on
  today, marked with what was already given. The stale hint pointing at the deleted buttons
  went with it |
| Date control changing width with the weekday | it had no styling of its own at all, only
  two phone overrides, so it was sized by whatever date it held: "Fri 4 Sep" one day and
  "Wednesday 16 September" the next, which moves the arrows out from under the finger
  pressing them. The label now has a fixed 14rem, centred and clipped, and takes the whole
  bar on a phone |
| Glance frozen on today while the calendar moved | it read the live state whatever date was
  on screen, so the dry spell and the next action described a different day from everything
  under them. Every figure now comes from the day being looked at: the water from that day's
  balance, the next job from that day's calendar, the dry spell counted back to it, the heat
  chip from its own temperature. Past what the diary and the projection reach it says so |
| "Why does Water the seed ask for a duration?" | it should not, and confirming it would have
  been worse than useless: the write went to `log_irrigation`, whose total feeds the balance,
  so a tap would have told the engine the root zone was full and cancelled the dawn cycle.
  Seedbed passes and syringing are now a plain tap recorded as work done, the diary keeps
  them in their own column, and a valve run is filed by the cycle it served rather than all
  runs counting as irrigation |
| "Soil water is still not the forecasted one" | right: the meter showed this instant, which
  on a lawn watered at dawn always reads full and says nothing. It is now the projected line
  over the days the balance can speak for, with the watering mark drawn under it, a tick on
  every day the plan waters, dashes past the forecast, and the week's low point beside the
  reading for now |
| "No proper at a glance, and no forecast for future entries" | the sky was nowhere in the
  panel. The week's weather is now drawn once above the lawns, since the property shares one,
  and marks where the forecast ends and the season's own rate takes over. Each day in the day
  view says what its weather was and whether it was measured, forecast or expected. The
  glance's columns are named once in a header instead of "Soil water" being printed on every
  row |
| Done offered on future work | fixed: a day that has not happened cannot be confirmed, and
  a month-long routine is not a job you tick off. Yesterday still gets a button, because a
  job done and not written down is what the diary is for |
| Confirmations on the device page | removed the number, the select and the five buttons.
  A confirmation is made about a job somebody is looking at, so it is now a Done button on
  the line that asked for it, in the overview and the day view, writing through one
  websocket command. The services stay for automations |
| "Soil water shows the same data for future dates" | two causes, both real. The seedbed's
  light waterings were in the agenda and missing from the projection, so the chart showed a
  lawn getting nothing on days it was being watered six millimetres; they are drawn now, and
  still not credited to the root zone, which is the point of them. And the chart made no
  distinction between the forecast week and the week after it, which is the season's rate
  with no rain assumed; that boundary is now marked |
| "Next irrigation on the 12th, in this heat?" | the preview was rolling dice for the
  forecast rain — `choice([0, 0, 0, 3, 8])` — and 8 mm of invented rain is exactly what
  pushes a watering out. The record ends in a dry spell at 34 °C, and the week ahead now
  carries it forward instead. The next cycle is two days out, then every other day |
| The second half of September empty | the agenda stopped at seven days, so every calendar
  went blank from mid-month to the first of the next. The cut is on a cadence and needs no
  forecast: it is now laid out for twenty-eight days. The water balance runs a fortnight |
| Still no mowing in September | the previous round left it out for a real reason that was
  itself wrong: the mower was held for three weeks after any sowing. Overseeding is not
  sowing. The old grass keeps growing over the seed and has to be cut, and the test
  diary shows a cut five days after the overseeding. Now only a lawn sown on bare soil holds
  the mower; an overseeded one keeps the cut and hands it to the push mower for a fortnight |
| "Should I really not mow for the next months?" | fixed: mowing was in the plan only as its
  three milestones. Every growing month now carries a height and an interval, and a lawn with
  a robot gets the robot's own cadence, which is daily in the flushes |
| No herbicide, ever, on a lawn laid this year | fixed twice. The ageing bug was one half;
  the other was the question itself. The wait now runs from the seed, six weeks, and sod
  waits only to root, so "diserbo foglia larga" is back in October 2026 and May 2027, which
  is what the professional calendar says |

## Done in phase 4, after the first screenshots

- Panel rebuilt as a lawn calendar: overview, day, week, month, with date navigation.
- All lawns on one calendar; a lawn is a lettered circle, a job is a coloured pill.
- One job on several lawns is one line, with the lawns as an "apply to" footer.
- Reasons behind a chevron, as chips, in the middle of a card.
- Own icon set, so nothing depends on Home Assistant's icon font.
- Two charts: water in the root zone, and what moved it, past and future around today.
- Mowing proposed for the afternoon, not the dew.
- At a glance is a table, so columns line up; a separate grid layout on phones.
- Watering panel with the dawn cycle's times on the overview and the day.

## Tests that guard the panel

- `tests/frontend/test_views.mjs` renders every view and drives the whole panel in all four
  modes through a DOM shim, and checks the phone layout's CSS cannot be outranked.
- `tests/frontend/test_i18n.mjs` checks every engine code has a sentence in both languages.
- Both run in `make check`.
