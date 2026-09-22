<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# research quantile regresssion methods in sports betting

Quantile regression (QR) is well-established across sports betting analytics, and the research above traces its full arc from theory to practical implementation.

**Core insight**: QR models the entire conditional distribution of an outcome (margin, total, performance metric) rather than just the mean, which turns out to be essential for betting decisions — a peer-reviewed study shows that knowing the median outcome alone isn't enough to identify profitable bets; you need multiple quantiles to spot when a posted line has genuine expected-value edge on one side.

The report covers:

- The mathematical foundation (pinball/check loss function, linear QR specification)
- Direct sports applications — Koenker's own NCAA basketball spread/totals work, Australian rules football margin modeling with quantile splines, and DataGolf's use of QR for projecting golfer strokes-gained percentiles (highly relevant to your PGA Tour analytics work)
- Modern tree-based and boosting extensions (quantile regression forests, gradient boosting with pinball objectives, extreme-value boosting for tail events)
- Bettor-behavior studies using QR on in-play and horse-race wagering data
- A comparison table of methods with tradeoffs, plus a practical validation workflow (bootstrap CIs, empirical coverage checks, split-conformal calibration)

Given your existing strokes-gained and DuckDB/Python modeling stack, the quantile regression forest and gradient-boosting-with-pinball-loss approaches are likely the most directly reusable — they'd let you generate calibrated percentile bands (e.g., 10th/50th/90th) for player or team performance without fitting separate linear models per quantile.

<span style="display:none">[^1_1][^1_10][^1_11][^1_12][^1_13][^1_14][^1_15][^1_16][^1_17][^1_18][^1_19][^1_2][^1_20][^1_21][^1_22][^1_23][^1_24][^1_25][^1_26][^1_27][^1_28][^1_29][^1_3][^1_30][^1_4][^1_5][^1_6][^1_7][^1_8][^1_9]</span>

<div align="center">⁂</div>

[^1_1]: https://pmc.ncbi.nlm.nih.gov/articles/PMC10306238/

[^1_2]: http://www.econ.uiuc.edu/~econ472/koenkerhallock02.pdf

[^1_3]: https://www.psai.ph/docs/publications/tps/tps_2016_65_2_5.pdf

[^1_4]: https://www.aeaweb.org/articles?id=10.1257/jep.15.4.143

[^1_5]: https://www.econ.puc-rio.br/uploads/adm/trabalhos/files/seminario/2003/het_paper_031803_v2.pdf

[^1_6]: https://www.bis.org/publ/work1250.pdf

[^1_7]: https://diogoribeiro7.github.io/time-series/probabilistic_forecasting_quantiles_pinball_loss/

[^1_8]: https://openeclass.panteion.gr/modules/document/file.php/PMS152/Lectures/Lecture10.pdf

[^1_9]: https://openeclass.panteion.gr/modules/document/index.php?course=PMS152\&download=/6419b3cfBDwy/649aef77efzM.pdf

[^1_10]: https://r-statistics.co/Quantile-Regression-Forests-and-Prediction-Intervals.html

[^1_11]: https://link.springer.com/article/10.1007/s10687-023-00473-x

[^1_12]: http://www.matterofstats.com/mafl-stats-journal/2014/3/7/attaching-probabilities-to-game-margins-the-magic-of-quantile-regression

[^1_13]: http://www.econ.uiuc.edu/~roger/research/bracketology/Eapp.pdf

[^1_14]: http://www.matterofstats.com/mafl-stats-journal/2014/4/4/predicting-the-lead-at-every-change-part-ii

[^1_15]: https://datagolf.com/projecting-careers-blog/

[^1_16]: https://research.aston.ac.uk/en/publications/quantile-regression-analysis-of-in-play-betting-in-a-large-online/

[^1_17]: https://erepo.uef.fi/server/api/core/bitstreams/cfedc3a9-e374-46c2-a58a-173807bb36a8/content

[^1_18]: https://www.greo.ca/Modules/EvidenceCentre/files/Whiteford et al (2022)\_Quantile%20regression%20analysis%20of%20in-play%20betting%20in%20gambling%20dataset_final.pdf

