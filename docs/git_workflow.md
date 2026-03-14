# Git Workflow and Release Rules

## 1) Branch Strategy (GitHub Flow)

- `main`: production stable
- `dev`: daily integration
- `feat/*`: feature branch from `dev`
- `fix/*`: bugfix branch from `dev`

## 2) Commit Message Convention

Use Angular-style commit messages:

- `feat: ...`
- `fix: ...`
- `docs: ...`
- `style: ...`
- `refactor: ...`
- `perf: ...`
- `test: ...`
- `chore: ...`
- `revert: ...`

## 3) Golden Push Timing

Push at these four critical checkpoints:

1. Independent feature closure (usually every 2-4 hours)
- Example: one API endpoint done and locally verified.

2. Before leaving computer (hard rule, no overnight local-only code)
- If unfinished, commit as `WIP` and push your branch.

3. Before opening PR or merge
- Push to trigger remote CI and syntax checks.

4. Right after fixing a major bug
- Do an immediate stop-bleeding commit and push.

## 4) Pull Request Rules

- Keep PR scope focused (single concern).
- Include test notes and rollback notes.
- Require passing CI before merge.
- Merge into `dev`, then controlled release to `main`.
- Branch protection recommendation:
  - Protect `main` and `dev`.
  - Require PR reviews + passing `backend-ci`.
  - Disallow direct push to `main`.

## 5) Husky + Commitlint Setup

Already included in project root:

- `package.json`
- `commitlint.config.js`
- `.husky/commit-msg`

Install hooks:

```bash
npm install
```

Then commit message lint runs automatically.
