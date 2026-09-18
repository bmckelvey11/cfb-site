# Perplexity research prompt — live totals middling

Companion to [middle-probability-2026-09-18.md](middle-probability-2026-09-18.md).
Targets the five questions that build left open, ordered by how much they would change
the tool. Paste into Perplexity in **Research / Deep Research mode**, not quick search.

---

```
Research in-play (live) totals markets in American college football and the
practice of middling them. I have built a calculator that prices a middle
between a pregame totals bet and a live total, and I need to know where its
assumptions are wrong.

Answer these five questions in order. Treat each as a separate section.

1. HISTORICAL IN-PLAY LINE DATA. Does any public, academic, commercial or
   scraped dataset contain timestamped in-play (live, during-game) totals for
   NCAA football, as opposed to pregame opening and closing lines? For each
   candidate name the provider, the seasons and sports covered, the sampling
   frequency, whether in-play quotes are genuinely distinguished from stale
   pregame ones, the access terms and the cost. Critically: does the feed log
   both sides of the same total with their prices at the same instant, or only
   a single consensus number? A consensus-only feed cannot tell me whether an
   Under at 58.5 was actually obtainable at the moment my Over 52.5 was live,
   which is the only thing that makes a middle real. Include academic
   replication archives and sports-analytics repositories, not only commercial
   odds APIs. Explicitly state if the honest answer is that no such dataset is
   publicly available for NCAA football.

2. HOW BOOKS PRICE IN-PLAY TOTALS. What modelling approaches are documented
   for live total pricing in American football -- drive-level Markov or
   expected-points models, Poisson or compound-Poisson scoring models,
   full-game simulation, or direct regression on game state? For each, what
   state variables are used beyond score and clock (possession, down and
   distance, field position, timeouts, observed pace, weather)? Cite the
   specific papers, patents, conference talks or vendor documentation.

3. VARIANCE OF REMAINING POINTS. What published estimates exist for the
   standard deviation of remaining points in a college or professional
   football game, conditional on time remaining? I want numbers I can compare
   against, and in particular whether sigma is documented as scaling with the
   square root of remaining time and where that approximation is reported to
   break down (late-game clock management, garbage time, overtime).

4. MIDDLE EXPECTED VALUE AND SIZING. What is the published treatment of middle
   bets -- the probability of hitting the middle, expected value net of vig,
   and optimal stake allocation across the two legs? Cover both the
   equalise-the-loss-legs convention and any Kelly or utility-based treatment.
   Is there evidence on whether live middling is profitable after vig and
   after accounting for limits, or is the documented consensus that it is not?

5. THE CONDITIONING-BIAS PROBLEM. My probability comes from a distribution
   conditioned on less information than the live market uses -- I have the
   live total and the clock, the book also has possession, pace and injuries.
   That makes my residual variance an upper bound on the true variance, which
   overstates the probability the middle hits. What is the standard name for
   this problem and what corrections are documented for it? Search the
   forecasting and probabilistic-calibration literature (variance inflation,
   recalibration, conditional coverage) as well as the sports-betting
   literature.

REQUIREMENTS FOR THE ANSWER

- Cite a source for every factual claim, with a link. Prefer peer-reviewed
  papers, working papers, primary vendor documentation and public datasets
  over blog posts, forum threads and tout content.
- Where you find a specific number -- a sigma, a hit rate, a hold percentage,
  a dataset size -- report it with the sample it came from and the years it
  covers. A number without a sample is not useful to me.
- Mark any claim you are not confident in with [uncertain]. Do not fabricate
  citations, statistics, dataset names or author names. If a section has no
  good sources, say "no reliable sources found" for that section rather than
  filling it with adjacent material.
- Distinguish throughout between college football and the NFL, and flag when
  you are substituting NFL evidence because college evidence does not exist.
- End with a section titled "What would change my calculator", listing only
  the findings that would actually alter a probability or an expected value,
  ranked by size of effect.
```

---

## Why these five

| # | What it would change |
| --- | --- |
| 1 | Would replace the whole drive-start reconstruction with real live lines and remove the conditioning bias entirely. Highest value if it exists. |
| 2 | Tells me which state variables are worth adding to the cell key. |
| 3 | An external σ benchmark to check 15.4 / 10.9 / 6.1 against. |
| 4 | Whether the tool should price middles at all, or price them and warn. |
| 5 | Turns the stated upper bound into a correction factor instead of a caveat. |
