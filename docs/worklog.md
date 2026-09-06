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
lawn with no trees, a different forecast for two zones twenty metres apart.

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
| Personal data in the repository | the real lawn, the real weather and the station's entity
  ids are gone. `scripts/local/` is git-ignored and the preview reads it in preference, so a
  real setup can be tried without ever being committed. What ships is a made-up lawn under a
  generated summer, and the docs no longer name a place or a person |
| Only proposed work could be recorded | a cut made on a whim, a treatment after a bad week
  and watering by hand had nowhere to go, and those are the entries the engine most needs
  because they are the ones it did not predict. Any kind can be recorded now, for one lawn or
  all of them. A feed carries the month's product and dose when the plan has one, since the
  nitrogen budget is summed from those grams |
| One entry per lawn asked the same questions over and over | the lawn is now one entry and
  each zone of it a subentry. What belongs to the turf as a whole is answered once — where it
  is, what it sits on, what grows on it, how and when it was made, what waters it, where the
  weather is read from. What differs between one part and another is answered per zone: area,
  aspect, and which valve opens it. The engine still sees a zone as one flat thing: the two
  are merged when the `FieldConfig` is built, so a zone may override anything the lawn said |
| Cuts advised above what the mower can do | tall fescue asks for 60-90 mm and a robot deck
  often stops at 60, so the advice named a setting that is not on the machine. The lawn now
  carries the heights its mower can be set to, and the species range is clamped into it: where
  they overlap that is the advice, where they do not it is the nearest height the deck reaches.
  The month's plan is frozen so the weather cannot reshuffle it, which meant the old heights
  stayed all month beside advice that had already moved: the plan now carries a stamp of the
  setup it was built for and is rebuilt when that changes |
| Cutting cadence ignored the height it cut to | the third rule is about height: the grass may
  reach half again what it is kept at, so the growth allowed between cuts is half the height
  and a lawn at 60 mm comes round a fifth sooner than one at 75. The interval was a table of
  days per phase. The table is now the growth rate per phase, calibrated to give back the
  usual intervals at 75 mm, and the interval is worked out from the height the lawn is
  actually cut to. A robot is unchanged: it takes a few millimetres at a time and keeps up
  with growth rather than keeping the third rule. The height itself was decided in three
  places — the day's advice, the week's calendar, the month's line — and is now decided once |
| A fix that shipped and changed nothing on screen | the month's plan is stored, and what
  rebuilt it was a change in the lawn or in what had been reported about it. A change in how
  the plan is built was neither, so an upgrade left every lawn reading the plan the old code
  had written until the month turned. Loading the entry now throws the stored plan away and
  builds it again: a restart, a reload and an upgrade are the moments somebody has changed
  something, and a plan costs a few milliseconds. A version constant would have worked too,
  and would have needed remembering |
| One month, two mowing lines for the same job | the seeded zones read "mow every 5 days at
  60 mm" and the zone beside them "robot out every 5 days, deck at 60 mm" -- the same interval
  at the same height, split because the robot is held off new seed. But a fortnight of that
  does not make a hand-mown month: the line now names the machine that cuts most of the month,
  keeps the reason as tailoring, and leaves the held days to the day's advice, which counts
  them down. The two lines merge into one row across all four zones |
| Nothing told a lawn to feed the seed it had just sown | the starter feed travelled as a
  parameter of the overseeding operation and went with it when that was ticked off, and the
  separate starter rule only covers a whole new lawn. So an overseeded lawn's next feed was
  October's autumn potassium: right for turf going into winter, wrong for a seedling rooting.
  A sowing now carries its own feed for four weeks, unless something has been spread since |
| Done on the seedbed watering wrote a record nothing read | the passes are recorded as work
  rather than as irrigation, so the balance is not told the roots were filled by water that wet
  the top centimetre. Nothing read that record back, so the line went on asking for the
  watering after it had been confirmed: a button that does nothing as far as anybody can see.
  The day's kinds are on the context now, and the day's passes are one job |
| A queue for lawns that have no valves | the seedbed hours were staggered by seven minutes and
  then fourteen on a lawn watered by hand. The queue is a fact about a controller opening one
  valve at a time; a person with a hose does one zone and then the next, and the stagger read
  as though the zones needed water at different times of day. Only zones with a valve queue |
| Five millimetres of rain or nothing | a settled watering was cancelled outright by 5 mm of
  rain and untouched by 4.9. It is the month plan's test now: a material change decides again
  -- a third of the planned depth, never less than three millimetres -- and drift does not, so
  rain nobody forecast takes back exactly as much of the watering as it has replaced. Only
  while the water is still to run: a cycle under way cannot be taken back |
