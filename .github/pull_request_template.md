## Summary

<!-- Brief description of what this PR changes and why -->

## Type of Change

- [ ] Bug fix
- [ ] New feature (schema, agent, report, dashboard)
- [ ] Documentation update
- [ ] Refactor / code quality
- [ ] Security / governance fix
- [ ] CI / infrastructure

## Checklist

- [ ] CI passes locally (`./scripts/ci-check.sh`)
- [ ] No secrets, private keys, or `.env` files in the diff
- [ ] Schema changes are idempotent (`ON_ERROR_STOP=1`, `ON CONFLICT` guards)
- [ ] New agents are registered in `services/agents/tasks.py` and documented in `AGENTS.md`
- [ ] New governed tables have `v_public_*` views with publication/consent gates
- [ ] New report types are added to `REPORT_GENERATORS` and `docs/export-guide.md`
- [ ] No unsupported claims (Venus, AMUSA, Hypercert, Ecocertain) without governed source evidence
- [ ] Seed files are wired into `scripts/seed.sh` or match the `*_pilot_*.sql` glob
- [ ] `AGENTS.md` updated if new commands, env vars, or conventions are introduced

## Notes

<!-- Any additional context, screenshots, or evidence for reviewers -->
