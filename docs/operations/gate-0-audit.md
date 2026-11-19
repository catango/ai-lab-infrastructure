# Gate 0: Pre-Architecture Audit Checklist

| Field | Value |
|---|---|
| Status | Ready for execution. The OCI audit of Part 2 is replaced by `facts --scope oci` (CR-18); the manual steps it replaced are in Appendix A |
| Date | 2026-11-17 |
| Updated | 2026-11-19 (CR-18, PR 7a) |
| Target location | `ai-lab-infrastructure/docs/operations/gate-0-audit.md` |
| Resolves | Q1 (policy), Q2 (tenancy state), Q3 (network), Q-A (SSH key), Q-B (plugin), parts of Spike S2 |
| Related | ADR-002, ADR-011, [operator.md](operator.md) |

## Rules for this audit

- **Read-only.** Nothing in this checklist creates, modifies, or deletes anything. If a step seems to require a change, stop and record it as a finding.
- **No Windows tooling.** Use only the OCI Console, OCI Cloud Shell (browser), Claude Desktop settings, and the GitHub web UI.
- **Report summaries only.** When sharing results in chat, report yes/no answers, counts, and sizes. Do **not** paste OCIDs, IP addresses, usernames, emails, or key fingerprints.
- **Stop conditions are binding.** If any check marked **STOP** fails, architecture work pauses until it is resolved.

---

## Part 1: Organizational policy (Q1)

Ask your Claude Enterprise admin and, where needed, IT security or legal. Record answers in writing, such as an email or ticket.

| # | Question | Answer |
|---|---|---|
| 1.1 | Is Claude Code (the Code tab in Claude Desktop) enabled for my Enterprise account? | |
| 1.2 | Are Claude Desktop **SSH sessions** permitted, including to a personally owned cloud VM? | |
| 1.3 | Is it acceptable that the Enterprise inference credential resides on that VM while sessions run? | |
| 1.4 | Is the GitHub plugin permitted, and may I link a **personal machine account** to it? | |
| 1.5 | May code and documents produced with Claude Enterprise be published in **public** personal GitHub repositories? Who owns them? | |
| 1.6 | Is outbound SSH (TCP 22, or an alternative port) from the corporate network/VPN permitted? | |

**STOP** if 1.1, 1.2, or 1.5 is "no". The architecture depends on all three.

---

## Part 2: OCI tenancy state (Q2)

Run the script for the counts and limits, then do the checks the script cannot make.

### 2.1 Account type (Console)

Open **Billing & Cost Management** and the account upgrade/payment page. Record:

| Check | Result |
|---|---|
| Account type: Free Tier (Always Free only), Free Trial, or Pay As You Go | |
| Any active trial credits remaining? | |
| Any existing budgets or alerts? | |

If the account is **Pay As You Go**, paid resources *can* be created. Compartment quotas become a critical control rather than defense in depth. Record this; it is not a stop.


### 2.2 Limits, usage, and resource counts (script)

`facts --scope oci` uses `list`, `get`, and `inspect` calls only, handles no OCI credential, and prints counts and yes/no. In
Cloud Shell it uses the approver's session. Until the lab operator VM exists, this is where it runs (see
[operator.md](operator.md), section 5).

```bash
git -c advice.detachedHead=false clone --branch <release-tag> https://github.com/<owner>/ai-lab-infrastructure.git
cd ai-lab-infrastructure
scripts/operator/facts --scope oci --oci-auth instance_obo_user            # dry run: prints the exact commands first
scripts/operator/facts --scope oci --oci-auth instance_obo_user --apply
```

| Audit item | Where it is in the output |
|---|---|
| Number of availability domains | `availability_domains` |
| Number of compartments | `compartments_total` (and `compartments_readable`) |
| Compute instances, A1 and E2.1.Micro | `instances_total`, `instances_a1`, `instances_micro`, `instances_other` |
| A1 OCPUs and memory, limit against used | `a1_ocpu_used`, `a1_memory_gb_used`, `a1_ocpu_in_instances`, `a1_memory_gb_in_instances` |
| Boot and block volumes, total size, backups | `boot_volumes`, `block_volumes`, `block_storage_gb_total`, `volume_backups` |
| Over the Always Free allowance | `a1_over_free_allowance`, `block_storage_over_free_allowance`, `volume_backups_over_free_allowance` |

