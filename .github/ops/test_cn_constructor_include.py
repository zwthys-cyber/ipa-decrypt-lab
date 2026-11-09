import unittest
from cn_constructor_include import constructor,ENTRY
class CNDormantEntrypoint(unittest.TestCase):
    def test_constructor_kept_and_authorization_entry_removed(self):
        body='static NSMutableURLRequest *PreparedCommerceSession(void);\n'
        self.assertEqual(constructor(body+ENTRY+'SYNTHETIC_ENTRY_BODY'),body)
    def test_ambiguous_or_missing_native_entry_cannot_be_used(self):
        for text in ('',ENTRY,ENTRY+ENTRY):
            with self.assertRaises(ValueError):constructor(text)
