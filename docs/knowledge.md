# The knowledge base and where it comes from

Every number the engine uses is listed here with its source. When a constant changes, the
line that justifies it changes with it. The programme is written for a cool-season home lawn
in a humid temperate climate first, and generalised by hemisphere and grass class.

## Evapotranspiration and water balance — `engine/et.py`, `engine/water.py`

- Reference ET₀ by FAO-56 Penman-Monteith and Hargreaves-Samani, verified against the paper's
  worked examples 2, 8, 9, 14, 15, 18 and 20. Allen, Pereira, Raes, Smith, *Crop
  evapotranspiration — Guidelines for computing crop water requirements*, FAO Irrigation and
  Drainage Paper 56, 1998.
- Total available water per metre of soil by texture: FAO-56 table 19, midpoints.
- Allowed depletion fraction 0.50 for turf: FAO-56 table 22. It drops to 0.30 for a lawn in
  its first year, a lawn under heat stress, or one whose last rating was fair or poor —
  FAO-56 lowers the fraction as demand rises (eq. 84), and each of these lawns has less
  reserve to give. In practice it is the difference between watering three-month-old sod
  every three days and every two.
- Cool-season turf ET averages 5.35 to 7.79 mm/day in summer, and acceptable quality is kept
  at 59 to 74 % of ET replacement: Braun et al., *Review of cool-season turfgrass water use
  and requirements: I*, Crop Science, 2022 (doi 10.1002/csc2.20791). This bounds the
  irrigation adaptation factor to 0.65 to 1.3.
- Turf crop coefficients around 0.8 for cool-season and 0.6 for warm-season turf, with a
  seasonal spread: Irrigation Association / ASABE landscape practice, and the Braun review.

## Season, soil temperature, degree days — `engine/phenology.py`, `knowledge/programme.py`

- Soil temperature at 5 cm approximated by the five-day mean of daily mean air temperature:
  extension practice, e.g. NOAA and university extension guidance on estimating planting
  soil temperature from rolling air means.
- Crabgrass pre-emergent timing: soil 10 to 13 °C sustained, or 250 to 500 GDD (base 32 °F)
  from 1 January, which is 140 to 280 GDD at base 0 °C: Michigan State University GDD
  Tracker; University of Wisconsin crabgrass pre-emergence timer; Fidanza, Dernoeden and
  Zhang, degree days for predicting smooth crabgrass emergence, Crop Science 1996 (major
  emergence 140 to 230 DD).
- Tall fescue and cool-season seeding: soil 12 to 22 °C, and at least 45 days before the
  first frost: NC State TurfFiles, *Time for fall seeding of tall fescue*; K-State turf
  extension.
- Selective herbicides are withheld from young grass, and the wait runs from the seed, not
  from the lawn's birthday. Product labels ask for the new grass to have been mowed three
  times, which in the autumn flush is about six weeks from sowing; sod is mature grass and
  waits only the two to three weeks it takes to root. A lawn overseeded at the start of
  September is therefore sprayable by the middle of October, which is what the professional
  calendar does. Extension guidance on weed control in newly seeded turf (Penn State,
  Purdue) and the "mowed at least three times" instruction common to 2,4-D and mecoprop
  products. Within twelve weeks of sowing the advice is to spot-treat rather than spray.
- Cool-season heat stress: shoot growth slows and roots stop above roughly 30 °C air and
  24 °C soil; three consecutive days over 30 °C is the engine's stress flag. Extension
  guidance on summer stress in cool-season lawns (Penn State, UMass).

## The yearly programme — `engine/plan.py`, `knowledge/programme.py`

- The cool-season month plan follows the calendar Italian professionals run on a home lawn in
  a humid temperate climate: March phosphorus starter (Pro Start), April and May
  greening feeds (Dark Green), broadleaf herbicide in May, coated potassium feeds in June and
  July (Summer K), grassy-weed herbicide in July, nothing in August, overseeding in
  September, broadleaf herbicide and potassium feed in October, potassium feed in November.
  Each month's operations carry the research codes that support them (two growth peaks,
  potassium before heat, coated nitrogen without a disease flush, autumn broadleaf control
  when translocation to roots is strongest, crabgrass post-emergent while plants are young,
  45 days before frost for seeding) and the data that tailored them for this lawn.
