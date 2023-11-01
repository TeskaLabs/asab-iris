import unittest
from asabiris.formatter.jinja.service import CaseInsensitiveDict


class TestCaseInsensitiveDict(unittest.TestCase):

    def setUp(self):
        self.cid = CaseInsensitiveDict()

    def test_set_and_get(self):
        self.cid['TestKey'] = 'value'
        self.assertEqual(self.cid['testkey'], 'value')
        self.assertEqual(self.cid['TESTKEY'], 'value')
        self.assertEqual(self.cid['TeStKeY'], 'value')

    def test_get_method(self):
        self.cid['Key'] = 'value'
        self.assertEqual(self.cid.get('key'), 'value')
        self.assertEqual(self.cid.get('KEY'), 'value')
        self.assertEqual(self.cid.get('KeY'), 'value')

    def test_update_and_get(self):
        self.cid.update({'AnotherKey': 'another_value'})
        self.assertEqual(self.cid['anotherkey'], 'another_value')
        self.assertEqual(self.cid['ANOTHERKEY'], 'another_value')
        self.assertEqual(self.cid['AnOtHeRkEy'], 'another_value')

    def test_key_error(self):
        with self.assertRaises(KeyError):
            _ = self.cid['nonexistentkey']

    def test_case_insensitive_contains(self):
        self.cid['key'] = 'value'
        self.assertTrue('KEY' in self.cid)
        self.assertTrue('Key' in self.cid)
        self.assertTrue('kEy' in self.cid)

    def test_case_insensitive_del(self):
        self.cid['key'] = 'value'
        del self.cid['KEY']
        self.assertNotIn('key', self.cid)

    def test_case_insensitive_pop(self):
        self.cid['key'] = 'value'
        self.cid.pop('KEY')
        self.assertNotIn('key', self.cid)

    def test_case_insensitive_setdefault(self):
        self.cid.setdefault('key', 'default_value')
        self.assertEqual(self.cid['KEY'], 'default_value')
        self.cid['key'] = 'new_value'
        self.assertEqual(self.cid.setdefault('KEY', 'default_value'), 'new_value')

    def test_case_insensitive_keys(self):
        self.cid['key'] = 'value'
        self.cid['ANOTHERKEY'] = 'another_value'
        keys = list(self.cid.keys())
        self.assertIn('KEY', keys)
        self.assertIn('ANOTHERKEY', keys)

    def test_case_insensitive_values(self):
        self.cid['key'] = 'value'
        self.cid['ANOTHERKEY'] = 'another_value'
        values = list(self.cid.values())
        self.assertIn('value', values)
        self.assertIn('another_value', values)

    def test_case_insensitive_items(self):
        self.cid['key'] = 'value'
        self.cid['ANOTHERKEY'] = 'another_value'
        items = list(self.cid.items())
        self.assertIn(('KEY', 'value'), items)
        self.assertIn(('ANOTHERKEY', 'another_value'), items)


if __name__ == '__main__':
    unittest.main()
