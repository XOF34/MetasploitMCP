import unittest

from prompt_summarizer import build_prompt


class BuildPromptTests(unittest.TestCase):
    def test_prompt_contains_topic_and_source(self):
        result = build_prompt("RCA", "The service failed after the deployment.")
        self.assertIn('acronym "RCA"', result)
        self.assertIn("The service failed after the deployment.", result)
        self.assertIn("main objectives", result)

    def test_prompt_rejects_empty_input(self):
        with self.assertRaises(ValueError):
            build_prompt("", "source")
        with self.assertRaises(ValueError):
            build_prompt("RCA", "  ")


if __name__ == "__main__":
    unittest.main()