| Every zone watering its seedbed at eleven | one valve serves the lawn a zone at a time, and
  the queue was applied only to a plan being decided there and then. A plan already settled
  could not gain the seedbed regime at all, so seed sown after the morning's plan was made was
  never watered that day -- and every later day, drawn from the fallback hours, showed all
  three zones starting together. The settled plan now gains the passes the way it gains a
  syringing, since surface water never enters the balance the settling protects, and the
  calendar lays an undecided day out with this zone's place in the queue. Zones leave a
  minute between them: a valve takes a moment, and two runs written to the minute against each
  other read as one |
| A zone filter with nowhere to see it | choosing one zone in the overview narrowed every
  other view and the next visit too, and nothing on screen said so: a week showing one lawn's
  cuts reads as a week in which nothing else was due. A chip beside the view tabs now names
  the zone in its own colour, and pressing it goes back to all of them. It went in the header
  first, where a percentage width against an auto-sized flex parent let the name -- the only
  part of it that may shrink -- collapse to nothing, leaving a dot and a cross |
| The month's routine read as a job in the day and the week | "Mow every 5 days, at 60 mm" is
  the reason a cut is on Tuesday, not work to do on Tuesday, and in a list of the day's jobs it
  is the plan standing where the work should be. The day and the week now show dated work only;
  the overview and the month, which are about the season's shape, keep it |
| Reporting a problem changed nothing until the month turned | the month's operations are
  decided once and kept so the weather cannot reshuffle them, and the stamp that forces a
  rebuild covered the setup only. Bare turf is what makes the autumn overseeding required
  rather than optional, and puts it in the plan of a first-year lawn that would otherwise be
  left to thicken -- but reporting it did nothing for weeks. What the person reports is not
  weather: the issues of the last 30 days and the condition score are on the stamp now |
| The plan asked for a job the diary already recorded | an operation counted as done only if
  the work fell in its own calendar month, so overseeding on 30 August left September's line
  open and the plan asked for it again a week later, beside advice that had already stopped
  asking. A job done in the run-up to a month is that job, done early: the fortnight before
  the month now counts for it |
| Heat stress cancelled mowing outright | the rule returned "delay" whatever the state of the
  grass and the week's calendar dated no cut at all, so a hot fortnight -- the normal state of
  a Mediterranean summer -- meant no mowing for a fortnight, and the cut at the end of it
  would have taken two thirds of the leaf. The heat is already in the interval through the
  summer growth rate; the delay now holds only while the grass is inside its allowance, and
  past that the cut is asked for, high, with the heat named in its reasons |
| A robot out every day | which is what the machine schedules, not what the grass needs: the
  lawn is occupied for hours at a time and the same ground is gone over daily, which is the
  part of robot mowing that costs the invertebrates in it. The lawn now says how often it
  wants the robot out — the manufacturer's schedule, half the growth the third rule allows
  (the default), or the whole of it — and the plan, the calendar and the day's advice all
  read it |
| A zone added to a running lawn did nothing | Home Assistant writes the subentry and fires the
  entry's update listeners; it does not reload the entry. Zones are built at setup, so a new one
  had no diary, no coordinator and no entities until a restart, and the panel said there was no
  lawn at all. An update listener reloads the lawn, and the lawn's own reconfigure step stopped
  asking for a second reload of its own |
| Panel stuck on "loading" | the chosen zone is remembered between visits and the zone it named
  was gone. Filtering on an id nothing answers to hid every lawn there was, for the rest of the
  session. A filter that matches nothing is dropped now, and the placeholder only says "loading"
  while something is actually in flight |
| Glance cards squeezed on a phone | the row became a card but the cells kept the table's
  `width: 24 %`, which is 24 % of the grid area they land in. The card had the whole screen and
  the name inside it was a column one word across |
| No way to give a lawn its past | the diary took work and water after the fact but not
  weather, so a lawn set up in September had no summer and the adaptation loop had nothing to
  learn from. `hosekeeper.import_weather` enters one measured day through the same code that
  writes a live one — the day's own computation came out of `assess()` into `observe()` for
  it — and applied oldest first the days rebuild the balance between them |
| Text truncated on a phone | an ellipsis on a screen that is already the width of the row
  loses the lawn's name and the job it wants, and buys nothing. Narrow screens wrap instead |
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
