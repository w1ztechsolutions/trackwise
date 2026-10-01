"""Import blueprint: downloadable rejected-row lists for completed imports.

The rejected rows an import produced used to be flashed to the browser and
discarded on redirect. This blueprint serves the full list as an XLSX so a
partially failed import can be corrected and re-uploaded. Rows are only readable
through the owning business; any mismatch is a 404.
"""

import json
import re

from flask import abort, send_file
from flask_login import current_user, login_required

from app.auth.decorators import role_required
from app.models import ImportRun
from app.services.reports.xlsx_export import create_xlsx

from . import imports_bp


XLSX_MIMETYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
_ROW_PREFIX = re.compile(r'^row\s+(\d+)\s*:\s*', re.IGNORECASE)


def _error_row(message):
    """Split a ``Row 12: <message>`` error into a worksheet row and a message."""
    match = _ROW_PREFIX.match(str(message or '').strip())
    if match:
        return int(match.group(1)), str(message)[match.end():]
    return '', str(message or '')


@imports_bp.route('/imports/<int:run_id>/errors')
@login_required
@role_required('admin', 'accountant')
def import_error_download(run_id):
    """Download every row an import rejected as a two-column XLSX."""
    business_id = getattr(current_user, 'business_id', None)
    run = ImportRun.query.filter_by(id=run_id, business_id=business_id).first()
    if run is None:
        abort(404)

    try:
        errors = json.loads(run.errors) if run.errors else []
    except (TypeError, ValueError):
        errors = []
    if not isinstance(errors, list):
        errors = []

    rows = [['Row', 'Error']]
    rows.extend([_error_row(error) for error in errors])

    filename = run.filename or f'import-{run.id}'
    download_name = f'{_safe_stem(filename)}-rejected-rows.xlsx'
    response = send_file(
        create_xlsx(rows, sheet_name='Rejected Rows'),
        mimetype=XLSX_MIMETYPE,
        as_attachment=True,
        download_name=download_name,
    )
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


def _safe_stem(filename):
    stem = str(filename).rsplit('/', 1)[-1].rsplit('\\', 1)[-1]
    stem = stem.rsplit('.', 1)[0] if '.' in stem else stem
    safe = ''.join(character for character in stem if character.isalnum() or character in '-_ ')
    return (safe.strip() or 'import')[:60]