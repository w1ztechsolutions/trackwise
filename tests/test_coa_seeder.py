import unittest
from app import create_app
from config import TestingConfig
from models import db, User
from app.models.accounting import Business, ChartOfAccounts
from app.accounting.coa_taxonomy import build_coa_tree, COA_TAXONOMY


class TestCoaTaxonomy(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        self.business = Business(name='Test Business', currency='MWK')
        db.session.add(self.business)
        db.session.flush()
        self.user = User(
            business_id=self.business.id,
            email='admin@test.com',
            password_hash='pbkdf2:sha256:600000$dummy',
            role='admin',
            is_active=True,
        )
        db.session.add(self.user)
        db.session.commit()
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess['_user_id'] = self.user.get_id()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def test_taxonomy_has_all_leaf_accounts(self):
        for major in COA_TAXONOMY:
            for sub in major['subcategories']:
                for atype in sub['account_types']:
                    for acct in atype['accounts']:
                        self.assertIn('code', acct)
                        self.assertIn('name', acct)
                        self.assertIn('type', acct)
                        self.assertIsInstance(acct['code'], str)
                        self.assertTrue(len(acct['code']) >= 4)

    def test_subtotals_generated(self):
        selected = ['1100', '1110', '1120']
        tree = build_coa_tree(selected)
        codes = [a['code'] for a in tree]
        self.assertIn('1199', codes)

    def test_subtotal_no_single_item_groups(self):
        selected = ['1100']
        tree = build_coa_tree(selected)
        codes = [a['code'] for a in tree]
        self.assertNotIn('1199', codes)

    def test_tree_assembly_parents_before_children(self):
        selected = ['1100', '1110', '1120']
        tree = build_coa_tree(selected)
        code_to_idx = {a['code']: i for i, a in enumerate(tree)}
        for i, acct in enumerate(tree):
            if acct.get('parent_code'):
                parent_idx = code_to_idx.get(acct['parent_code'])
                self.assertIsNotNone(parent_idx)
                self.assertLess(parent_idx, i)

    def test_deduplication(self):
        selected = ['1100', '1110']
        existing = ChartOfAccounts(
            business_id=self.business.id, code='1100', name='Product Sales', type='income', is_active=True
        )
        db.session.add(existing)
        db.session.commit()
        tree = build_coa_tree(selected)
        skipped = [a['code'] for a in tree if a['code'] == '1100']
        self.assertEqual(len(skipped), 1)

    def test_import_endpoint(self):
        selected = ['1100', '1110', '1120']
        resp = self.client.post(
            '/accounting/chart-of-accounts/seed',
            json={'selected_codes': selected},
            headers={'Accept': 'application/json'},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('imported', data)
        self.assertGreaterEqual(data['imported'], 3)
        accounts = ChartOfAccounts.query.filter_by(business_id=self.business.id).all()
        codes = [a.code for a in accounts]
        for code in selected:
            self.assertIn(code, codes)

    def test_unauthorized_access(self):
        from config import Config
        class NoLoginConfig(TestingConfig):
            LOGIN_DISABLED = False
            WTF_CSRF_ENABLED = False
        app = create_app(NoLoginConfig)
        with app.app_context():
            db.create_all()
            business = Business(name='Test', currency='MWK')
            db.session.add(business)
            db.session.flush()
            user = User(
                business_id=business.id,
                email='viewer@test.com',
                password_hash='pbkdf2:sha256:600000$dummy',
                role='viewer',
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()
            client = app.test_client()
            with client.session_transaction() as sess:
                sess['_user_id'] = user.get_id()
            resp = client.post(
                '/accounting/chart-of-accounts/seed',
                json={'selected_codes': ['1100']},
                headers={'Accept': 'application/json'},
            )
            self.assertEqual(resp.status_code, 403)

    def test_empty_selection(self):
        resp = self.client.post(
            '/accounting/chart-of-accounts/seed',
            json={'selected_codes': []},
            headers={'Accept': 'application/json'},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['imported'], 0)
        self.assertEqual(data['skipped'], 0)


if __name__ == '__main__':
    unittest.main()
