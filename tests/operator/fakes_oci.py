"""Fakes for the OCI scope tests: a recording stub `oci` command (started through process.run's path parameter) and canary data.

Every identifier-shaped value is assembled at run time, so that no OCID, address, or email appears in the repository."""
import json
import os
import stat
import sys

import helpers

KINDS = ("tenancy", "compartment", "instance")


def ident(kind, name):
    return f"{helpers.OCID}.{kind}.oc1..{name}"


TENANCY = ident("tenancy", "canarytenancy")
LAB = ident("compartment", "canarylab")
INST_A1 = ident("instance", "canarya1")
INST_MICRO = ident("instance", "canarymicro")
ADS = ("canary:UK-LONDON-1-AD-1", "canary:UK-LONDON-1-AD-2", "canary:UK-LONDON-1-AD-3")
IP_ADDRESS = ".".join(("192", "0", "2", "55"))
EMAIL = "ops" + helpers.AT + "example.invalid"
NAME = "canary-instance-name"
CANARIES = (TENANCY, LAB, INST_A1, INST_MICRO, IP_ADDRESS, EMAIL, NAME, helpers.OCID, *ADS)

STUB = """#!PYTHON
import json, os, sys, time
here = os.path.dirname(os.path.realpath(__file__))
argv = sys.argv[1:]
with open(os.path.join(here, "calls.jsonl"), "a") as log:
    log.write(json.dumps({"argv": argv, "env": dict(os.environ)}) + "\\n")
with open(os.path.join(here, "responses.json")) as handle:
    responses = json.load(handle)
for entry in responses:
    if all(token in argv for token in entry["match"]):
        time.sleep(entry.get("sleep", 0))
        if "big" in entry:
            sys.stdout.write("x" * entry["big"])
        elif "raw" in entry:
            sys.stdout.write(entry["raw"])
        else:
            sys.stdout.write(json.dumps(entry.get("out")))
        sys.stderr.write(entry.get("err", ""))
        sys.exit(entry.get("code", 0))
sys.stderr.write('ServiceError:\\n{"code": "NotAuthorizedOrNotFound", "status": 404, "message": "unmatched"}\\n')
sys.exit(1)
"""

DENIED = {"code": 1, "err": 'ServiceError:\n{"code": "NotAuthorizedOrNotFound", "status": 404, "message": "denied"}\n', "out": None}


class Stub:
    """A directory holding an executable named oci. Responses are matched by tokens that must all appear in the arguments."""

    def __init__(self, directory):
        self.dir = str(directory)
        path = os.path.join(self.dir, "oci")
        with open(path, "w") as handle:
            handle.write(STUB.replace("PYTHON", sys.executable + " -S", 1))
        os.chmod(path, stat.S_IRWXU)
        self.set(default_responses())

    def set(self, responses):
        with open(os.path.join(self.dir, "responses.json"), "w") as handle:
            json.dump(list(responses.values()) if isinstance(responses, dict) else responses, handle)

    def calls(self):
        path = os.path.join(self.dir, "calls.jsonl")
        if not os.path.exists(path):
            return []
        with open(path) as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def argvs(self):
        return [["oci"] + call["argv"] for call in self.calls()]


def entry(match, out=None, **extra):
    """A successful answer. An empty list is printed the way oci-cli 3.96 prints it: nothing at all (its renderer leaves out the
    `data` key when the list is empty, and prints nothing when no response header is shown either)."""
    if not out:
        return {"match": list(match), "raw": "", **extra}
    return {"match": list(match), "out": {"data": out}, **extra}


def compartment(identifier, parent, name="canary-name"):
    return {"id": identifier, "name": name, "compartment-id": parent, "lifecycle-state": "ACTIVE"}