- Operations are decided once a month and kept in the diary; daily rules decide only their
  timing inside the month. A missed feed is carried into the following month once.

## Fertilization — `knowledge/programme.py`, `knowledge/fertilizers.py`

- Cool-season lawn: two growth peaks, spring and early autumn; 4 to 5 applications a year,
  nitrogen weighted to autumn, potassium before summer; around 25 g/m² of product per pass
  and moderation with nitrogen to avoid succulent tissue prone to disease and frost. ICL
  Italia, *Programmi di concimazione annuale per prati in microterme* and *Guida alla
  concimazione del prato in autunno*; Bestprato and Greenterest programmes for Italian home
  lawns. The engine's totals: 15 to 25 g N/m²/year cool-season, 20 to 30 warm-season.
- No nitrogen in heat stress or drought: above 30 °C fresh nitrogen is not taken up and
  feeds brown patch and Pythium. Extension guidance (UMass, Penn State) and the ICL notes.
- Bottos compositions, from the manufacturer's data sheets as reproduced by Italian
  resellers: Pro Start 13-24-10 (25 % slow-release N, 30 to 35 g/m²), Slow Green 22-5-10
  +2MgO (35 % slow, up to 60 days, 25 to 30 g/m²), Slow K 13-5-20 +2MgO (43 % slow, 30 to
  35 g/m²), Autumn K 21-0-25, Dark Green 11-0-0 +3MgO +4.5Fe (greening and anti-moss, 25 to
  35 g/m²), Summer K 10-0-30 (nitrogen fully coated over 90 days, potassium sulphate, 30 to
  40 g/m²). The programme uses them by role (starter, greening, growth, stress, autumn),
  never by name.

## Disease — `engine/disease.py`

- Dollar spot: Smith-Kerns model, logit = −11.4041 + 0.0894·RH₅ + 0.1932·T₅ on five-day
  means; act at 20 % probability. Smith, Kerns et al., 2018; University of Wisconsin
  Turfgrass Diagnostic Lab model page; Agronomy Journal 2025 follow-up on additional uses.
- Brown patch: Fidanza, Dernoeden and Grybauskas E2 index, E = −21.5 + 0.15·RH + 1.4·Tmin
  − 0.033·Tmin², warning at E ≥ 6; 85 % accuracy over three seasons. Penn State turf
  pathology; UC IPM brown patch guidelines for the environmental thresholds (night above
  20 °C, RH above 95 % or 10 hours of leaf wetness).

## Mowing — `engine/rules.py`, `engine/plan.py`

- Never remove more than a third of the leaf in one cut; raise the height in summer; the
  last autumn cut lower. Cutting height ranges per species from Italian and US extension
  tables (tall fescue 60 to 90 mm, ryegrass 40 to 70, bluegrass 50 to 80, bermuda 25 to 50).
- The species range is clamped into what the mower can be set to, when the lawn says what
  that is. A robot deck that stops at 60 mm cannot make the 75 the species asks for, and
  advice naming a setting that is not on the machine is advice nobody can follow: where the
  two ranges overlap that is the height, where they do not it is the nearest the deck reaches.
- The third rule is about height, so the interval follows from it rather than from a table of
  days. Cutting back to H having let the grass reach h removes h - H, which may not exceed a
  third of h; the grass may therefore reach 1.5 H, and the growth allowed between two cuts is
  half the height the lawn is kept at. A lawn at 60 mm comes round a fifth sooner than the
  same lawn at 75. What the season sets is the growth rate — 3.8 mm a day at green-up, 6.2 in
  each flush, 4.2 through the heat, 3.1 in late autumn — calibrated so the intervals a home
  lawn is usually given (10, 6, 9, 6, 12 days) come back at 75 mm, the middle of a
  cool-season range. Bounded to 3 to 21 days, since no home lawn is cut every other day.
