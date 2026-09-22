# Optimal Prompting Guide for Perplexity

## Executive answer

The best Perplexity prompt is **retrieval-first, specific, and output-bound**. It should tell Perplexity what decision or question to resolve, provide the minimum necessary context, define the research boundaries and evidence standard, and specify the final deliverable. Perplexity’s own guidance identifies five basic ingredients—**instruction, context, input, keywords, and output format**—while also warning against vagueness, missing context, and combining too many unrelated tasks.[^1][^2]

For serious research, expand those five ingredients into the seven-part structure below:

1. **Task** — the exact job and decision to support.
2. **Context** — background that changes how the question should be answered.
3. **Scope** — entities, dates, geography, definitions, and exclusions.
4. **Evidence** — preferred sources, recency, citation, and verification rules.
5. **Analysis** — comparisons, calculations, tests, or reasoning required.
6. **Output** — format, length, sections, tables, and files.
7. **Uncertainty** — how to handle missing, conflicting, or weak evidence.

This structure is optimal because Perplexity uses the user’s actual question to drive retrieval. In the Agent API, `input` both contains the question and seeds the first search query; in Sonar, the user message drives search while the system prompt affects only answer generation.[^3][^4]

## The core structure

### 1. Task

Start with a direct action verb and one primary objective. Good openings include **research**, **compare**, **audit**, **explain**, **extract**, **evaluate**, **design**, or **recommend**.

```markdown
Research whether [specific hypothesis or claim] is supported by current evidence.

Compare [A, B, and C] and recommend the best option for [specific use case].

Audit the attached [document/data/code] for [defined classes of problems].
```

Avoid beginning with a broad topic such as “college football models” or “DuckDB.” Perplexity explicitly recommends starting with a clear question rather than a single broad keyword and says that focused Research questions produce more focused reports.[^5]

### 2. Context

Include only facts that materially affect the answer: the intended user, current system, prior findings, technical level, decision stage, and constraints. Perplexity’s official prompt guidance says context helps it understand the task and that prompts should include specific data or text needed to answer it.[^2][^1]

```markdown
Context:
- I am building a pregame college-football totals model.
- The current benchmark is the market closing total.
- The data covers FBS games from 2005–2025, but schema coverage changes over time.
- The goal is out-of-sample improvement, not in-sample fit.
```

Do not bury the actual question below a long biography or generic role description. Context should change the research; otherwise, omit it.

### 3. Scope

Define the retrieval boundaries explicitly. Useful scope fields include:

- Time period or publication cutoff.
- Geography, league, industry, or population.
- Included and excluded entities.
- Definitions for ambiguous terms.
- Number of options, examples, or recommendations.
- What is out of scope.

```markdown
Scope:
- Prioritize work published or updated from January 2022 through September 2026.
- Include academic forecasting literature and credible sports-analytics applications.
- Focus on methods feasible with game-level or team-week data.
- Exclude methods requiring proprietary player-tracking data.
- Return no more than six recommended methods.
```

Capping list size improves focus; Perplexity’s API guidance specifically recommends stating how long a requested list should be. For the API, hard domain, date, recency, and location restrictions belong in search-filter parameters rather than prompt prose.[^4][^6][^3]

### 4. Evidence

Tell Perplexity what constitutes acceptable support. This is more useful than a generic “be accurate” instruction.

```markdown
Evidence requirements:
- Prefer primary sources: official documentation, peer-reviewed papers, conference papers, and first-party datasets.
- Use strong secondary sources only for context or when no primary source exists.
- Cite every substantive factual claim near the claim.
- Cross-check consequential claims with at least two independent sources where possible.
- Distinguish publication date from the date of the underlying data.
- Do not treat search snippets as sufficient evidence when the full source is available.
```

For current or changing subjects, use an explicit “as of” date. For document-based research, name the uploaded material and explain whether it should be treated as authoritative, compared with the web, or challenged. Perplexity recommends combining uploaded files with current web sources and cross-referencing the two. Long uploads may be selectively extracted rather than read entirely, so point to relevant sections, page ranges, tables, or filenames when precision matters.[^7][^5]

### 5. Analysis

State the intellectual work required after retrieval. Without this block, a research answer can become a source summary rather than a decision tool.