[^1_19]: https://www.efmaefm.org/0efmameetings/efma annual meetings/2010-Aarhus/papers/Lidia_Sanchis_EFMA.pdf

[^1_20]: https://oasis.library.unlv.edu/gaming_institute/2016/June9/14/

[^1_21]: https://www.sciencedirect.com/science/article/pii/S2451958822000288

[^1_22]: https://www3.stat.sinica.edu.tw/ss_newpaper/SS-2020-0109_na.pdf

[^1_23]: https://columbia.edu/~mnb2/broadie/Assets/strokes_gained_pga_broadie_20110408.pdf

[^1_24]: https://pmc.ncbi.nlm.nih.gov/articles/PMC10929675/pdf/CJAS_51_2120973.pdf

[^1_25]: http://www.econ.uiuc.edu/~roger/research/rq/QRJEP.pdf

[^1_26]: https://sklearn-quantile.readthedocs.io/en/master/notebooks/example_qrf.html

[^1_27]: https://www.nber.org/system/files/working_papers/t0339/t0339.pdf

[^1_28]: https://scholarship.richmond.edu/economics-faculty-publications/115/

[^1_29]: http://www.econ.uiuc.edu/~roger/research/rq/rq.html

[^1_30]: https://pdfs.semanticscholar.org/5fc9/edc7e111376ee71a6529d5cce4ccd1a9848f.pdf


---

# add in info about spreads and totals and give a walkthrough on how you would build a model

Added the requested content, integrating both the spreads/totals research and a full step-by-step model-building walkthrough into the report.

**What's new in the report:**

