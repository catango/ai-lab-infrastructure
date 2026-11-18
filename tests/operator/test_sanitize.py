import unittest

import helpers  # noqa: F401
from operator_lib import sanitize

SAMPLES = {
    "ocid": helpers.OCID + ".instance.oc1.uk-london-1.anuwgljrabcdefghijklmnopqrstuvwxyz234567",
    "ocid compartment": helpers.OCID + ".compartment.oc1..aaaaaaaabcdefghijklmnopqrstuvwxyz234567",
    "ipv4": "192.0.2.17",
    "ipv6": "2001:db8::1234",
    "ipv6 full": "2001:0db8:0000:0000:0000:0000:0000:0001",
    "ipv6 mapped": "::ffff:192.0.2.1",
    "email": "someone.name+tag" + helpers.AT + "example.org",
}


class Scrub(unittest.TestCase):
    def test_each_identifier_is_removed(self):
        for label, value in SAMPLES.items():
            with self.subTest(label):
                out = sanitize.scrub(f"before {value} after")
                self.assertNotIn(value, out)
                self.assertTrue(out.startswith("before ") and out.endswith(" after"), out)

    def test_several_identifiers_in_one_line(self):
        line = f"{SAMPLES['ocid']} at {SAMPLES['ipv4']} owned by {SAMPLES['email']}"
        out = sanitize.scrub(line)
        for value in (SAMPLES["ocid"], SAMPLES["ipv4"], SAMPLES["email"]):
            self.assertNotIn(value, out)

    def test_plain_text_and_counts_are_unchanged(self):
        for text in ("instances: 2", "limit reached: no", "version 1.2.3"):
            with self.subTest(text=text):
                self.assertEqual(sanitize.scrub(text), text)

    def test_control_characters_are_dropped(self):
        self.assertEqual(sanitize.scrub("a\x1b[31mb\x00c"), "a[31mbc")


class SummaryValues(unittest.TestCase):
    def test_classified_values_pass(self):
        cases = [(True, "yes"), (False, "no"), (0, "0"), (12, "12"), ("yes", "yes"), ("no", "no"), ("unknown", "unknown"),
                 ("47 GB", "47 GB"), ("1024 MB", "1024 MB"), ("3", "3"),
                 ("3.13", "3.13"), ("2.43.0", "2.43.0"), ("6.8", "6.8")]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(sanitize.summary_value(value), expected)

    def test_unclassified_values_become_a_placeholder(self):
        for value in ("host-01.internal", "alice", SAMPLES["ipv4"], SAMPLES["ocid"], "free text here", "1.2.3" + ".4", "1.2.3" + ".4.5", "v1.2", "1.2.x", None, [1], -1, 10**12, 1.5):
            with self.subTest(value=value):
                self.assertEqual(sanitize.summary_value(value), sanitize.PLACEHOLDER)

    def test_summary_lines_use_safe_keys(self):
        lines = sanitize.summary_lines({"instances": 2, "egress_stable": True, "bad key!": "x", "host": "name-1"})
        self.assertEqual(lines[0], "instances: 2")
        self.assertEqual(lines[1], "egress_stable: yes")
        self.assertEqual(lines[2], f"{sanitize.PLACEHOLDER}: {sanitize.PLACEHOLDER}")
        self.assertEqual(lines[3], f"host: {sanitize.PLACEHOLDER}")


if __name__ == "__main__":
    unittest.main()
