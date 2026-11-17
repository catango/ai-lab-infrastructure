"""pr-contract: checks a pull request against ADR-003 rules PC-1 to PC-7 (CR-2 design section 6).

Standard library only. PR text (title, body, branch, paths) is untrusted input: it is parsed
with line scanners, never passed to a process, and sanitized before it is printed.
"""
