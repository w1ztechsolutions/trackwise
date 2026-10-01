import json
from datetime import datetime, timedelta, timezone

import pytest
from werkzeug.exceptions import NotFound

from app.models import Business, ImportRun, User, db
from app.services.import_run_service import (
    COMMITTED_STATUS,
    FAILED_STATUS,
    complete_import,
    load_staged,
    normalize_date_order,
    purge_stale_staged_runs,
    stage_import,
    staged_records,
)


ROWS = [
    {'Date': '2026-09-01', 'Description': 'Deposit', 'Amount': 100},
    {'Date': '2026-09-02', 'Description': 'Fee', 'Amount': -15},
]


def _other_business(app):
    business = Business(name='Other Business', currency='MWK')
    db.session.add(business)
    db.session.flush()
    user = User(
        business_id=business.id,
        email='other@example.com',
        password_hash='pbkdf2:sha256:600000$dummy',
        role='admin',
    )
    db.session.add(user)
    db.session.commit()
    return business, user


def _xlsx_cells(data):
    from io import BytesIO
    from xml.etree import ElementTree
    from zipfile import ZipFile

    with ZipFile(BytesIO(data)) as workbook:
        sheet = ElementTree.fromstring(workbook.read('xl/worksheets/sheet1.xml'))
    return [
        (node.text or '') for node in sheet.iter()
        if node.tag.endswith('}t') or node.tag.endswith('}v')
    ]


def test_stage_import_records_the_workload(app, business):
    with app.app_context():
        run = stage_import(
            business.id, app.test_client_user.id, 'bank_statements',
            'statement.xlsx', ROWS, {'date': 'Date'}, date_order='dmy',
        )
        db.session.commit()

        assert run.status == 'staged'
        assert run.row_count == 2
        assert json.loads(run.column_map) == {'date': 'Date'}
        assert run.date_order == 'DMY'
        assert staged_records(run) == ROWS
        assert run.actor_email == app.test_client_user.email
        assert run.completed_at is None


def test_normalize_date_order_falls_back_to_mdy():
    assert normalize_date_order('mdy') == 'MDY'
    assert normalize_date_order('DMY') == 'DMY'
    assert normalize_date_order(None) == 'MDY'
    assert normalize_date_order('nonsense') == 'MDY'
    assert normalize_date_order('') == 'MDY'


def test_complete_import_purges_staged_rows_and_records_counts(app, business):
    with app.app_context():
        run = stage_import(
            business.id, app.test_client_user.id, 'customers', 'customers.xlsx', ROWS,
        )
        db.session.commit()

        complete_import(run, {'imported': 1, 'duplicates': 2, 'errors': ['Row 4: bad']})
        db.session.commit()

        assert run.status == COMMITTED_STATUS
        assert run.staged_rows is None
        assert run.imported_count == 1
        assert run.duplicate_count == 2
        assert run.error_count == 1
        assert json.loads(run.errors) == ['Row 4: bad']
        assert run.completed_at is not None


def test_complete_import_records_a_failure_without_a_result(app, business):
    with app.app_context():
        run = stage_import(
            business.id, app.test_client_user.id, 'customers', 'customers.xlsx', ROWS,
        )
        db.session.commit()

        complete_import(run, status=FAILED_STATUS, error='Upload it again.')
        db.session.commit()

        assert run.status == FAILED_STATUS
        assert run.staged_rows is None
        assert run.imported_count == 0
        assert run.error_count == 1
        assert json.loads(run.errors) == ['Upload it again.']


def test_load_staged_returns_the_owners_run(app, business):
    with app.app_context():
        run = stage_import(
            business.id, app.test_client_user.id, 'suppliers', 'suppliers.xlsx', ROWS,
        )
        db.session.commit()

        assert load_staged(business.id, run.id).id == run.id


