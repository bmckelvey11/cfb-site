# Product

## Register

product

## Users

Small group (the owner plus a few others) backtesting college football betting systems — analysts working at a desk, not on mobile. They come in with a hypothesis ("home dogs off a bye week cover"), configure filters against 13k+ historical games, and read hit rate / ROI / p-value output to decide whether a system is real. Repeat, data-dense sessions, not one-off visits.

## Product Purpose

`cfb_system_maker` backtests college football betting systems against historical CFBD data. It exists so a system can be defined, filtered, and statistically validated (Wilson CI, permutation p-value, holdout split) before anyone bets real money on it. Success is a trustworthy, fast read on whether a filter combination has real edge or is noise — the UI's job is to make that read fast and hard to misread, not to look impressive.

## Brand Personality

Modeled explicitly on Sports Insights Bet Labs and terminal-style trading tools: dense, numbers-first, no-nonsense. Tabular-nums, compact stat chips, a sidebar filter panel, a single restrained accent color (teal) used only for signal (positive/active state), not decoration. Confidence through density and precision, not whitespace or polish-for-its-own-sake.

## Anti-references

Not a consumer SaaS dashboard — avoid soft gradients, big rounded hero cards, marketing-style stat tiles, or generous whitespace that would slow down scanning a table of 50 systems. Avoid decorative color; every color in the UI should mean something (win/loss/push, active/inactive, positive/negative).

## Design Principles

- Density over decoration — this is a working tool used repeatedly, not a landing page seen once.
- Every color carries meaning (win/loss/push, positive/negative ROI, active filter) — never decorative.
- Numbers are the product — tabular-nums, right-aligned figures, scannable tables are non-negotiable.
- Progressive enhancement — filter modal / search / sidebar JS enhancements must degrade to working `<form>` fallbacks (existing `.js` / no-JS CSS pattern).
- No lookahead, ever, in what the UI presents as pre-game — `result_lookahead` features stay visually quarantined (existing amber-bordered `.feature-group.lookahead` pattern), not just filtered in code.

## Accessibility & Inclusion

WCAG AA baseline: focus-visible outlines on all interactive elements, sufficient contrast on body/muted text, keyboard-operable filter modal and dropdowns. No specialized accommodations beyond that.
