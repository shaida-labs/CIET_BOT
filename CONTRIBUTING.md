# Contributing

Use Node 22.12+ and Python 3.12+. Keep secrets outside version control and preserve existing migrations.

Before submitting a change, run `npm test`, `npm run lint`, `npm run build`, `npm run test:e2e`, backend `pytest`, backend `ruff check app tests`, and the applicable dependency/migration checks. Every bug fix needs a regression test; security-sensitive changes need a negative test. Do not weaken or skip failing tests to obtain a green result.
