#!/usr/bin/env python3
"""Run a command with a pseudo-terminal as its stdin, stdout, and stderr; answer prompts.

Usage: pty_run.py [--timeout SECONDS] [--reply 'PROMPT=TEXT']... -- COMMAND [ARGS]
Each reply is sent (with a newline) once, after PROMPT first appears in the terminal output.
The terminal output is printed to stdout; the exit status is the command's.
"""
import os
import pty
import select
import sys
import time


def main(argv):
    timeout, replies = 60.0, []
    while argv and argv[0] != "--":
        flag = argv.pop(0)
        if flag == "--timeout":
            timeout = float(argv.pop(0))
        elif flag == "--reply":
            prompt, _, text = argv.pop(0).partition("=")
            replies.append([prompt, text, False])
        else:
            sys.exit("usage error")
    command = argv[1:]
    pid, master = pty.fork()
    if pid == 0:
        os.execvp(command[0], command)
    output = b""
    deadline = time.monotonic() + timeout
    status = None
    while status is None and time.monotonic() < deadline:
        ready, _, _ = select.select([master], [], [], 0.2)
        if ready:
            try:
                chunk = os.read(master, 4096)
            except OSError:
                chunk = b""
            if chunk:
                output += chunk
        text = output.decode("utf-8", "replace")
        for reply in replies:
            if not reply[2] and reply[0] in text:
                reply[2] = True
                time.sleep(0.1)
                os.write(master, (reply[1] + "\n").encode())
        done, state = os.waitpid(pid, os.WNOHANG)
        if done:
            status = state
    if status is None:
        os.kill(pid, 9)
        os.waitpid(pid, 0)
        sys.stdout.write(output.decode("utf-8", "replace"))
        sys.exit(124)
    try:
        while True:
            chunk = os.read(master, 4096)
            if not chunk:
                break
            output += chunk
    except OSError:
        pass
    sys.stdout.write(output.decode("utf-8", "replace"))
    sys.stdout.flush()
    sys.exit(os.waitstatus_to_exitcode(status))


if __name__ == "__main__":
    main(sys.argv[1:])