A value of `unknown` means a call was denied, failed, or had another page. The script guesses nothing. Do the matching steps
of Appendix A by hand for those values.

**STOP: urgent.** If `a1_over_free_allowance` is `yes` (total A1 use above **2 OCPUs or 12 GB**), record it and resolve it before
anything else. Oracle disables over-allowance A1 instances and deletes them after 30 days in Always Free tenancies.

### 2.3 Still manual (Console and Cloud Shell)

The script does not read these. Use the matching steps in Appendix A.

| Check | Result |
|---|---|
| Home region (Cloud Shell, Appendix A.1) | |
| Object Storage buckets and approximate usage (GB) | |
| Other notable resources (VCNs, load balancers, databases) (Appendix A.2, search query) | |
| Existing compartment quotas (`oci limits quota list`, Appendix A.3) | |
| Number of IAM users, and users with API keys (count) (Appendix A.4) | |
| MFA enabled on the administrator login | |

Any unused API keys found are a finding to remediate later. Do not delete anything now.

---

## Part 3: Spike S2 pre-checks (read-only portion)

| # | Check | Method | Result |
|---|---|---|---|
| S2a | Default identity domain **type** (for example "Free") | Console: **Identity & Security → Domains** | |
| S2a | Do Oracle's docs state that identity propagation trusts / token exchange are supported for this domain type? | Oracle IAM documentation | |
| S2e | Terraform versions offered by Resource Manager | Cloud Shell: `oci resource-manager stack list-terraform-versions --compartment-id "$OCI_TENANCY"` | |

Items S2b, S2c, S2d, and S2f in ADR-002 are documentation research. They will be completed during the ADR-001/ADR-002 follow-up work.

---

## Part 4: Network (Q3)

| Check | Method | Result |
|---|---|---|
| Corporate egress IP stable? | Ask IT, or compare a "what is my IP" web page across days and with/without VPN | |
| Egress differs on VPN vs. office vs. home? | Same | |
| Outbound SSH allowed? | Ask IT (Q1.6). A practical test happens during Spike S1. | |

Do not paste the IP itself into chat. Report only "stable / changes / multiple".

---

## Part 5: Claude Desktop and GitHub plugin (Q-A, Q-B)

| Check | Method | Result |
|---|---|---|
| Claude Desktop version | Help / About | |
| Code tab available | Visual check | |
| "Add SSH connection" visible in the Code environment picker | Visual check only; do not add a host yet | |
| GitHub plugin: installed by admin or by me? | Plugin/connector settings | |
| GitHub plugin: which GitHub account is linked? | Plugin/connector settings | |
| GitHub plugin: can individual tools (merge, review) be disabled? | Plugin/connector settings | |
| Windows built-in OpenSSH client present? Is it permitted under the no-developer-tools rule? (Q-A) | Windows Settings → Optional features; your decision | |

---

## Part 6: GitHub accounts

| Check | Method | Result |
|---|---|---|
| Personal account plan is GitHub Free | GitHub → Settings → Billing and plans | |
| 2FA enabled (passkey preferred) on personal account | GitHub → Settings → Password and authentication | |
| Machine account already exists? | | |
| GitHub Terms of Service on machine accounts reviewed | docs.github.com → Site policy → Terms of Service | |
| Paid Actions or Codespaces spending limit set to $0 | GitHub → Settings → Billing → Budgets/spending limits | |

---

## Part 7: Console-only checks (VO-12, VO-13)

These two open verification items of the CR-18 design (section 9) are read in the Console and in Oracle's documentation. No script
reads them. Record yes/no and numbers only.

| # | Check | Method | Result |
|---|---|---|---|
| VO-12 | Public IPv4 limits: how many ephemeral and reserved addresses the tenancy may hold, and whether an address is kept on stop, start, and in-place replacement of an instance | Console: Limits, Quotas and Usage (Networking), and Oracle's documentation | |
| VO-13 | Alarm behavior (absence detection and whether a 72-hour period is supported, trigger delay, repeat notification, suppression, `groupBy`) and the Always Free limits for alarms and Notifications | Console: Monitoring and Notifications limits, and Oracle's Monitoring documentation | |

---

## Results summary (paste this back into the architecture discussion)