```markdown
Analysis requirements:
- Separate descriptive evidence from causal claims.
- Compare methods on predictive value, leakage risk, sample efficiency, interpretability, computational cost, and implementation difficulty.
- Identify assumptions and failure modes.
- Explain where sources agree and disagree.
- Convert findings into a prioritized implementation sequence.
```

Ask for calculations only when the inputs are available, and require Perplexity to show assumptions. If the objective is source discovery rather than synthesis, ask for an annotated source list instead of a full report; this avoids paying for analysis that is not needed.

### 6. Output

Specify a deliverable, not merely “a detailed answer.” Perplexity supports requests for summaries, tables, bullets, step-by-step guides, documents, presentations, and spreadsheets; its guidance recommends naming both the file type and expected structure for generated artifacts.[^5]

```markdown
Output:
1. Begin with a five-bullet executive verdict.
2. Provide a comparison table with one row per method.
3. Give the evidence review in clearly labeled sections.
4. End with a prioritized implementation plan and validation checklist.
5. Keep the main report under 2,500 words.
6. Use concise Markdown and inline citations.
```

For API workflows that require dependable machine-readable output, use `response_format` with a JSON Schema rather than relying on prose formatting instructions alone. Perplexity notes that schema conformance can fail if generation is cut off by the token limit, so allocate sufficient output tokens.[^8][^9]

### 7. Uncertainty

Explicitly authorize Perplexity to report gaps instead of filling them with plausible-sounding material.

```markdown
Uncertainty rules:
- Say when evidence is thin, contested, inaccessible, or absent.
- Do not substitute evidence about a related population, product, season, or metric without labeling the substitution.
- If sources conflict, describe the conflict and judge them by source quality and relevance.
- Label inference separately from sourced fact.
- Do not invent citations, data, quotations, or implementation details.
```

This mirrors Perplexity’s Agent API recommendation to state when relevant results cannot be found after alternative searches rather than substituting off-topic evidence.[^3]

## Universal template

```markdown
# Task
[Use one action verb.] [State the exact question, decision, or deliverable.]

# Context
- User/audience: [who will use the result]
- Current situation: [relevant background]
- Objective: [what success means]
- Constraints: [budget, tools, data, skills, time, risk tolerance]

# Inputs
- Use: [attached files, pasted text, URLs, datasets, prior findings]
- Treat [input] as: [authoritative / a claim to verify / one source among many]
- Relevant locations: [filename, section, page, table, column]

# Scope
- Include: [entities, topics, methods]
- Exclude: [out-of-scope material]
- Time range: [dates and “as of” date]
- Geography/population: [scope]
- Definitions: [ambiguous terms]
- Limit: [number of items or recommendations]

# Evidence requirements
- Prioritize: [primary and authoritative source types]
- Recency: [requirements]
- Verification: [cross-check rules]
- Citations: [placement and density]

# Analysis requirements
- Evaluate using: [criteria]
- Compare: [alternatives]
- Test or calculate: [required analysis]
- Identify: [assumptions, conflicts, risks, gaps]

# Output
- Deliverable: [answer/report/table/plan/document/spreadsheet]
- Structure: [ordered sections]
- Length: [limit]
- Style: [technical level and tone]
- Tables/files: [requirements]

# Uncertainty rules
If evidence is unavailable, conflicting, or weak, say so explicitly. Separate sourced facts from inference. Do not invent missing data or substitute adjacent evidence without labeling it.
```

Not every prompt needs every block. A quick factual lookup may need only **Task + Scope + Output**; a consequential research decision should use all seven.

## Task-specific templates

### Deep research

```markdown
Research [precise question] to support [decision].

Context:
- [Relevant project or decision background]
- [What is already known or previously tested]
- [Constraints that affect applicability]

Research scope:
- Cover [subquestions].
- Focus on [population/geography/domain] from [date] through [as-of date].
- Include [source classes]; exclude [irrelevant areas].

Evidence standard:
- Prioritize primary and authoritative sources.
- Cross-check major claims across independent sources.
- Distinguish direct evidence, expert interpretation, and your inference.
- State where evidence is thin, contested, or absent.

Analysis:
- Compare findings across [criteria].
- Identify assumptions, contradictions, and failure modes.
- Explain what transfers to my context and what does not.
- Produce actionable recommendations ranked by expected value and feasibility.

Output:
- Executive verdict.
- Research findings by subquestion.
- Comparison table.
- Ranked recommendations.
- Validation plan and unresolved questions.
- Concise Markdown with inline citations; maximum [N] words.
```

