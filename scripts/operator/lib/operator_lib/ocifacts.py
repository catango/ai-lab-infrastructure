"""facts, OCI scope (CR-18 design section 5.1, R5; acceptance F-2): limits, usage, and resource counts as counts and yes/no.

Only list, get, and inspect calls reach the OCI CLI, and only through operator_lib.process, which refuses anything else. The
CLI authenticates itself: with the lab operator VM's instance principal (the default) or, in Cloud Shell, with the approver's
session. This module never reads, stores, prompts for, or passes a credential. In Cloud Shell it forwards two plain values
(the path of the session's configuration file and its profile name) so that the CLI can find the session.

A call that is denied, fails, times out, is cut by the output cap, or has another page makes the facts that depend on it
`unknown`. Nothing is guessed. Raw answers (they contain identifiers) go only to the private raw-output directory.
"""
import json
import re
import time

from . import process
from .rawdir import RawDirError

UNKNOWN = "unknown"
AUTH_CHOICES = ("instance_principal", "instance_obo_user")
DEFAULT_AUTH = "instance_principal"
FORWARDED = {"OCI_CLI_CONFIG_FILE": re.compile(r"/[A-Za-z0-9_./-]{1,127}"), "OCI_CLI_PROFILE": re.compile(r"[A-Za-z0-9_-]{1,64}")}

MAX_COMPARTMENTS = 10
MAX_CALLS = 250
PAGE = "500"
CALL_TIMEOUT = 90
TOTAL_SECONDS = 900
MAX_OUTPUT = 2 * 1024 * 1024
RAW_CAP = 24 * 1024 * 1024
CLOCK = time.monotonic

# Always Free allowances stated on Oracle's Always Free page (A1: 2 OCPU and 12 GB; block storage 200 GB; five volume backups).
FREE_A1_OCPU, FREE_A1_MEMORY_GB, FREE_STORAGE_GB, FREE_BACKUPS = 2, 12, 200, 5

COMMON = ("--output", "json", "--connection-timeout", "10", "--read-timeout", "60")
TENANCY, COMPARTMENT, LIMIT, DOMAIN = "<tenancy>", "<compartment>", "<limit>", "<availability-domain>"

# Every command as a template. The static gate check reads these tuples, so each is a plain list of constants.
VERSION = ("oci", "--version")
COMPARTMENTS = ("oci", "iam", "compartment", "list", "--include-root", "--compartment-id-in-subtree", "true", "--access-level", "ACCESSIBLE",
                "--lifecycle-state", "ACTIVE", "--limit", PAGE)
DOMAINS = ("oci", "iam", "availability-domain", "list")
LIMIT_VALUES = ("oci", "limits", "value", "list", "--service-name", "compute", "--compartment-id", TENANCY, "--name", LIMIT, "--limit", PAGE)
AVAILABILITY = ("oci", "limits", "resource-availability", "get", "--service-name", "compute", "--limit-name", LIMIT, "--compartment-id", TENANCY)
AVAILABILITY_AD = AVAILABILITY + ("--availability-domain", DOMAIN)
INSTANCES = ("oci", "compute", "instance", "list", "--compartment-id", COMPARTMENT, "--limit", PAGE)
VOLUMES = ("oci", "bv", "volume", "list", "--compartment-id", COMPARTMENT, "--limit", PAGE)
BOOT_VOLUMES = ("oci", "bv", "boot-volume", "list", "--compartment-id", COMPARTMENT, "--availability-domain", DOMAIN, "--limit", PAGE)
BACKUPS = ("oci", "bv", "backup", "list", "--compartment-id", COMPARTMENT, "--limit", PAGE)
BOOT_BACKUPS = ("oci", "bv", "boot-volume-backup", "list", "--compartment-id", COMPARTMENT, "--limit", PAGE)
IP_RESERVED = ("oci", "network", "public-ip", "list", "--compartment-id", COMPARTMENT, "--scope", "REGION", "--lifetime", "RESERVED", "--limit", PAGE)
IP_EPHEMERAL = ("oci", "network", "public-ip", "list", "--compartment-id", COMPARTMENT, "--scope", "AVAILABILITY_DOMAIN",
                "--availability-domain", DOMAIN, "--lifetime", "EPHEMERAL", "--limit", PAGE)
