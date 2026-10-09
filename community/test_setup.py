import os
import unittest
from unittest.mock import patch
from community import setup as module


class SetupTests(unittest.TestCase):
    def test_preview_preserves_existing_bindings_and_uses_preview_db(self):
        calls = []
        def api(method, path, body=None):
            calls.append((method, path, body))
            if method == 'GET' and '/d1/database?' in path:
                return [{'name': 'knua-community-preview', 'uuid': 'preview-id'}]
            if path.endswith('/query'):
                return [{'success': True}]
            if method == 'GET':
                return {'deployment_configs': {'preview': {'d1_databases': {'OTHER_DB': {'id': 'other-id'}}}, 'production': {'d1_databases': {'COMMUNITY_DB': {'id': 'production-id'}}}}}
            return {}
        with patch.dict(os.environ, {'CLOUDFLARE_ACCOUNT_ID': 'account'}), patch.object(module, 'api', api):
            module.setup('preview')
        patch_body = calls[-1][2]
        self.assertEqual(set(patch_body['deployment_configs']), {'preview'})
        bindings = patch_body['deployment_configs']['preview']['d1_databases']
        self.assertEqual(bindings['OTHER_DB']['id'], 'other-id')
        self.assertEqual(bindings['COMMUNITY_DB']['id'], 'preview-id')
        self.assertFalse(any(method == 'POST' and path.endswith('/d1/database') for method, path, _ in calls))
        schema_calls = [body['sql'] for _, path, body in calls if path.endswith('/query')]
        self.assertTrue(any('AFTER INSERT' in sql and 'END;' in sql for sql in schema_calls))
        self.assertFalse(any('DROP ' in sql for sql in schema_calls))

    def test_permission_failure_does_not_patch_pages(self):
        with patch.dict(os.environ, {'CLOUDFLARE_ACCOUNT_ID': 'account'}), patch.object(module, 'api', side_effect=RuntimeError('D1 permission denied')) as api:
            with self.assertRaises(RuntimeError):
                module.setup('production')
        self.assertEqual(api.call_count, 1)


if __name__ == '__main__':
    unittest.main()
