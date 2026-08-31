# B4 Raw Data Field Inventory

## Step 1: All Available Fields

### games_2024.json
```
{'attendance': 'NoneType', 'awayClassification': 'NoneType', 'awayConference': 'NoneType', 'awayId': 'int', 'awayLineScores': 'list', 'awayPoints': 'int', 'awayPostgameElo': 'NoneType', 'awayPostgameWinProbability': 'NoneType', 'awayPregameElo': 'NoneType', 'awayTeam': 'str', 'completed': 'bool', 'conferenceGame': 'bool', 'excitementIndex': 'NoneType', 'highlights': 'str', 'homeClassification': 'str', 'homeConference': 'str', 'homeId': 'int', 'homeLineScores': 'list', 'homePoints': 'int', 'homePostgameElo': 'NoneType', 'homePostgameWinProbability': 'NoneType', 'homePregameElo': 'NoneType', 'homeTeam': 'str', 'id': 'int', 'neutralSite': 'bool', 'notes': 'NoneType', 'season': 'int', 'seasonType': 'str', 'startDate': 'str', 'startTimeTBD': 'bool', 'venue': 'NoneType', 'venueId': 'NoneType', 'week': 'int'}
```

### lines_2024.json
```
{'awayClassification': 'str', 'awayConference': 'str', 'awayScore': 'int', 'awayTeam': 'str', 'awayTeamId': 'int', 'homeClassification': 'str', 'homeConference': 'str', 'homeScore': 'int', 'homeTeam': 'str', 'homeTeamId': 'int', 'id': 'int', 'lines': 'list', 'season': 'int', 'seasonType': 'str', 'startDate': 'str', 'week': 'int'}
```

## Step 2: Candidate Feature Availability (in specified order)

1. **`week`** - AVAILABLE (int in both games_2024.json and lines_2024.json)
2. **`neutralSite`** - AVAILABLE (bool in games_2024.json)
3. **`conferenceGame`** - AVAILABLE (bool in games_2024.json)
4. **`fcs_dog`** - AVAILABLE (can be computed: check if underdog's conference field is None/missing; games_2024.json has awayConference, homeConference; lines_2024.json has awayConference, homeConference)
   - Full-file null-rate check: awayConference is None in 53 of 3747 records (~1.4%); homeConference is None in 17 of 3747 records (~0.5%). This minority-subset pattern is consistent with FCS opponents (which have no conference data), confirming the field is available for feature computation. Verify by running:
   ```bash
   python -c "
   import json
   from pathlib import Path
   g = json.loads(Path('../cfb-site/data/raw/games_2024.json').read_text(encoding='utf-8'))
   n = len(g)
   none_away = sum(1 for r in g if r.get('awayConference') is None)
   none_home = sum(1 for r in g if r.get('homeConference') is None)
   print(f'total={n} awayConference_None={none_away} homeConference_None={none_home}')
   "
   ```
5. **`home_dog`** - Would require computing underdog position from betting lines (not a raw field)

### Selection Summary (first 4 supported, in order)
- [x] week
- [x] neutralSite
- [x] conferenceGame
- [ ] fcs_dog
- [x] home_dog

**Total selected: 4 features** (Bonferroni budget reached)

**Note:** `fcs_dog` turned out to be zero-variance post-join (no FCS
opponent carries a betting line, so `fcs_dog=0` for all 12,493 joined
games) and was substituted with `home_dog` (item 5 above, the plan's own
next-in-order fallback candidate) for the actual B4.2 run — see
`research/BLOCKERS.md`, B4.2 entry (owner resolution dated 2026-07-31).
`home_dog` is selected in place of `fcs_dog`; the "first 4 supported"
framing above reflects the original B4.1 determination and predates this
substitution.
