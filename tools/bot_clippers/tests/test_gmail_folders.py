"""Regression coverage for localized Gmail folder discovery.

These tests perform no Gmail network access or delivery of real 2FA codes.
"""
import unittest
from test_codes_reliable import load_codes


class GmailFoldersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codes = load_codes()

    def test_localized_gmail_all_mail_and_spam(self):
        lines = [
            b'(\\HasNoChildren) "/" "INBOX"',
            b'(\\HasNoChildren \\All) "/" "[Gmail]/Tous les messages"',
            b'(\\HasNoChildren \\Junk) "/" "[Gmail]/Spam"',
        ]
        found = self.codes._dossiers_speciaux(lines)
        self.assertEqual(found["all"], "[Gmail]/Tous les messages")
        self.assertEqual(found["spam"], "[Gmail]/Spam")
        reader = self.codes.Lecteur()
        reader.speciales = found
        self.assertEqual(reader.dossiers(),
                         ["INBOX", "[Gmail]/Tous les messages", "[Gmail]/Spam"])

    def test_does_not_guess_missing_all_mail(self):
        reader = self.codes.Lecteur()
        reader.speciales = {"spam": "[Gmail]/Spam"}
        self.assertNotIn("[Gmail]/All Mail", reader.dossiers())
        self.assertEqual(reader.dossiers()[0], "INBOX")

    def test_no_duplicate_when_folder_matches_inbox(self):
        reader = self.codes.Lecteur()
        reader.speciales = {"all": "INBOX", "spam": "[Gmail]/Spam"}
        self.assertEqual(reader.dossiers().count("INBOX"), 1)


if __name__ == "__main__":
    unittest.main()