Use one well-defined research objective per run, then drill down with follow-ups. Perplexity recommends iterative follow-up questions for Research, and its current Advanced Deep Research interface allows follow-ups while research is still running.[^10][^5]

### Product or method comparison

```markdown
Compare [A], [B], and [C] for [specific use case and user].

Evaluate them on:
- [criterion 1]
- [criterion 2]
- [criterion 3]
- [total cost or implementation burden]
- [risks and limitations]

Use information current as of [date]. Prefer official product documentation and first-party pricing, then independent testing. Separate advertised capability from independently verified performance.

Output a side-by-side table, explain the decisive trade-offs, recommend one option, and identify the conditions under which a different option would win. State any information that could not be verified.
```

### Uploaded-file audit

```markdown
Audit the attached [filename] for [objective].

Treat the file as [authoritative input / an artifact to challenge]. Focus on [pages, sections, tables, columns, or modules]. Check for:
- [error class]
- [internal inconsistencies]
- [missing evidence or fields]
- [methodological or implementation risks]
- [differences from current external guidance]

Cross-reference the file with current authoritative web sources where relevant. For every issue, report its location, severity, evidence, impact, and recommended correction. Do not assume omitted material is present elsewhere; label anything that could not be inspected.
```

### Technical architecture

```markdown
Design and critique an architecture for [system].

Environment:
- Current stack: [languages, databases, cloud, tools]
- Data scale and update frequency: [details]
- Users and workloads: [details]
- Constraints: [cost, latency, security, maintenance, skill level]

Compare [candidate approaches] on correctness, operability, scalability, cost, lock-in, and migration risk. Prefer official documentation for current product capabilities. Identify hidden assumptions and reject unnecessary complexity.

Output:
1. Recommended architecture and rationale.
2. Component and data-flow description.
3. Decision table.
4. Phased implementation plan.
5. Testing, observability, rollback, and governance checklist.
6. Open questions that must be resolved before implementation.
```

## Projects and persistent instructions

Perplexity Projects are persistent workspaces that can hold searches, Computer tasks, files, connected tools, context, and custom instructions; current documentation allows up to 8,000 characters of Project instructions. Use those instructions for **stable behavior that should apply to every query**, while keeping the changing research question, dates, entities, and deliverable in the individual prompt.[^11]

### Recommended Project instructions

```markdown
# Role
Act as a rigorous research and technical-analysis partner for [project/domain].

# Default behavior
- Lead with the direct answer or decision-relevant finding.
- Prefer primary and authoritative sources.
- Cite factual claims near the claim.
- Distinguish sourced fact, calculation, interpretation, and recommendation.
- State when evidence is weak, conflicting, inaccessible, or absent.
- Never invent data, citations, quotations, file contents, or test results.
- Ask one concise clarification question only when ambiguity would materially change the result; otherwise state assumptions and proceed.

# Analysis standards
- Check dates, definitions, populations, units, and denominators.
- Look for leakage, survivorship bias, selection effects, and train/test contamination when reviewing models.
- Compare recommendations against a simple benchmark and the current workflow.
- Prefer out-of-sample evidence and reproducible methods.
- Include implementation burden and failure modes, not just theoretical advantages.

# Output defaults
- Use concise Markdown with descriptive headings.
- Use tables for genuine side-by-side comparisons.
- Put the recommendation before supporting detail.
- End with next actions only when the task calls for them.
- Avoid generic introductions, repeated conclusions, and unsupported confidence.

# Project context
[Add stable domain definitions, stack details, canonical files, and standing constraints.]
```

Do not turn Project instructions into a giant prompt library. Stable standards belong there; reusable task templates should live in separate Markdown files, and run-specific requirements should remain in the current query. This separation follows the Agent API’s analogous distinction: persistent `instructions` are for role, tone, formatting, and grounding rules, while query-specific framing belongs in `input`.[^3]

