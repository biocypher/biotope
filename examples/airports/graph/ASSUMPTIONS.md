# Assumptions and open questions

Scientific questions the sources do not settle. Each one names what would resolve it.

Raised 2026-11-05 before the graph was built; answered the same day by the operations desk.
Every answer below is implemented in the graph and, where a consumer needs it, restated in the
`scope`, a policy or a description in `graph/build/` — this file is the development record and
does not travel with the export.

## Answered 2026-11-05

### 1. SFO / Alaska Airlines is a hub in `hubs.csv` and a focus city in the notes — **the notes win**

`airports/hubs.csv` has the row `SFO,AS`; the notes say "Focus city for Alaska Airlines." under
SFO and never call Alaska a hub there. The desk ruled: the notes were reviewed in March 2026 and
`hubs.csv` is older, so **the notes' role stands and the `SFO,AS` row is not admitted**.

Implemented as: one edge per airline-airport pair, the role taken from the notes. `SFO`/`AS` is a
`focus_city` edge. The hub row is excluded with policy `hub_row_superseded_by_notes` (1 record; evidence
`data/airports/hubs.csv` line 13). "Airlines with a hub at SFO" therefore returns United only.

### 2. Naming an airline in the notes is not an airline code — **resolve by exact name, fail on no match**

The notes name airlines in prose; `airlines.csv` gives code and name. The desk ruled: **resolve the
notes' names to airline codes by exact name, and fail the build on a name that matches no airline.
One node per airline.**

Implemented in `graph/alignment/airlines.py`: the airline table is indexed by its exact `name`, the
notes' name is looked up by exact string equality only (no normalisation, case folding or partial
match), and an unmatched name raises, so the build fails rather than inventing a node. All five
notes names equal an `airlines.csv` name exactly, so the resolution is unambiguous for this data.
This overrides the skill's default of separate source-specific nodes, on the desk's authority; the
equivalence is declared as the `airline_name` term in `standardization.py`.

### 3. Silence is not a denial — **the notes are not a complete inventory**

The desk ruled: **silence means not recorded.** No section says an airport is *not* a hub or focus
city for anyone, so the graph records only what a source asserts.

Implemented as: a hub row whose pair the notes never mention is still admitted as a `hub` edge (the
notes' silence does not deny it); only a hub row the notes *contradict* is excluded. For this data
every hub pair is restated in the notes, so the rule changes nothing now — it is there for later
data. Stated in `scope` and in the edge description: a pair with no edge is one no source records,
not one that is not a hub or focus city. "Which airports are focus cities" returns SFO/Alaska alone.

### 4. Creator and license of the data — **creator is the operations desk; no license**

The desk named itself as creator and confirmed the data is internal with **no license to state**.

Implemented as: `creator: Operations desk` in `.biotope/config.yaml`, which fills both manifests;
`license` left empty rather than invented. An access-restrictions value (`internal`) is available on
`biotope config set-project-metadata` and was not set, since the desk did not ask for it.

### 5. The prose about each airport — **left out**

The notes' sentences about an airport's size, location and connectivity name no airline role, so the
extractor reads none of them. Only `Hub for …` and `Focus city for …` statements become records.

### 6. Extractor strictness — **kept**

The reader stays regex-only: no model and no external service reads the notes, which are internal.
An unexpected statement shape, a non-IATA heading or a section with no role raises `ExtractionError`
rather than yielding partial records. One type error in it was repaired without loosening any check:
`heading.group(1)` was assigned through a `str | None` variable that Pyright could not narrow, so the
code now assigns it to an explicitly `str`-typed local. Behaviour is unchanged; `biotope graph check`
is clean.

## Recorded, no answer needed

- **Purpose** (`.biotope/project.yaml`): operations staff look up which airlines use which airports
  as hubs or focus cities. The three questions are answered in the hand-over.
- **Airport identity**: the notes' `##` headings are IATA codes, the same key
  `airports.csv#airports/iata` uses, so the airport table, the hub table and the notes establish the
  match jointly. Declared as the `airport_iata` term; the airline code likewise as `airline_code`.
- **Airport and airline sets**: the graph's airports are `airports.csv`'s and its airlines are
  `airlines.csv`'s. A claim naming an airport code or an airline name the corresponding table does
  not have fails the build — the same rule the desk gave for airline names, applied to airport codes
  as an engineering consequence, since neither table is asserted to be complete.
- **No model reads the notes.** They are internal. The extractor
  (`graph/extraction/airport_notes.py`) parses them with regular expressions only, and nothing in
  the pipeline sends document text anywhere.

## Still open

None. The graph's coverage limits are recorded as descriptions and in `scope`, not as open
questions: neither `airports.csv` nor `airlines.csv` is asserted to be a complete inventory, and the
notes are not one by the desk's answer above.