def test_load_staged_refuses_another_tenants_run(app, business):
    with app.app_context():
        other, _ = _other_business(app)
        run = stage_import(
            other.id, app.test_client_user.id, 'suppliers', 'suppliers.xlsx', ROWS,
        )
        db.session.commit()

        with pytest.raises(NotFound):
            load_staged(business.id, run.id)


def test_load_staged_refuses_a_completed_run(app, business):
    with app.app_context():
        run = stage_import(
            business.id, app.test_client_user.id, 'suppliers', 'suppliers.xlsx', ROWS,
        )
        db.session.commit()
        complete_import(run, {'imported': 1, 'duplicates': 0, 'errors': []})
        db.session.commit()

        with pytest.raises(NotFound):
            load_staged(business.id, run.id)


def test_load_staged_refuses_a_missing_or_unparsable_id(app, business):
    with app.app_context():
        for run_id in (999999, 'abc', None):
            with pytest.raises(NotFound):
                load_staged(business.id, run_id)


def test_purge_deletes_only_stale_staged_runs(app, business):
    with app.app_context():
        stale = stage_import(
            business.id, app.test_client_user.id, 'suppliers', 'stale.xlsx', ROWS,
        )
        fresh = stage_import(
            business.id, app.test_client_user.id, 'suppliers', 'fresh.xlsx', ROWS,
        )
        committed = stage_import(
            business.id, app.test_client_user.id, 'suppliers', 'committed.xlsx', ROWS,
        )
        failed = stage_import(
            business.id, app.test_client_user.id, 'suppliers', 'failed.xlsx', ROWS,
        )
        db.session.flush()

        stale.created_at = datetime.now(timezone.utc) - timedelta(hours=48)
        complete_import(committed, {'imported': 1, 'duplicates': 0, 'errors': []})
        complete_import(failed, status=FAILED_STATUS, error='nope')
        fresh.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
        db.session.commit()

        assert purge_stale_staged_runs() == 1
        db.session.commit()

        remaining = {run.id for run in ImportRun.query.all()}
        assert remaining == {fresh.id, committed.id, failed.id}


def test_rejected_rows_download_returns_an_xlsx(client, business, app):
    with app.app_context():
        run = stage_import(
            business.id, app.test_client_user.id, 'bank_statements',
            'statement.xlsx', ROWS,
        )
        db.session.commit()
        complete_import(run, {
            'imported': 1,
            'duplicates': 0,
            'errors': ['Row 3: a valid date and amount are required.', 'Unnumbered failure'],
        })
        db.session.commit()

        response = client.get(f'/imports/{run.id}/errors')
        assert response.status_code == 200
        assert response.headers['Content-Disposition'].endswith(
            'filename=statement-rejected-rows.xlsx'
        )
        assert _xlsx_cells(response.data) == [
            'Row', 'Error',
            '3', 'a valid date and amount are required.',
            '', 'Unnumbered failure',
        ]


def test_rejected_rows_download_hides_another_tenants_run(client, business, app):
    with app.app_context():
        other, _ = _other_business(app)
        run = stage_import(
            other.id, app.test_client_user.id, 'bank_statements',
            'other.xlsx', ROWS,
        )
        db.session.commit()
        complete_import(run, {'imported': 0, 'duplicates': 0, 'errors': ['Row 2: bad']})
        db.session.commit()

        assert client.get(f'/imports/{run.id}/errors').status_code == 404
        assert client.get('/imports/999999/errors').status_code == 404


def test_rejected_rows_download_of_a_run_without_errors(client, business, app):
    with app.app_context():
        run = stage_import(
            business.id, app.test_client_user.id, 'customers', 'clean.xlsx', ROWS,
        )
        db.session.commit()
        complete_import(run, {'imported': 2, 'duplicates': 0, 'errors': []})
        db.session.commit()

        response = client.get(f'/imports/{run.id}/errors')
        assert response.status_code == 200
        assert _xlsx_cells(response.data) == ['Row', 'Error']