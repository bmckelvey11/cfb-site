# Do entering PFF grades line up with the totals residual?

**Question.** After the market total is subtracted, do snap-weighted entering PFF offense and defense grades still move the combined score?

**Method.** Regular-season games. Residual is final points (overtime included) minus the book-median total, open and close separately (`core.v_game_book_median`). Each grade is the snap-weighted mean of weekly rows in `stg.pff_offense_summary` or `stg.pff_defense_summary` with week strictly before the game. Week 0 is excluded. A team with no earlier week uses the previous season. The regressor is home plus away. OLS slope, one grade at a time. The 95% interval is a wild cluster bootstrap on season (9999 Rademacher draws). The leave-one-season range is the min and max slope with each season held out. 2026 is plotted and left out of the fit. Seven grades were named before the fit: `grades_offense`, `grades_pass`, `grades_run`, `grades_defense`, `grades_coverage_defense`, `grades_pass_rush_defense`, `grades_run_defense`.

**Data.** Both teams have an entering grade on 4,809 games in 2019–2025. The open residual uses 3,656 of those, seasons 2021–2025, because 2019 and 2020 have no opening total in the view. The close residual uses all 4,809, seasons 2019–2025. 2026 contributes 155 graded games to the plot only.

**Numbers.** Slope is points of total per grade point of the home+away sum. A 10-point move in that sum is the "1 point per 10 grades" size when the slope is 0.1.

| Grade | Residual | n | Seasons | Slope | Leave-one-season | 95% interval |
| --- | --- | ---: | ---: | ---: | --- | --- |
| grades_offense | open | 3656 | 5 | -0.051 | -0.119 to -0.003 | -0.216 to 0.114 |
| grades_offense | close | 4809 | 7 | -0.104 | -0.147 to -0.074 | -0.221 to 0.012 |
| grades_pass | open | 3656 | 5 | -0.006 | -0.038 to 0.022 | -0.065 to 0.053 |
| grades_pass | close | 4809 | 7 | -0.018 | -0.036 to 0.001 | -0.061 to 0.026 |
| grades_run | open | 3656 | 5 | -0.055 | -0.104 to 0.001 | -0.206 to 0.097 |
| grades_run | close | 4809 | 7 | -0.099 | -0.132 to -0.068 | -0.207 to 0.014 |
| grades_defense | open | 3656 | 5 | -0.108 | -0.175 to -0.026 | -0.293 to 0.077 |
| grades_defense | close | 4809 | 7 | -0.091 | -0.141 to -0.039 | -0.228 to 0.050 |
| grades_coverage_defense | open | 3656 | 5 | -0.022 | -0.092 to 0.032 | -0.181 to 0.137 |
| grades_coverage_defense | close | 4809 | 7 | -0.068 | -0.126 to -0.034 | -0.208 to 0.073 |
| grades_pass_rush_defense | open | 3656 | 5 | -0.044 | -0.114 to 0.049 | -0.268 to 0.181 |
| grades_pass_rush_defense | close | 4809 | 7 | 0.008 | -0.040 to 0.074 | -0.162 to 0.178 |
| grades_run_defense | open | 3656 | 5 | -0.170 | -0.244 to -0.119 | -0.330 to -0.009 |
| grades_run_defense | close | 4809 | 7 | -0.116 | -0.169 to -0.079 | -0.245 to 0.013 |

Thirteen of the fourteen intervals cover 0. The exception is run defense against the open: -0.170, 95% -0.330 to -0.009, and every leave-one-season slope stays negative. The same grade against the close has 95% -0.245 to 0.013, which covers 0. Several other close slopes stay negative in every leave-one-season refit, and their bootstrap intervals still cover 0. An interval that covers 0 is not evidence the grade is unrelated. Offense-open, coverage-open, and both pass-rush intervals also cover a +1 point shift per 10 grade points, so those four cannot see an effect of that size.

**What this does not support.** A bet. A claim that run defense beats the closing number. A claim that the other six grades are zero. Treating 2026 as confirmation. The grades are themselves estimates, so measurement error pulls these slopes toward 0. The open and the close are different clocks: 2019–2020 have no open, and the median open is not one timestamp.

Reproduce with `python research/totals/scripts/pff_residual_screen.py`. Figure and table: `data/exports/pff_residual_screen.png`, `data/exports/pff_residual_screen.csv`.