ALARMS = ("oci", "monitoring", "alarm", "list", "--compartment-id", COMPARTMENT, "--limit", PAGE)
TOPICS = ("oci", "ons", "topic", "list", "--compartment-id", COMPARTMENT, "--limit", PAGE)
SUBSCRIPTIONS = ("oci", "ons", "subscription", "list", "--compartment-id", COMPARTMENT, "--limit", PAGE)
PLAN = (VERSION, COMPARTMENTS, DOMAINS, LIMIT_VALUES, AVAILABILITY, AVAILABILITY_AD, INSTANCES, VOLUMES, BOOT_VOLUMES, BACKUPS, BOOT_BACKUPS,
        IP_RESERVED, IP_EPHEMERAL, ALARMS, TOPICS, SUBSCRIPTIONS)
LIMITS = (("standard-a1-core-count", "a1_ocpu"), ("standard-a1-memory-count", "a1_memory_gb"), ("standard-e2-micro-core-count", "micro_core"))

RESOURCE_KEYS = ("instances_total", "instances_a1", "instances_micro", "instances_other", "a1_ocpu_in_instances", "a1_memory_gb_in_instances",
                 "block_volumes", "boot_volumes", "block_storage_gb_total", "volume_backups", "public_ip_ephemeral", "public_ip_reserved",
                 "public_ip_reserved_assigned", "public_ip_reserved_unassigned", "alarms", "alarms_enabled", "absence_alarms", "topics",
                 "subscriptions", "subscriptions_active", "subscriptions_pending", "subscriptions_email")
_DENIED = re.compile(r'"status":\s*(?:401|403|404)|NotAuthorized|NotAuthenticated|Forbidden', re.IGNORECASE)
_GONE = frozenset({"TERMINATED", "TERMINATING", "DELETED", "DELETING"})
TENANCY_PREFIX = "ocid1.tenancy."


def argv_for(template, auth, subs=None):
    argv = list(template) if template == VERSION else [*template, "--auth", auth, *COMMON]
    return [(subs or {}).get(item, item) for item in argv]


def plan_lines(auth):
    lines = [f"would: read limits, usage, and resource counts with list, get, and inspect calls only, using --auth {auth}:"]
    lines.extend("would: " + json.dumps(argv_for(template, auth)) for template in PLAN)
    lines.append(f"would: repeat the compartment commands for each compartment (at most {MAX_COMPARTMENTS}), the availability-domain commands for each "
                 "availability domain, and the limit commands for each of the three limit names; the placeholders in angle brackets are filled in "
                 "from earlier answers and are never printed")
    lines.append(f"would: make at most {MAX_CALLS} calls one after another, each with a {CALL_TIMEOUT} s timeout, within {TOTAL_SECONDS} s in total")
    if auth == "instance_obo_user":
        lines.append("would: pass only " + " and ".join(FORWARDED) + " from the Cloud Shell environment to the oci command (the values are not printed)")
    lines.append("would: write the raw answers only to the private raw-output directory in the operator's home (mode 700), never to the screen")
    return lines


def forwarded_env(auth, environ):
    """The only environment the CLI gets beyond a minimal one: in Cloud Shell the session's configuration path and profile name."""
    if auth != "instance_obo_user":
        return {}
    env = {}
    for name, pattern in FORWARDED.items():
        value = environ.get(name)
        if value in (None, ""):
            continue
        if not pattern.fullmatch(value) or ".." in value.split("/"):
            raise ValueError(f"{name} is not a plain value; nothing was run")
        env[name] = value
    return env


class Reply:
    def __init__(self, status, data=None, more=False):
        self.status, self.data, self.more = status, data, more