def default_responses():
    """A small Always Free style tenancy: 1 A1 instance (2 OCPU, 12 GB), 1 micro instance, one lab compartment."""
    responses = {
        "version": {"match": ["--version"], "raw": "3.96.3\n"},
        "compartments": entry(["iam", "compartment", "list"], [compartment(TENANCY, None, "canary-root"), compartment(LAB, TENANCY)]),
        "domains": entry(["iam", "availability-domain", "list"], [{"name": ad, "id": ident("tenancy", "ad")} for ad in ADS]),
    }
    limits = {"standard-a1-core-count": (16, (2, 0, 0)), "standard-a1-memory-count": (96, (12, 0, 0)), "standard-e2-micro-core-count": (2, (1, 0, 0))}
    for name, (limit, used) in limits.items():
        responses[f"value-{name}"] = entry(["limits", "value", "list", name],
                                          [{"name": name, "scope-type": "AD", "availability-domain": ad, "value": limit} for ad in ADS])
        for ad, amount in zip(ADS, used):
            responses[f"avail-{name}-{ad}"] = entry(["limits", "resource-availability", "get", name, ad], {"available": limit - amount, "used": amount})
    shape = {"id": INST_A1, "display-name": NAME, "shape": "VM.Standard.A1.Flex", "lifecycle-state": "RUNNING",
             "shape-config": {"ocpus": 2.0, "memory-in-gbs": 12.0}}
    micro = {"id": INST_MICRO, "display-name": NAME, "shape": "VM.Standard.E2.1.Micro", "lifecycle-state": "STOPPED", "shape-config": {"ocpus": 1.0, "memory-in-gbs": 1.0}}
    gone = {"id": ident("instance", "gone"), "display-name": NAME, "shape": "VM.Standard.A1.Flex", "lifecycle-state": "TERMINATED",
            "shape-config": {"ocpus": 4.0, "memory-in-gbs": 24.0}}
    responses["instances"] = entry(["compute", "instance", "list", LAB], [shape, micro, gone])
    responses["volumes"] = entry(["bv", "volume", "list", LAB], [{"size-in-gbs": 50, "lifecycle-state": "AVAILABLE"}, {"size-in-gbs": 99, "lifecycle-state": "TERMINATED"}])
    responses["boot-ad1"] = entry(["bv", "boot-volume", "list", LAB, ADS[0]], [{"size-in-gbs": 47, "lifecycle-state": "AVAILABLE"}, {"size-in-gbs": 47, "lifecycle-state": "AVAILABLE"}])
    responses["backups"] = entry(["bv", "backup", "list", LAB], [{"lifecycle-state": "AVAILABLE"}, {"lifecycle-state": "TERMINATED"}])
    responses["boot-backups"] = entry(["bv", "boot-volume-backup", "list", LAB], [{"lifecycle-state": "AVAILABLE"}])
    responses["ip-reserved"] = entry(["network", "public-ip", "list", LAB, "RESERVED"],
                                     [{"lifetime": "RESERVED", "lifecycle-state": "ASSIGNED", "ip-address": IP_ADDRESS}, {"lifetime": "RESERVED", "lifecycle-state": "AVAILABLE", "ip-address": IP_ADDRESS}])
    responses["ip-ephemeral"] = entry(["network", "public-ip", "list", LAB, "EPHEMERAL", ADS[0]], [{"lifetime": "EPHEMERAL", "lifecycle-state": "ASSIGNED", "ip-address": IP_ADDRESS}])
    absence = f'CpuUtilization[1m]{{resourceId = "{INST_A1}"}}.absent()'
    responses["alarms"] = entry(["monitoring", "alarm", "list", LAB], [
        {"namespace": "oci_computeagent", "query": absence, "is-enabled": True, "lifecycle-state": "ACTIVE", "display-name": NAME},
        {"namespace": "oci_computeagent", "query": absence.replace(INST_A1, INST_MICRO), "is-enabled": False, "lifecycle-state": "ACTIVE"},
        {"namespace": "oci_computeagent", "query": "CpuUtilization[1m].mean() > 90", "is-enabled": True, "lifecycle-state": "ACTIVE"}])
    responses["topics"] = entry(["ons", "topic", "list", LAB], [{"lifecycle-state": "ACTIVE", "name": NAME}])
    responses["subscriptions"] = entry(["ons", "subscription", "list", LAB], [
        {"protocol": "EMAIL", "lifecycle-state": "ACTIVE", "endpoint": EMAIL}, {"protocol": "EMAIL", "lifecycle-state": "PENDING", "endpoint": EMAIL}])
    for key, match in (("instances-any", ["compute", "instance", "list"]), ("volumes-any", ["bv", "volume", "list"]), ("boot-any", ["bv", "boot-volume", "list"]),
                       ("backups-any", ["bv", "backup", "list"]), ("boot-backups-any", ["bv", "boot-volume-backup", "list"]),
                       ("ip-any", ["network", "public-ip", "list"]), ("alarms-any", ["monitoring", "alarm", "list"]),
                       ("topics-any", ["ons", "topic", "list"]), ("subscriptions-any", ["ons", "subscription", "list"])):
        responses[key] = entry(match)
    return responses
