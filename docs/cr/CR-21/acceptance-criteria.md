# CR-21 Acceptance criteria

Verified by the implementation PR. "CI" means a green run of the named check.

| ID | Criterion | Evidence |
|---|---|---|
| A-1 | A PR that changes a path in the operator set and has no section "Operator script review" fails `pr-contract` with a message naming PC-8. | Test with a fixture PR, in CI (`gate-tests`) |
| A-2 | The same PR with the section present but empty, or holding only a template comment, fails. | Fixture tests |
| A-3 | The same PR with a non-empty section passes PC-8. | Fixture test |
| A-4 | A PR that changes no path in the operator set passes PC-8 whether or not it has the section. | Fixture test |
| A-5 | Each path form of the operator set triggers the rule: `scripts/operator/`, `ansible/operator.yml`, `ansible/roles/operator_*/`, and `toolchain/python/operator.lock`. | Fixture tests per path |
| A-6 | The failure output contains the rule ID and the section title and none of the PR text. | Fixture test |
| A-7 | A Dependabot PR that changes an operator path is exempt from PC-8 (Q3). | Fixture test |
| A-8 | PC-1 to PC-7 give the same results as before on their existing fixtures. | Existing tests |
| A-9 | The implementation, change, toolchain, and infra templates carry the hint comment, and PC-1 still passes on an untouched template. | Template tests |