- Overseeding is not sowing, and the mower is the place the difference shows. A lawn sown on
  bare soil has nothing to cut for about three weeks. A lawn overseeded still carries its own
  grass over the seed, and that grass has to be cut on time: left standing it shades the
  seedlings out in the fortnight they most need light. The blade is not the danger, since it
  passes well above a seedling; the danger is a robot's wheels tracking the same lines every
  day, so the cut is made by hand for the two weeks the seed takes to root. Extension
  overseeding guides (Purdue, Penn State) and robot manufacturers' guidance after seeding.
- Mowing is in the plan of every growing month, not only at its milestones. Between the
  first cut of March, the raised height of May and the low last cut of November the grass
  keeps growing, and a plan that says nothing for those months reads as though it had
  stopped. Each month therefore carries a height and the interval that height implies.
- A robot is a different regime and gets a different line. It takes a few millimetres at a
  time, so it is not held to the third rule but to keeping up with growth: the manufacturers
  schedule it out every day in the spring and autumn flushes, every second day through the
  heat, every third at green-up and every fourth in late autumn. Robot mower manufacturers'
  scheduling guidance and extension notes on mulching mowers. Hosekeeper knows a lawn has one
  because a mower entity was given for it.
- Daily is what the machine can do, not what the lawn needs, and it is not free: a slow robot
  has the lawn occupied for hours at a time, and going over the same ground every day is the
  part of robot mowing that costs the invertebrates living in it — the wildlife guidance asks
  for fewer passes and none at night. So the cadence is a choice between the manufacturer's
  schedule and the agronomic maximum: `frequent` is the table above, `gentle` is the whole of
  the growth the third rule allows, which is what a hand mower gets, and `balanced` — the
  default — is half of it, which keeps the clippings short enough to fall into the sward and
  vanish while leaving the lawn alone between passes. At 60 mm in the autumn flush that is
  fifteen passes a month rather than thirty.
- Heat and drought put a cut off; they do not cancel one. The heat is already in the
  interval, since the summer phase grows slowly and the third rule stretches with it, so
  suppressing the cut on top of that counts the same slowdown twice. A lawn that has reached
  half again its height has to be cut whatever the weather: waiting out a fortnight above
  30 °C means taking two thirds of the leaf off at the end of it, which is the scalping the
  rule exists to prevent. Under stress the cut goes to the top of the range and the advice
  names the heat as what it is a compromise with. Extension summer-mowing guidance: raise the
  height, mow less often, mow when it is cooler -- not stop.
- A month's mowing line names the machine that cuts most of that month. Seed sown at the end
  of August holds a robot off the first week of September and no longer, and calling the whole
  month hand-mown leaves two lawns cut the same way at the same height on the same interval
  reading as two different jobs. The fortnight the robot is held off is the day's advice, which
  counts it down; the month line says the robot waits at first and stays the robot's.
- A routine is never finished by one pass: mowing once in a month does not tick the month's
  mowing off, the way a fertilization is ticked off by spreading it.

- A month's operation is satisfied by work done in the fortnight before it as well as within
  it. The plan's windows are month-sized and the boundary is arbitrary to a lawn: overseeding
  on 30 August is the September overseeding, and the first of the month does not undo it.

- A watering is decided once for the day so its depth cannot wobble with every refresh, and
  decided again when the day has materially moved: a third of the planned depth, and never
  less than three millimetres, which is about what a summer shower puts down. Rain that fell
  after the plan was made, or a forecast that filled up since, therefore takes back as much of
  the watering as it has replaced rather than all of it or none. A cycle already running is
  left alone; water that has gone on cannot be taken back.

