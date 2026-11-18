"""Exit codes (design section 4 rule 8): the same convention as the quality gate."""
OK = 0
FAILED = 1  # a check or a call failed
USAGE = 2  # bad command line
SKIPPED = 77  # a prerequisite (tool or network) is missing