class Client:
    """Runs the commands: sequential, counted, timed, and recorded in the raw-output directory."""

    def __init__(self, runner, auth, env, raw):
        self.runner, self.auth, self.env, self.raw = runner, auth, env, raw
        self.calls = self.denied = self.failed = 0
        self.raw_saved = raw is not None
        self.exhausted = False
        self.deadline = CLOCK() + TOTAL_SECONDS

    def _record(self, template, stdout, stderr):
        if self.raw is None:
            return
        slug = "-".join(item for item in template[1:5] if not item.startswith("-"))
        try:
            self.raw.write(f"{self.calls:03d}-{slug}.json", stdout.encode("utf-8"))
            if stderr:
                self.raw.write(f"{self.calls:03d}-{slug}.err", stderr.encode("utf-8"))
        except RawDirError:
            self.raw_saved = False

    def version(self):
        result = self.runner(argv_for(VERSION, self.auth), timeout=30, max_output=4096, extra_env=self.env)
        self.calls += 1
        match = re.search(r"\b[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\b", result.stdout) if result.returncode == 0 else None
        return match.group(0) if match else UNKNOWN

    def call(self, template, subs=None):
        if self.exhausted or self.calls >= MAX_CALLS or CLOCK() > self.deadline:
            self.exhausted = True
            self.failed += 1
            return Reply("failed")
        argv = argv_for(template, self.auth, subs)
        self.calls += 1
        try:
            result = self.runner(argv, timeout=CALL_TIMEOUT, max_output=MAX_OUTPUT, extra_env=self.env)
        except process.CommandTimeout:
            self.failed += 1
            return Reply("failed")
        self._record(template, result.stdout, result.stderr)
        if result.returncode != 0:
            if _DENIED.search(result.stderr) or _DENIED.search(result.stdout):
                self.denied += 1
                return Reply("denied")
            self.failed += 1
            return Reply("failed")
        try:
            body = json.loads(result.stdout)
        except ValueError:
            body = None
        if result.truncated or not isinstance(body, dict) or "data" not in body:
            self.failed += 1
            return Reply("failed")
        return Reply("ok", body["data"], more=bool(body.get("opc-next-page")))


def _pick(item, *keys):
    for key in keys:
        if isinstance(item, dict) and key in item:
            return item[key]
    return None


def _whole(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float) and value.is_integer() and value >= 0:
        return int(value)
    return None


def _items(reply):
    """The list of objects of a complete answer, or None (not ok, another page, or an unexpected shape). A full page counts as
    another page too, because the documentation does not state the name of the paging key."""
    if reply.status != "ok" or reply.more or not isinstance(reply.data, list) or not all(isinstance(i, dict) for i in reply.data):
        return None
    return None if len(reply.data) >= int(PAGE) else reply.data


def _live(item):
    return str(_pick(item, "lifecycle-state", "lifecycleState") or "").upper() not in _GONE


class Tally:
    def __init__(self, keys):
        self.values = {key: 0 for key in keys}
        self.bad = set()

    def add(self, key, amount=1):
        self.values[key] += amount

    def poison(self, *keys):
        self.bad.update(keys)

    def get(self, key):
        return UNKNOWN if key in self.bad else self.values[key]


def _scan_compartment(client, tally, compartment, domains, state):
    subs = {COMPARTMENT: compartment}
    reply = client.call(INSTANCES, subs)
    if reply.status != "ok":
        return False
    rows = _items(reply)
    if rows is None:
        tally.poison("instances_total", "instances_a1", "instances_micro", "instances_other", "a1_ocpu_in_instances", "a1_memory_gb_in_instances")
        state["instances_complete"] = False
    for row in rows or []:
        if not _live(row):
            continue
        shape = str(_pick(row, "shape") or "")
        tally.add("instances_total")
        state["instance_ids"].append(_pick(row, "id"))
        if shape.startswith("VM.Standard.A1"):
            tally.add("instances_a1")
            config = _pick(row, "shape-config", "shapeConfig")
            ocpus, memory = _whole(_pick(config, "ocpus")), _whole(_pick(config, "memory-in-gbs", "memoryInGBs"))
            if ocpus is None or memory is None:
                tally.poison("a1_ocpu_in_instances", "a1_memory_gb_in_instances")
            else:
                tally.add("a1_ocpu_in_instances", ocpus)
                tally.add("a1_memory_gb_in_instances", memory)
        elif shape == "VM.Standard.E2.1.Micro":
            tally.add("instances_micro")
        else:
            tally.add("instances_other")
    _sized(client, tally, VOLUMES, subs, "block_volumes")
    if domains is None:
        tally.poison("boot_volumes", "block_storage_gb_total", "public_ip_ephemeral")
    for domain in domains or []:
        _sized(client, tally, BOOT_VOLUMES, {**subs, DOMAIN: domain}, "boot_volumes")
    for template in (BACKUPS, BOOT_BACKUPS):
        _counted(client, tally, template, subs, "volume_backups")
    _public_ips(client, tally, subs, domains)
    _alarms(client, tally, subs, state)
    _counted(client, tally, TOPICS, subs, "topics", lambda row: str(_pick(row, "lifecycle-state", "lifecycleState")).upper() == "ACTIVE")
    rows = _items(client.call(SUBSCRIPTIONS, subs))
    if rows is None:
        tally.poison("subscriptions", "subscriptions_active", "subscriptions_pending", "subscriptions_email")
    for row in rows or []:
        if not _live(row):
            continue
        tally.add("subscriptions")
        status = str(_pick(row, "lifecycle-state", "lifecycleState")).upper()
        tally.add("subscriptions_active", status == "ACTIVE")
        tally.add("subscriptions_pending", status == "PENDING")
        tally.add("subscriptions_email", str(_pick(row, "protocol")).upper() == "EMAIL")
    return True


