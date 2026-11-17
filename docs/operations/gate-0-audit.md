# Gate 0: Pre-Architecture Audit Checklist

| Field | Value |
|---|---|
| Status | Ready for execution |
| Date | 2026-11-17 |
| Target location | `ai-lab-infrastructure/docs/operations/gate-0-audit.md` |
| Resolves | Q1 (policy), Q2 (tenancy state), Q3 (network), Q-A (SSH key), Q-B (plugin), parts of Spike S2 |
| Related | ADR-002 |

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

### 2.1 Account type (Console)

Open **Billing & Cost Management** and the account upgrade/payment page. Record:

| Check | Result |
|---|---|
| Account type: Free Tier (Always Free only), Free Trial, or Pay As You Go | |
| Any active trial credits remaining? | |
| Any existing budgets or alerts? | |

If the account is **Pay As You Go**, paid resources *can* be created. Compartment quotas become a critical control rather than defense in depth. Record this; it is not a stop.

### 2.2 Home region and availability domains (Cloud Shell)

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

### 2.3 Existing resources (Cloud Shell)

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

### 2.4 Service limits and A1 availability (Console + Cloud Shell)

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

### 2.5 Identity hygiene (Cloud Shell)

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
```
