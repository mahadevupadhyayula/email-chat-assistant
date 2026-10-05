# AI Workflow Rules

## Approach
Build incrementally from spec files in `context/specs/`, in the order of `00-build-plan.md`. Implement against the specs and context files — never infer or invent behaviour.

## Scoping Rules
- Work on exactly one unit at a time.
- Implement only what the current spec lists as in scope. Do not "prepare" for future units (no empty tool stubs, no unused tables, no placeholder endpoints).
- Do not refactor unrelated code. Do not combine unrelated system boundaries in one step.
- Install only the dependencies the current spec lists. Add Python deps with `uv add` (or `uv add --dev`), frontend deps with `pnpm add` (or `pnpm add -D`).
- Database changes only through a new Alembic revision (`uv run alembic revision --autogenerate -m "<msg>"`), reviewed by hand before committing.

## When to Split Work
Split a step if it combines: a schema migration + UI work; a new agent tool + a new frontend card type that isn't required to see the tool's result; mailbox mutation logic + unrelated read logic; worker scheduling + API CRUD; or behaviour not defined in the context files. If a change can't be verified end to end in under 15 minutes, it's too big.

## Handling Missing Requirements
- Do not invent product behaviour.
- If a requirement is ambiguous or missing, stop, add it to Open Questions in `progress-tracker.md`, and ask.
- If a third-party API behaves differently than a spec assumes (Gmail, LangGraph, OpenAI), implement the closest faithful behaviour, note the deviation in the spec's unit summary and in `progress-tracker.md` Session Notes.

## Protected Files
Do not modify without explicit instruction:
- `frontend/src/components/ui/*` (shadcn-generated; add new ones only with `pnpm dlx shadcn@latest add <name>`)
- `frontend/src/lib/api/schema.d.ts` (generated — regenerate with `pnpm gen:api`, never hand-edit)
- Applied Alembic revisions in `backend/alembic/versions/` (add new revisions instead)
- `backend/uv.lock`, `frontend/pnpm-lock.yaml` by hand (only via `uv`/`pnpm`)
- `.env` (never read into output, never commit); `.env.example` only when a spec adds a variable
- `context/specs/*` other than marking status — specs change only when the user asks

## Safety Rules for This Product
- Never run code that sends real email, archives or labels against a real Gmail account as part of automated tests. Manual verification against real Gmail is done by the user.
- Never print OAuth tokens, `TOKEN_ENCRYPTION_KEY`, or API keys in logs, test output or summaries.

## Keeping Docs in Sync
Update the relevant context file whenever implementation changes architecture, storage, conventions, or scope (e.g. a new table → architecture.md Data Model; a new SSE event → architecture.md Data Flow + code-standards.md).

## Per-Unit Loop
1. Create branch `unit/NN-kebab-name` from `main`.
2. Read the spec. Mark it In Progress in `progress-tracker.md`.
3. Implement exactly as specified.
4. Write the spec's Required Tests and run them along with the full suite, lint, typecheck and build.
5. Check every Success Criterion and Definition of Done item.
6. Summarise what changed and how the user can manually verify it. Stop and wait for review.
7. After user approval: mark complete in `progress-tracker.md`, commit as `feat(NN): <name>`, merge the branch into `main`.

Prompts the user runs per unit:
```
Implement:  Read context/specs/NN-name.md. Mark it In Progress in context/progress-tracker.md. Implement exactly as specified — nothing beyond its scope. Write and run the Required Tests. Stop when the Definition of Done checklist passes and summarise what to review.
Correct:    The [element] doesn't match the spec. Expected: [spec]. Current: [actual]. Fix only this.
Close:      Unit NN is reviewed and verified. Mark it complete in context/progress-tracker.md and commit as feat(NN): <name>.
```

## Definition of Done (every unit)
- [ ] All spec Success Criteria met
- [ ] Required tests written and passing; full suite passing (`make test`)
- [ ] `make lint` (ruff, ruff format --check, mypy, eslint, tsc) and `make build` pass
- [ ] No invariant in `architecture.md` violated
- [ ] `progress-tracker.md` updated