def _counted(client, tally, template, subs, key, keep=_live):
    rows = _items(client.call(template, subs))
    if rows is None:
        tally.poison(key)
        return
    tally.add(key, sum(1 for row in rows if keep(row)))


def _sized(client, tally, template, subs, key):
    rows = _items(client.call(template, subs))
    if rows is None:
        tally.poison(key, "block_storage_gb_total")
        return
    for row in rows:
        if not _live(row):
            continue
        size = _whole(_pick(row, "size-in-gbs", "sizeInGBs"))
        tally.add(key)
        if size is None:
            tally.poison("block_storage_gb_total")
        else:
            tally.add("block_storage_gb_total", size)


def _public_ips(client, tally, subs, domains):
    rows = _items(client.call(IP_RESERVED, subs))
    if rows is None:
        tally.poison("public_ip_reserved", "public_ip_reserved_assigned", "public_ip_reserved_unassigned")
    for row in rows or []:
        status = str(_pick(row, "lifecycle-state", "lifecycleState")).upper()
        if status in _GONE:
            continue
        tally.add("public_ip_reserved")
        tally.add("public_ip_reserved_assigned", status in ("ASSIGNED", "ASSIGNING"))
        tally.add("public_ip_reserved_unassigned", status == "AVAILABLE")
    for domain in domains or []:
        _counted(client, tally, IP_EPHEMERAL, {**subs, DOMAIN: domain}, "public_ip_ephemeral")


def _alarms(client, tally, subs, state):
    rows = _items(client.call(ALARMS, subs))
    if rows is None:
        tally.poison("alarms", "alarms_enabled", "absence_alarms")
        state["alarms_complete"] = False
        return
    for row in rows:
        if not _live(row):
            continue
        enabled = _pick(row, "is-enabled", "isEnabled") is True
        tally.add("alarms")
        tally.add("alarms_enabled", enabled)
        query = _pick(row, "query")
        if not isinstance(query, str):
            state["alarms_complete"] = False
        elif enabled and _pick(row, "namespace") == "oci_computeagent" and "CpuUtilization" in query and "absent(" in query:
            tally.add("absence_alarms")
            state["absence_queries"].append(query)


def _limit(client, tenancy, name, prefix):
    keys = (f"{prefix}_limit_per_ad", f"{prefix}_used", f"{prefix}_available_best_ad")
    subs = {TENANCY: tenancy, LIMIT: name}
    rows = _items(client.call(LIMIT_VALUES, subs))
    rows = [row for row in rows or [] if _pick(row, "name") == name]
    if not rows:
        return dict.fromkeys(keys, UNKNOWN)
    limits, used, available = [], [], []
    for row in rows:
        value, scope = _whole(_pick(row, "value")), _pick(row, "scope-type", "scopeType")
        domain = _pick(row, "availability-domain", "availabilityDomain")
        if value is None or (scope == "AD" and not isinstance(domain, str)):
            return dict.fromkeys(keys, UNKNOWN)
        reply = client.call(AVAILABILITY_AD if scope == "AD" else AVAILABILITY, {**subs, DOMAIN: domain})
        data = reply.data if reply.status == "ok" else None
        row_used, row_available = _whole(_pick(data, "used")), _whole(_pick(data, "available"))
        if row_used is None or row_available is None:
            return dict.fromkeys(keys, UNKNOWN)
        limits.append(value)
        used.append(row_used)
        available.append(row_available)
    return dict(zip(keys, (max(limits), sum(used), max(available))))


def _over(value, allowance):
    return None if not isinstance(value, int) else value > allowance