```text
Q1  Policy: 1.1=__ 1.2=__ 1.3=__ 1.4=__ 1.5=__ 1.6=__
Q2  Account type=__  trial credits=__  home region=__  ADs=__
    A1 used: __ OCPU / __ GB (limit 2 / 12)  E2 micro=__  block storage=__ GB  backups=__
    Over-allowance (STOP)? __   Existing quotas? __   Users with API keys=__
S2  Domain type=__  token exchange documented for this type? __  RM Terraform max=__
Q3  Egress IP: stable/changes/multiple=__   SSH outbound allowed? __
Q-A Windows OpenSSH permitted? __
Q-B Plugin installed by=__  linked account=personal/machine/none  per-tool disable possible? __
GH  Plan=Free? __  2FA=__  machine account exists? __  spending limit $0? __
Q2  OCI facts: paste the yes/no and counts of `facts --scope oci` (no identifiers)
VO  VO-12=__  VO-13=__
```


---

## Appendix A: Manual OCI audit (replaced by `facts --scope oci`)

These are the original manual steps of Part 2. They stay valid. Use them for any value the script reports as `unknown`, for the
checks in section 2.3, and to roll back the script (see [operator.md](operator.md), section 6). The numbering below is the
original one (2.2 is A.1, and so on).

### A.1 (was 2.2) Home region and availability domains (Cloud Shell)

Open Cloud Shell from the Console toolbar. It is pre-authenticated and set to the home region.

```bash
# Home region
oci iam region-subscription list \
  --query 'data[?"is-home-region"].{region:"region-name"}' --output table

# Availability domains in the home region
oci iam availability-domain list --query 'data[].name' --output table
```

| Check | Result |
|---|---|
| Home region | |
| Number of availability domains | |

### A.2 (was 2.3) Existing resources (Cloud Shell)

```bash
# Everything not terminated or deleted, across all compartments
oci search resource structured-search \
  --query-text "query all resources where lifeCycleState != 'TERMINATED' && lifeCycleState != 'DELETED'" \
  --query 'data.items[].{type:"resource-type",name:"display-name",state:"lifecycle-state"}' \
  --output table --all
```

For each compute instance found, open it in the Console (or use `oci compute instance get`) and record its shape, OCPUs, and memory.

| Check | Result |
|---|---|
| Number of compute instances (any state except terminated) | |
| Total A1 OCPUs across all instances | |
| Total A1 memory (GB) across all instances | |
| E2.1.Micro instances | |
| Total boot + block volume size (GB) | |
| Number of boot/block volume backups | |
| Object Storage buckets and approximate usage (GB) | |
| Other notable resources (VCNs, load balancers, databases) | |

**STOP: urgent.** If total A1 usage exceeds **2 OCPUs or 12 GB**, record it and resolve it before anything else. Oracle disables over-allowance A1 instances and deletes them after 30 days in Always Free tenancies.

### A.3 (was 2.4) Service limits and A1 availability (Console + Cloud Shell)

Console: open **Governance & Administration → Limits, Quotas and Usage** and filter on Compute. Find the A1 core and memory entries.

```bash
# A1-related limit names and values
oci limits value list --service-name compute \
  --compartment-id "$OCI_TENANCY" --all \
  --query "data[?contains(name,'a1')]" --output table

# Availability per AD (repeat per AD; take the limit name from the output above)
oci limits resource-availability get --service-name compute \
  --limit-name standard-a1-core-count \
  --compartment-id "$OCI_TENANCY" \
  --availability-domain "<AD-name>"
```

If a command errors because a name differs, use the Console view instead and note the difference.

| Check | Result |
|---|---|
| A1 core limit / used / available | |
| A1 memory limit / used / available | |
| Existing compartment quotas (`oci limits quota list --compartment-id "$OCI_TENANCY"`) | |

### A.4 (was 2.5) Identity hygiene (Cloud Shell)

```bash
oci iam user list --all --query 'data[].{name:name,state:"lifecycle-state"}' --output table
oci iam compartment list --all --compartment-id-in-subtree true \
  --query 'data[].{name:name,state:"lifecycle-state"}' --output table
```

For each user, check in the Console whether **API keys** or **auth tokens** exist.

| Check | Result |
|---|---|
| Number of IAM users | |
| Users with API keys (count) | |
| Existing compartments (count, names only if not sensitive) | |
| MFA enabled on the administrator login | |

Any unused API keys found are a finding to remediate later. Do not delete anything now.
