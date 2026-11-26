<!-- PR type: toolchain. Branch: toolchain/<slug>. Rule PC-1 (ADR-003) requires every section below, non-empty. -->
<!-- Every download needs an artifact with a checksum for each architecture listed under the key `architectures` of config/project.yaml (amd64 only at present). Never use curl | sh. -->
<!-- If a path listed under the key `operator_paths` of config/project.yaml changes (the operator scripts and profiles; the value on the base commit counts), add a section "Operator script review" (PC-8): credentials, commands, modes, calls, output, resources, release tag. No identifiers, addresses, or names. -->

## Summary
<!-- Which tools change and why. -->

## Class
<!-- 1, 2, or 3, with a one-line justification. -->

## Manifest changes
<!-- Per tool: old version, new version, install source, architectures covered. -->

## Verification
<!-- How checksums or signatures were verified for each architecture in config/project.yaml. -->

## Validation
<!-- Smoke tests and linters run, and what could not be run. -->

## Checkpoint
<!-- checkpoint:start -->
- [ ] Manifest updated (every architecture in config/project.yaml)
- [ ] Checksums verified
- [ ] Validation run
- [ ] Marked ready for review
<!-- checkpoint:end -->