- **Spreads and totals section expanded** with concrete methods: Koenker's NCAA bracketology quantile paired-comparison model, an NFL stochastic margin-of-victory quantile model with worked confidence bounds, and how totals modeling mirrors spread modeling by swapping the target variable (summed vs. signed score).
- **A 7-step build walkthrough** covering: defining the target (margin vs. total), assembling features (ratings, home-field, market-implied probability as benchmark), choosing decision-relevant quantiles, picking a model class (linear QR via statsmodels/sklearn vs. gradient boosting/XGBoost's `reg:quantileerror` vs. quantile regression forests), handling the discreteness of integer scores via kernel smoothing, validating with pinball loss and empirical coverage checks (plus split-conformal calibration), and finally translating quantiles into an actual backtested betting rule with a realistic win-rate benchmark (~52.4% needed to beat the vig).

Given your Python/DuckDB stack, Step 4 is the most actionable starting point — `HistGradientBoostingRegressor(loss='quantile')` or XGBoost's `reg:quantileerror` would slot directly into your existing feature pipelines for spread/total or golf projections.

<span style="display:none">[^2_1][^2_10][^2_11][^2_12][^2_13][^2_14][^2_15][^2_16][^2_17][^2_18][^2_19][^2_2][^2_20][^2_21][^2_22][^2_23][^2_24][^2_25][^2_26][^2_27][^2_28][^2_29][^2_3][^2_30][^2_31][^2_32][^2_33][^2_34][^2_35][^2_36][^2_37][^2_38][^2_39][^2_4][^2_40][^2_41][^2_42][^2_43][^2_44][^2_5][^2_6][^2_7][^2_8][^2_9]</span>

<div align="center">⁂</div>

[^2_1]: https://pmc.ncbi.nlm.nih.gov/articles/PMC10929675/

[^2_2]: https://pmc.ncbi.nlm.nih.gov/articles/PMC10306238/

[^2_3]: https://icots.info/documents/papers/isi56/IPM45_Everson.pdf?1402524980

[^2_4]: https://moreland.dev/projects/elora/example.html

[^2_5]: https://cienciadedatos.net/documentos/py68-quantile-regression-python

[^2_6]: https://pypi.org/project/sports-betting/

[^2_7]: https://digital.wpi.edu/downloads/x346d423k

[^2_8]: https://github.com/throwawayhub25/Sports-Betting-Model

[^2_9]: https://github.com/statsmodels/statsmodels/blob/main/statsmodels/regression/quantile_regression.py

[^2_10]: http://www.econ.uiuc.edu/~roger/research/bracketology/MM.pdf

[^2_11]: https://xgboost.readthedocs.io/en/release_2.0.0/python/examples/quantile_regression.html

[^2_12]: https://www.tandfonline.com/doi/abs/10.1080/02664763.2022.2120973

[^2_13]: https://www.ec-undp-electoralassistance.org/\_pdfs/publication/qwSc2E/PythonQuantileRegression.pdf

[^2_14]: https://shiny4.lsnet.ucla.edu/venv/lib64/python3.10/site-packages/sklearn/linear_model/\_quantile.py

[^2_15]: https://gist.github.com/conormm/e1c688be69bb31a32ce2b28e029f175d

[^2_16]: https://research.aston.ac.uk/en/publications/quantile-regression-analysis-of-in-play-betting-in-a-large-online/

[^2_17]: https://erepo.uef.fi/server/api/core/bitstreams/cfedc3a9-e374-46c2-a58a-173807bb36a8/content

[^2_18]: https://www.greo.ca/Modules/EvidenceCentre/files/Whiteford et al (2022)\_Quantile%20regression%20analysis%20of%20in-play%20betting%20in%20gambling%20dataset_final.pdf

[^2_19]: http://www.matterofstats.com/mafl-stats-journal/2014/3/7/attaching-probabilities-to-game-margins-the-magic-of-quantile-regression

[^2_20]: https://oasis.library.unlv.edu/gaming_institute/2016/June9/14/

[^2_21]: http://www.econ.uiuc.edu/~roger/research/bracketology/Eapp.pdf

[^2_22]: http://www.matterofstats.com/mafl-stats-journal/2014/4/4/predicting-the-lead-at-every-change-part-ii

[^2_23]: https://www.sciencedirect.com/science/article/pii/S2451958822000288

[^2_24]: https://datagolf.com/projecting-careers-blog/

[^2_25]: https://www3.stat.sinica.edu.tw/ss_newpaper/SS-2020-0109_na.pdf

[^2_26]: https://columbia.edu/~mnb2/broadie/Assets/strokes_gained_pga_broadie_20110408.pdf

[^2_27]: https://www.bis.org/publ/work1250.pdf

[^2_28]: https://pmc.ncbi.nlm.nih.gov/articles/PMC10929675/pdf/CJAS_51_2120973.pdf

[^2_29]: https://www.efmaefm.org/0efmameetings/efma annual meetings/2010-Aarhus/papers/Lidia_Sanchis_EFMA.pdf

[^2_30]: http://www.econ.uiuc.edu/~econ472/koenkerhallock02.pdf

[^2_31]: https://www.psai.ph/docs/publications/tps/tps_2016_65_2_5.pdf

[^2_32]: http://www.econ.uiuc.edu/~roger/research/rq/QRJEP.pdf

[^2_33]: https://openeclass.panteion.gr/modules/document/file.php/PMS152/Lectures/Lecture10.pdf

[^2_34]: https://www.aeaweb.org/articles?id=10.1257/jep.15.4.143

[^2_35]: https://sklearn-quantile.readthedocs.io/en/master/notebooks/example_qrf.html

[^2_36]: https://www.econ.puc-rio.br/uploads/adm/trabalhos/files/seminario/2003/het_paper_031803_v2.pdf

[^2_37]: https://link.springer.com/article/10.1007/s10687-023-00473-x

[^2_38]: https://openeclass.panteion.gr/modules/document/index.php?course=PMS152\&download=/6419b3cfBDwy/649aef77efzM.pdf

[^2_39]: https://www.nber.org/system/files/working_papers/t0339/t0339.pdf

[^2_40]: https://r-statistics.co/Quantile-Regression-Forests-and-Prediction-Intervals.html

[^2_41]: https://scholarship.richmond.edu/economics-faculty-publications/115/

[^2_42]: http://www.econ.uiuc.edu/~roger/research/rq/rq.html

[^2_43]: https://pdfs.semanticscholar.org/5fc9/edc7e111376ee71a6529d5cce4ccd1a9848f.pdf

[^2_44]: https://diogoribeiro7.github.io/time-series/probabilistic_forecasting_quantiles_pinball_loss/