- Seed sown into an existing lawn asks for its own feed, in the month it went down. The
  starter used to travel as a parameter of the overseeding operation, which was fine while
  the overseeding was still to do and went with it the moment it was ticked off; the next
  line in the programme is the autumn potassium feed, which is what a lawn wants before
  winter and not what a seedling wants while it is putting a root down. Phosphorus is, so
  the sowing carries a starter of its own for four weeks, unless something has already been
  spread since the seed went down. Extension overseeding guides: a starter at sowing, or with
  the first cut of the new grass.

## Establishment — `knowledge/programme.py`

- Overseeding an established lawn is two regimes at once: the turf around the seed still has
  roots at depth and keeps its deep dawn cycle, while the seed needs the top centimetre damp.
  Hosekeeper therefore adds short waterings of about 2 mm at 11:00, 14:00 and 17:00 for the
  fortnight the seed takes to come up, and stops them before evening so the leaf dries before
  dark. A lawn sown from bare soil has no established turf to water deeply, and gets the
  light regime alone.
- Rooting depth grows with the lawn and is not the depth the species reaches when mature.
  Sod is laid with two or three centimetres of soil and knits downward over a season; seed
  starts shallower still. The engine ramps the effective depth from 6 cm at laying, or 3 cm
  at sowing, to the species depth over 300 days for sod and 400 for seed, in the spirit of
  the growing root zone of FAO-56 chapter 8. It matters more than it looks: a lawn three
  months old holds about half the water a mature one does, so it needs watering twice as
  often, and a schedule built on the mature depth starves it.
- Sod: keep moist, roots take in two to three weeks, first mow once it cannot be lifted.
- Seed: keep the surface moist, germination in 7 to 14 days for fescue and ryegrass, a lawn
  in about two months; starter fertilizer high in phosphorus at seeding. NC State and
  Purdue extension establishment guides; Bottos Pro Start data sheet.

## Timing in the day — `engine/schedule.py`

- One deep watering rather than a little every day: the root zone is refilled when it has
  dried to the readily available limit, which is what sends roots down. Frequent light
  watering keeps them at the surface. Braun et al. review and extension guidance.
- One valve at a time. A domestic controller opens one zone at a time, so the lawns share a
  queue rather than a clock: the dawn cycles stack backwards from sunrise, each lawn ending
  where the next begins, and the seedbed's passes stack forwards from their hour. Three lawns
  all starting at eleven means the second and third get whatever pressure is left.
- Cycle and soak: a lawn takes water only as fast as the soil lets it in, so a refill deeper
  than about an hour of infiltration is split into runs with a soak between them — the same
  water, the same morning, without runoff. Infiltration classes from FAO-56 chapter 7 and the
  USDA soil classes: roughly 30 mm/h on sand, 12 on loam, 5 on clay, with a single run held
  to 20, 12 and 6 mm respectively. The number of runs therefore follows the soil, and the
  depth follows the season, because the deficit does.
- The hour matters, and the order is not close. **Before dawn, finishing at sunrise** is
  best on both counts that matter: evaporation and wind drift are at their lowest, so more
  of the water reaches the soil, and the leaf dries within an hour of the sun coming up, so
  the wetness the disease models count barely accumulates. **Evening and night are the
  worst**: the water lands well, but the leaf then stays wet for ten to fourteen hours,
  which is precisely the condition brown patch and dollar spot need. **Midday is the least
  efficient**, losing a fifth or more of the water to evaporation and wind, though the old
  story about droplets scorching the leaf is not true. So Hosekeeper waters before dawn,
  never in the evening, and uses midday only for syringing — 1 to 2 mm to cool the canopy
  on a day of heat stress, which is a different job and is not counted in the balance.
  Extension irrigation guidance (Penn State, UC IPM), the Braun review, and the leaf-wetness
  term in the Smith-Kerns and Fidanza models.
- Mow dry grass, in the afternoon rather than the morning: dew sits on the leaf until mid
  morning and later in autumn, and a wet cut tears rather than slices, smears the clippings
  and carries disease across the lawn. The calendar proposes 16:00 to 18:00, and 18:00 to
  20:00 on a day of heat stress; the window in which a robot may run at all is 10:30 to
  20:00, minus the middle of the day when the lawn is stressed. Extension mowing guidance.
