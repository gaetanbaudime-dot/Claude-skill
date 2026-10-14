"""Regression: login verification code is not an account-change OTP.

Synthetic examples only; neither Gmail nor Discord is contacted.
"""
import unittest
from test_codes_reliable import load_codes


class VerifyProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = load_codes()
        cls.c.SECURITES = True

    def test_instagram_verify_profile_email(self):
        body = (
            "Hi sample.daily,\n"
            "Someone tried to log in to your Instagram profile.\n"
            "If this was you, please use the following code to confirm your identity:\n"
            "123456\n"
            "If this wasn't you, please reset your password to secure your account.\n"
            "from Meta\n"
            "This message was sent to sample@example.com."
        )
        result = self.c.classer(
            "Instagram <security@mail.instagram.com>", "Verify your profile",
            body, complets=[body + " Facebook, Threads and Meta Platforms."])
        self.assertEqual(result["decision"], "donner")
        self.assertEqual(result["type"], "connexion")
        self.assertEqual(result["code"], "123456")

    def test_icloud_relayed_same_template(self):
        body = ("Hi sample.daily, Someone tried to log in to your Instagram profile. "
                "If this was you, please use the following code to confirm your identity: 123456. "
                "If this wasn't you, please reset your password.")
        result = self.c.classer(
            "Instagram <no-reply_at_mail_instagram_com_ab12_cd34@icloud.com>",
            "Verify your profile", body, complets=[body])
        self.assertEqual(result["decision"], "donner")

    def test_actual_password_change_still_rejected(self):
        body = ("Hi sample.daily, Enter the following code to reset your password "
                "and change the account login: 123456")
        result = self.c.classer(
            "Instagram <security@mail.instagram.com>", "Verify your profile", body)
        self.assertNotEqual(result["decision"], "donner")

    def test_not_an_instagram_sender(self):
        body = ("Someone tried to log in to your Instagram profile. "
                "Please use the following code to confirm your identity: 123456")
        result = self.c.classer("Unknown <someone@example.org>",
                               "Verify your profile", body)
        self.assertNotEqual(result["decision"], "donner")


if __name__ == "__main__":
    unittest.main()
