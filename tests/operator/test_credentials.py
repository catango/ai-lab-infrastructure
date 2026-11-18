import io
import unittest
from contextlib import redirect_stderr, redirect_stdout

import helpers  # noqa: F401
from operator_lib import credentials


class PromptToken(unittest.TestCase):
    def test_token_comes_from_getpass_only(self):
        prompts = []
        token = credentials.prompt_token("T3", getpass_fn=lambda prompt: prompts.append(prompt) or "  " + helpers.PAT + "ABCDEFGH12345678  ")
        self.assertEqual(token, helpers.PAT + "ABCDEFGH12345678")
        self.assertIn("T3", prompts[0])

    def test_nothing_is_printed(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            credentials.prompt_token("T3", getpass_fn=lambda _: helpers.PAT + "ABCDEFGH12345678")
        self.assertEqual(out.getvalue() + err.getvalue(), "")

    def test_bad_input_is_refused_without_echoing_it(self):
        for value in ("", "   ", "short", "has space inside token 1234", "x" * 600, "tab\tinside12345678", "new\nline12345678"):
            with self.subTest(length=len(value)), self.assertRaises(credentials.TokenError) as caught:
                credentials.prompt_token("T2", getpass_fn=lambda _: value)
            if value.strip():
                self.assertNotIn(value.strip(), str(caught.exception))

    def test_end_of_input_is_an_error(self):
        def eof(_):
            raise EOFError
        with self.assertRaises(credentials.TokenError):
            credentials.prompt_token("T2", getpass_fn=eof)

    def test_the_environment_is_never_read(self):
        import os
        os.environ["GH_TOKEN"] = helpers.PAT + "FROM_ENVIRONMENT_1234"
        try:
            token = credentials.prompt_token("T2", getpass_fn=lambda _: helpers.PAT + "ABCDEFGH12345678")
        finally:
            del os.environ["GH_TOKEN"]
        self.assertEqual(token, helpers.PAT + "ABCDEFGH12345678")


if __name__ == "__main__":
    unittest.main()