def _verdict(*flags):
    if any(flag is True for flag in flags):
        return "yes"
    return "no" if all(flag is False for flag in flags) else UNKNOWN


def _tenancy_and_compartments(rows):
    tenancy = next((_pick(r, "id") for r in rows if str(_pick(r, "id")).startswith(TENANCY_PREFIX)), None)
    if tenancy is None:
        tenancy = next((_pick(r, "compartment-id", "compartmentId") for r in rows if str(_pick(r, "compartment-id", "compartmentId")).startswith(TENANCY_PREFIX)), None)
    others = [_pick(r, "id") for r in rows if isinstance(_pick(r, "id"), str) and _pick(r, "id") != tenancy]
    return tenancy, others


def collect(runner, auth, env, raw):
    """Run the commands and return (facts, tenancy_resolved). The facts are counts, yes/no, and unknown."""
    client = Client(runner, auth, env, raw)
    facts = {"oci_cli_version": client.version()}
    reply = client.call(COMPARTMENTS)
    rows = _items(reply)
    tenancy, others = _tenancy_and_compartments(rows or [])
    if tenancy is None:
        facts.update({"tenancy_resolved": "no", "calls_made": client.calls, "calls_denied": client.denied, "calls_failed": client.failed})
        return facts, False
    targets = ([tenancy] + others)
    scanned = targets[:MAX_COMPARTMENTS]
    domain_rows = _items(client.call(DOMAINS))
    domains = None if domain_rows is None else [d for d in (_pick(r, "name") for r in domain_rows) if isinstance(d, str)]
    facts["availability_domains"] = UNKNOWN if domains is None else len(domains)
    limit_facts = {}
    for name, prefix in LIMITS:
        limit_facts.update(_limit(client, tenancy, name, prefix))
    tally = Tally(RESOURCE_KEYS)
    state = {"instance_ids": [], "absence_queries": [], "instances_complete": True, "alarms_complete": True}
    readable = sum(1 for compartment in scanned if _scan_compartment(client, tally, compartment, domains, state))
    if readable == 0:
        tally.poison(*RESOURCE_KEYS)
    facts.update({"tenancy_resolved": "yes", "compartments_total": len(targets), "compartments_readable": readable,
                  "compartments_unreadable": len(scanned) - readable, "compartments_truncated": "yes" if len(targets) > len(scanned) else "no"})
    facts.update(limit_facts)
    facts["a1_over_free_allowance"] = _verdict(_over(limit_facts["a1_ocpu_used"], FREE_A1_OCPU), _over(limit_facts["a1_memory_gb_used"], FREE_A1_MEMORY_GB))
    for key in ("instances_total", "instances_a1", "instances_micro", "instances_other", "a1_ocpu_in_instances", "a1_memory_gb_in_instances",
                "block_volumes", "boot_volumes", "block_storage_gb_total"):
        facts[key] = tally.get(key)
    facts["block_storage_over_free_allowance"] = _verdict(_over(facts["block_storage_gb_total"], FREE_STORAGE_GB))
    facts["volume_backups"] = tally.get("volume_backups")
    facts["volume_backups_over_free_allowance"] = _verdict(_over(facts["volume_backups"], FREE_BACKUPS))
    for key in ("public_ip_ephemeral", "public_ip_reserved", "public_ip_reserved_assigned", "public_ip_reserved_unassigned",
                "alarms", "alarms_enabled", "absence_alarms"):
        facts[key] = tally.get(key)
    complete = readable > 0 and state["instances_complete"] and state["alarms_complete"] and not tally.bad & {"instances_total", "alarms"}
    covered = sum(1 for _id in state["instance_ids"] if any(_id in query for query in state["absence_queries"])) if complete else None
    facts["instances_with_absence_alarm"] = UNKNOWN if covered is None else covered
    facts["instances_without_absence_alarm"] = UNKNOWN if covered is None else len(state["instance_ids"]) - covered
    for key in ("topics", "subscriptions", "subscriptions_active", "subscriptions_pending", "subscriptions_email"):
        facts[key] = tally.get(key)
    facts.update({"calls_made": client.calls, "calls_denied": client.denied, "calls_failed": client.failed,
                  "budget_exhausted": "yes" if client.exhausted else "no", "raw_saved": "yes" if client.raw_saved else "no"})
    return facts, True
