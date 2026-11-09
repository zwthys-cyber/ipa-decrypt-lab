import unittest
from tf_virtual_resume import wait_until

class StoreCooldownTests(unittest.TestCase):
    def test_cooldown_waits_before_returning_without_an_http_retry(self):
        clock=[1000];slept=[]
        def sleep(seconds):slept.append(seconds);clock[0]+=seconds
        wait_until({"TF_VIRTUAL_NOT_BEFORE":"1031"},now=lambda:clock[0],sleep=sleep)
        self.assertEqual(sum(slept),31)
        self.assertLessEqual(max(slept),15)

    def test_expired_cooldown_is_immediate(self):
        wait_until({"TF_VIRTUAL_NOT_BEFORE":"999"},now=lambda:1000,sleep=lambda _:self.fail())

    def test_missing_or_excessive_wait_is_rejected(self):
        for value in ("","x","2000"):
            with self.assertRaises(ValueError):
                wait_until({"TF_VIRTUAL_NOT_BEFORE":value},now=lambda:1000,sleep=lambda _:self.fail())
