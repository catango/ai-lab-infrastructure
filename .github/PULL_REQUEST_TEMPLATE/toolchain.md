<!-- PR type: toolchain. Branch: toolchain/<slug>. Rule PC-1 (ADR-003) requires every section below, non-empty. -->
<!-- Every download needs amd64 and arm64 entries with checksums. Never use curl | sh. -->
<!-- If operator code changes (scripts/operator/, ansible/operator.yml, ansible/roles/operator_*, toolchain/python/operator.lock), add a section "Operator script review" (PC-8): credentials, commands, modes, calls, output, resources, release tag. No identifiers, addresses, or names. -->

## Summary
<!-- Which tools change and why. -->

## Class
<!-- 1, 2, or 3, with a one-line justification. -->

## Manifest changes
<!-- Per tool: old version, new version, install source, architectures covered. -->

## Verification
<!-- How checksums or signatures were verified for amd64 and arm64. -->

## Validation
<!-- Smoke tests and linters run, and what could not be run. -->

## Checkpoint
<!-- checkpoint:start -->
- [ ] Manifest updated (amd64 and arm64)
- [ ] Checksums verified
- [ ] Validation run
- [ ] Marked ready for review
<!-- checkpoint:end -->