- Disease alerts fire on the second consecutive day over threshold, as the models are
  built on multi-day means and a one-day spike is noise.

## Shade and trees — `field.py`, `engine/rules.py`, `engine/plan.py`

- Turf under trees or structures uses roughly 60 to 70 % of the water of turf in the open
  (Braun review; Feldhake, Danielson and Butler on shade and turf ET); the crop coefficient
  is reduced by 35 % of the shaded share. Tree roots share the root zone and take some of
  that saving back: 15 % of the tree-covered share is added.
- Shade thins cool-season turf and favours moss and foliar disease: mowing at the top of the
  range, a shade-tolerant fine-fescue mix for overseeding, an optional late-winter moss pass,
  and a lower alert threshold for the planned preventive treatment. Extension guidance on
  lawns in shade (Purdue, UMass).
- Leaves left on the lawn smother it and hold moisture; deciduous trees add a leaf-clearing
  operation in October and November.

## What only a person can report — `const.py`, `engine/plan.py`, `engine/rules.py`

- The rating (excellent, good, fair, poor) is the trend the adaptation loop runs on, and it
  is also what lowers the allowed depletion: a lawn rated fair or poor is watered at 0.30
  rather than 0.50, on FAO-56's principle that a crop under stress has less reserve to give.
- The issues are the diagnosis behind the rating, and each changes a decision rather than
  merely describing the lawn. Weeds make the herbicide pass compulsory instead of optional;
  moss the same for the moss pass, and with thatch it makes the autumn soil work compulsory;
  bare or thin turf makes the overseeding compulsory; fungus or brown patches make the
  preventive treatment compulsory and hold the nitrogen back, since fresh nitrogen feeds
  brown patch and Pythium. Pests are recorded for the diary alone: no rule acts on them, and
  a test keeps that list honest so an unused question is never asked of the reader.

## Which source wins — `coordinator.py`

- A station on the lawn outranks a forecast for the same place. Where a field has its own
  sensors, they are the record of what happened: humidity and wind are taken from them and
  never from the forecast, and the forecast's temperatures are used only to anticipate the
  part of the day that has not happened yet. After eight in the evening the day is the
  station's, whatever the model said. The forecast keeps the job only it can do, which is
  telling the engine about tomorrow.

## Sensors that lie — `coordinator.py`

- An anemometer in the lee of a house reads calm every day of the year. A daily mean under
  0.5 m/s is therefore treated as shelter rather than weather, and FAO-56's own default of
  2 m/s is used in its place (chapter 3, where wind data are missing or of doubtful
  quality). On a station under test, believing 0.4 m/s understated the lawn's water use by a
  fifth: 3.3 mm a day instead of 4.1, which over a hot fortnight is a watering missed.
- A pyranometer in the shade of a building, or under dust, reads low all day and every day,
  and nothing in the number says so. Measured daily radiation below 70 % of what the day's
  temperature range implies (FAO-56 eq. 50) is therefore treated as a siting problem, and
  the temperature-based estimate is used instead. One station under test read 53 % of
  clear sky through a cloudless August, which would have halved the water the engine asked
  for.

## How far ahead the week is drawn — `engine/agenda.py`

- Three horizons, because three different things are being predicted and none is knowable as
  far as the next. The weather model is read for seven days. The water balance is run on for
  another seven, drying at the season's rate with no rain assumed, which is a projection and
  not a promise but beats a blank fortnight. Work on a cadence — the cut, the seedbed — needs
  no forecast at all and is laid out for twenty-eight days, so the calendar does not go empty
  from the middle of one month to the first of the next.

## Forecast skill — `engine/climate.py`

- Own method: forecast issued the day before is stored next to the measurement; over a
  thirty-day window the rain ratio and rain hit rate (events of 2 mm or more) discount the
  forecast, and the temperature bias is reported. Neutral until five days can be compared.
