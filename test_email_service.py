from unittest import TestCase

from email_service import fetch_emails, my_wait_for_verification_email


class Test(TestCase):
    def test_fetch_emails(self):
        my_wait_for_verification_email("admin@para.de5.net")