## API-specific rules

| Concern | Optimal location | Why |
|---|---|---|
| Role, tone, language, citation behavior | `instructions` or system prompt | These rules should persist across the answer process.[^3] |
| Actual research question and specific context | `input` or user message | The input seeds retrieval; specificity improves search relevance.[^3][^4] |
| Domain, publication date, update date, recency, location | `web_search.filters` and `user_location` | These are hard retrieval controls; the Agent API supports domain, date, recency, and location filters.[^6] |
| Exact machine-readable shape | `response_format` with JSON Schema | It enforces a parseable schema more reliably than prose.[^8][^9] |
| Search/reasoning depth | `max_steps` or an appropriate preset | Perplexity advises controlling the loop with request parameters rather than lengthy tool instructions.[^3] |
| Sources and URLs | Response citation/search-result fields | Sonar already returns citations and search results; prompting it to reproduce URLs in prose is unnecessary.[^4] |

For Sonar specifically, do not place retrieval requirements only in the system prompt because the system prompt is not used to generate the search. Put descriptive search language in the user message and hard restrictions in filter parameters. Avoid content-heavy few-shot examples because the search stage can latch onto the example’s topic; examples of structure are safer, while JSON Schema is the better choice when exact output shape matters.[^4]

## Common failure patterns

| Failure | Why it underperforms | Better approach |
|---|---|---|
| “Tell me everything about X” | No decision, boundary, or stopping rule | Ask one decision-oriented question with explicit scope. |
| Several unrelated tasks in one prompt | Retrieval and analysis compete for attention | Split the work into sequential prompts or separate threads. Perplexity explicitly advises one thing at a time.[^5] |
| Excessive persona text | Consumes attention without improving retrieval | Use one sentence for expertise and spend detail on context, evidence, and scope. |
| “Use reliable sources” only | Reliability remains undefined | Name preferred source classes and verification rules. |
| “Latest” without a date | The cutoff is ambiguous and difficult to audit | State “current as of September 22, 2026” or the appropriate date. |
| Asking for “all” examples or sources | Produces unfocused, arbitrarily long output | Cap the count and define selection criteria.[^4] |
| Pasting a model answer to imitate | Can contaminate retrieval with the example topic | Specify headings or a schema without example content.[^4] |
| Putting API filters in prose | Soft language may not constrain retrieval | Use domain/date/location filter parameters.[^3][^6] |
| Demanding certainty | Encourages false resolution of gaps | Require explicit uncertainty, conflicts, and missing evidence. |
| Repeating the entire prompt during follow-up | Wastes context and can reset focus | Refer to the prior result and request one targeted revision or extension. |

## Recommended workflow

1. **Choose the mode by job.** Use a short search-style prompt for quick facts, a detailed prompt for synthesis, Research for complex multi-source investigation, and Computer or document creation when the desired result is an artifact. Perplexity distinguishes quick search from detailed conversational prompting and recommends stating the intended action and deliverable.[^12][^5]
2. **Write the decision first.** If the prompt does not reveal what the answer will be used for, add one sentence explaining the decision.
3. **Add scope before style.** Dates, definitions, included populations, and exclusions improve retrieval more than elaborate tone instructions.
4. **Attach and point.** Upload relevant files, but name the precise sections or fields to inspect; Perplexity retains attachment context for follow-ups, while long files may be selectively extracted.[^7]
5. **Run a broad first pass.** Ask for the map of the issue, major evidence, disagreements, and gaps.
6. **Use targeted follow-ups.** Challenge the weakest claim, request missing primary sources, change one assumption, or deepen one subquestion rather than rerunning the whole prompt. Perplexity recommends iterative refinement and follow-up questions.[^2][^5]
7. **Finish with verification.** Ask for a claim audit, date check, source-quality review, or implementation checklist before treating the output as final.

## Best default prompt

