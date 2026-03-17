# Dibble Frontend

React + Vite + TypeScript frontend for the revised learner workflow surfaces defined in:

- `planning/4 - revised-spec/*`
- `planning/5 - dev-handoff-revised-spec/*`
- `planning/current-backend-gap-analysis.md`

## Frontend Standards

- Use Tailwind CSS for layout, tokens, spacing, and visual states.
- Use shadcn-style repo-owned primitives in `src/components/ui/*`.
- Keep domain workflow components separate from UI primitives.
- Keep API contracts, payload shaping, and formatting logic out of view components.
- Prefer explicit, modular composition over clever abstraction.

## Runtime Requirements

- Node `22.14.0` or newer is required.
- The repo pins Node for common toolchains with both `.nvmrc` and `.node-version`.
- `package.json` also includes a Volta pin for Node `22.14.0` and npm `11.7.0`.
- The frontend is authored as ES modules:
  - `package.json` sets `"type": "module"`
  - TypeScript is configured for `"module": "ESNext"`
  - Vite config uses native `import` / `export`

If tooling throws `Cannot use import statement outside a module` or fails on newer syntax, verify the runner is actually using Node 22 rather than an older shell-managed Node binary.

## Local Development

```bash
cd frontend
nvm use
npm install
npm run dev
```

If `nvm` is not active in your shell, use the explicit Node 22 path:

```bash
PATH=/Users/sfw/.nvm/versions/node/v22.14.0/bin:$PATH npm run dev
```

## Verification

```bash
cd frontend
PATH=/Users/sfw/.nvm/versions/node/v22.14.0/bin:$PATH npm run test:run
PATH=/Users/sfw/.nvm/versions/node/v22.14.0/bin:$PATH npm run lint
PATH=/Users/sfw/.nvm/versions/node/v22.14.0/bin:$PATH npm run build
```

The test suite uses Vitest + jsdom + React Testing Library and is intended to grow alongside feature work rather than being deferred until the UI is "done."

## Current Surfaces

- learner summary and `current_flow`
- generated content workflow summaries
- Socratic session summaries
- remediation session summaries
- teacher-facing explainability and intervention-oriented contract gap callouts

## Notes

- Demo fallback data is available so the UI can still be exercised when backend endpoints are unavailable.
- The styling foundation is Tailwind + shadcn-style primitives, with some earlier app-shell CSS still present during the migration.
