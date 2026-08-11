# What changed

<!-- One or two sentences. What does this PR do, and why? -->

## Type

- [ ] Feature
- [ ] Bug fix
- [ ] Refactor / chore
- [ ] Docs
- [ ] CI/CD

## How to test

<!-- The exact commands a reviewer should run. -->

```bash
docker compose up --build
# then: ...
```

## Checklist

- [ ] `cd backend && python manage.py test` passes locally
- [ ] `cd frontend && npm run typecheck && npm run build` passes locally
- [ ] New behaviour has tests
- [ ] Migrations are committed (`python manage.py makemigrations --check --dry-run` is clean)
- [ ] README / API docs updated if the API changed
- [ ] No secrets, tokens or `.env` files committed

## Business rules touched

<!-- Delete if not applicable. Call out anything affecting stock, challan
     state transitions, or role permissions - those have dedicated tests. -->

- [ ] Stock movements
- [ ] Challan state machine (draft / confirmed / cancelled)
- [ ] Role permissions
- [ ] None of the above

---

<sub>CI runs lint, the backend test suite against PostgreSQL, the frontend
typecheck and build, and a Docker image build. Test results and coverage are
posted back as a comment on this PR.</sub>