```markdown
Research and evaluate [specific question] to support [specific decision].

Context: [2–5 facts that materially affect the answer].

Scope: Cover [topics/entities] for [population/geography] from [start date] through [as-of date]. Include [items] and exclude [items]. Define [ambiguous terms]. Limit recommendations to [N].

Evidence: Prioritize [primary/authoritative sources]. Cross-check consequential claims where possible, cite factual claims near the claim, and distinguish direct evidence from inference. Do not substitute adjacent evidence without labeling it.

Analysis: Compare the alternatives on [criteria]. Identify assumptions, conflicting evidence, failure modes, implementation burden, and what would invalidate each conclusion.

Output: Begin with the direct verdict, then provide [required sections], a comparison table, ranked recommendations, and a validation checklist. Use concise Markdown and stay under [length].

If relevant evidence is weak, contested, inaccessible, or absent, say so explicitly rather than filling the gap.
```

For this user’s technical research workflow, the most important additions beyond Perplexity’s basic five-part formula are the **evidence**, **analysis**, and **uncertainty** blocks. They turn a good search prompt into a reproducible research specification and align naturally with the user’s existing practice of keeping focused Projects, reusable Markdown playbooks, and separate research workflows.[^13][^14][^15]

---

## References

1. [Practical Tips for Using Perplexity - Perplexity Help Center](https://www.perplexity.ai/help-center/en/articles/10352971-practical-tips-for-using-perplexity) - A prompt is the starting point for each of your conversations—or sessions—with Perplexity. Clearly s...

2. [Prompting tips and examples | Perplexity Help Center](https://www.perplexity.ai/help-center/en/articles/10354321-prompting-tips-and-examples) - Some tips and tricks from the Perplexity Team on how to write a prompt for a great response.

3. [Prompt Guide - Perplexity API](https://docs.perplexity.ai/docs/agent-api/prompt-guide) - Rules: - Aim for brief sentences and paragraphs. - Define jargon the first time you use it. - Prefer...

4. [Prompt Guide - Perplexity API](https://docs.perplexity.ai/docs/sonar/prompt-guide) - The shared prompting best practices live in the Agent API Prompt Guide and apply to Sonar without mo...

5. [Tips for Getting Better Answers from Perplexity](https://www.perplexity.ai/help-center/en/articles/13645819-tips-for-getting-better-answers-from-perplexity) - Say how you want the answer. You can ask for a summary, a table, bullet points, or a step-by-step gu...

6. [Web Search - Perplexity API](https://docs.perplexity.ai/docs/agent-api/tools/web-search) - Search the web from the Agent API with filters, search configurations, pricing, parameters, and resp...

7. [File Uploads - Perplexity Help Center](https://www.perplexity.ai/help-center/en/articles/10354807-file-uploads) - Upload files to Perplexity with the attach button or drag and drop. See supported file types, includ...

8. [Output Control](https://docs.perplexity.ai/docs/agent-api/output-control)

9. [Structured Output Extraction - Perplexity API](https://docs.perplexity.ai/docs/cookbook/articles/structured-output-extraction/README)

10. [What's New in Advanced Deep Research - Perplexity](https://www.perplexity.ai/help-center/en/articles/13600190-what-s-new-in-advanced-deep-research) - Advanced Deep Research is a major update to Perplexity's Research feature, introducing improved accu...

11. [What are Projects? - Perplexity Help Center](https://www.perplexity.ai/help-center/en/articles/10352961-what-are-spaces) - Projects are persistent, shareable Perplexity workspaces that keep searches, Computer tasks, files, ...

12. [What is the difference between a prompt and a search? - Perplexity](https://www.perplexity.ai/help-center/en/articles/10354937-what-is-the-difference-between-a-prompt-and-a-search) - In Perplexity, a prompt is a specific question or detailed instruction you give to the AI to generat...

13. [spaces in perplexity](https://www.perplexity.ai/search/4871db05-55df-4342-b026-dbda34dbf188) - Perplexity Spaces are dedicated workspaces for organizing threads, files, and custom instructions ar...

14. [Yes, please create a markdown file for all six spaces](https://www.perplexity.ai/search/856f6c71-1b1d-44dd-ae29-e24a015fcb03) - Perplexity Spaces are designed to be persistent workspaces that combine custom instructions, uploade...

15. [how to structure a research space in perplexity](https://www.perplexity.ai/search/fdf43e8e-f1fb-43b3-9691-c6616636a8a5) - Structure a Perplexity research Space like a focused project workspace: one topic, one goal, one set...

