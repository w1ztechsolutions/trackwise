"""Dependency-free XLSX parsing for spreadsheet imports.

Mirrors the raw ``zipfile`` + ``xml.etree.ElementTree`` approach used by
:mod:`app.services.reports.xlsx_export` so no new dependency is required.
"""

from decimal import Decimal, InvalidOperation
from io import BytesIO
from datetime import date, datetime, timedelta
from xml.etree.ElementTree import fromstring
from zipfile import BadZipFile, ZipFile


_MAIN_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
_REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
_PKG_REL_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'

EXCEL_EPOCH = date(1899, 12, 30)

SUPPORTED_EXTENSIONS = ('.xlsx',)


class XlsxParseError(ValueError):
    """Raised when an uploaded workbook cannot be parsed."""


def _column_index(reference):
    letters = ''.join(ch for ch in reference if ch.isalpha())
    index = 0
    for character in letters.upper():
        index = index * 26 + (ord(character) - 64)
    return index - 1


def _shared_strings(workbook):
    try:
        raw = workbook.read('xl/sharedStrings.xml')
    except KeyError:
        return []
    root = fromstring(raw)
    strings = []
    for item in root.findall(f'{{{_MAIN_NS}}}si'):
        strings.append(''.join(
            node.text or '' for node in item.iter(f'{{{_MAIN_NS}}}t')
        ))
    return strings


def _sheet_targets(workbook):
    """Return ``(sheet_name, part_path)`` pairs in workbook order."""
    workbook_xml = fromstring(workbook.read('xl/workbook.xml'))
    rels_xml = fromstring(workbook.read('xl/_rels/workbook.xml.rels'))
    rel_targets = {
        rel.get('Id'): rel.get('Target')
        for rel in rels_xml.findall(f'{{{_PKG_REL_NS}}}Relationship')
    }

    targets = []
    for index, sheet in enumerate(
        workbook_xml.findall(f'{{{_MAIN_NS}}}sheets/{{{_MAIN_NS}}}sheet'),
        start=1,
    ):
        rel_id = sheet.get(f'{{{_REL_NS}}}id')
        target = rel_targets.get(rel_id) or f'worksheets/sheet{index}.xml'
        if target.startswith('/'):
            part = target.lstrip('/')
        elif target.startswith('xl/'):
            part = target
        else:
            part = f'xl/{target}'
        targets.append((sheet.get('name') or f'Sheet{index}', part))
    return targets


def _coerce_number(text):
    try:
        return Decimal(text)
    except (InvalidOperation, TypeError, ValueError):
        return None


def _cell_value(cell, shared_strings):
    cell_type = cell.get('t')

    if cell_type == 'inlineStr':
        inline = cell.find(f'{{{_MAIN_NS}}}is')
        if inline is None:
            return ''
        return ''.join(node.text or '' for node in inline.iter(f'{{{_MAIN_NS}}}t'))

    value_node = cell.find(f'{{{_MAIN_NS}}}v')
    if value_node is None or value_node.text is None:
        return ''
    raw = value_node.text

    if cell_type == 's':
        try:
            return shared_strings[int(raw)]
        except (ValueError, IndexError):
            return raw
    if cell_type in ('str', 'e'):
        return raw
    if cell_type == 'b':
        return raw == '1'

    number = _coerce_number(raw)
    return raw if number is None else number


def read_sheet_rows(file_stream):
    """Return the first worksheet of a workbook as a list of row value lists."""
    return _read_worksheet(file_stream, sheet_index=0)


def _read_worksheet(file_stream, sheet_index=0):
    try:
        workbook = ZipFile(BytesIO(file_stream.read()))
    except (BadZipFile, ValueError) as error:
        raise XlsxParseError(
            'That file could not be read as an Excel workbook. Upload a valid .xlsx file.'
        ) from error

    with workbook:
        targets = _sheet_targets(workbook)
        if not targets:
            raise XlsxParseError('That workbook does not contain any worksheets.')
        if sheet_index >= len(targets):
            raise XlsxParseError('That worksheet does not exist in the workbook.')
        try:
            sheet_xml = workbook.read(targets[sheet_index][1])
        except KeyError as error:
            raise XlsxParseError('That worksheet could not be read.') from error
        shared_strings = _shared_strings(workbook)

    sheet = fromstring(sheet_xml)
    rows = []
    for row in sheet.findall(f'{{{_MAIN_NS}}}sheetData/{{{_MAIN_NS}}}row'):
        values = {}
        highest = -1
        for cell in row.findall(f'{{{_MAIN_NS}}}c'):
            position = _column_index(cell.get('r') or '')
            values[position] = _cell_value(cell, shared_strings)
            highest = max(highest, position)
        rows.append([values.get(index, '') for index in range(highest + 1)])

    if not rows:
        return []
    width = max(len(row) for row in rows)
    return [row + [''] * (width - len(row)) for row in rows]


def parse_xlsx_file(file_storage, sheet_index=0):
    """Parse an uploaded workbook into ``(sheet_names, rows)``.

    ``file_storage`` is a Werkzeug ``FileStorage`` (anything exposing ``read``).
    The first row is treated as the header row.
    """
    if file_storage is None:
        raise XlsxParseError('Select a file to import.')

    filename = (getattr(file_storage, 'filename', '') or '').lower()
    if filename and not filename.endswith(SUPPORTED_EXTENSIONS):
        raise XlsxParseError('Only .xlsx files are supported.')

    data = file_storage.read()
    if not data:
        raise XlsxParseError('The uploaded file is empty.')

    try:
        workbook = ZipFile(BytesIO(data))
        with workbook:
            sheet_names = [name for name, _ in _sheet_targets(workbook)]
    except (BadZipFile, KeyError, ValueError) as error:
        raise XlsxParseError(
            'That file could not be read as an Excel workbook. Upload a valid .xlsx file.'
        ) from error

    rows = _read_worksheet(BytesIO(data), sheet_index=sheet_index)
    if not rows:
        return sheet_names, []

    headers = [str(value).strip() for value in rows[0]]
    records = []
    for row in rows[1:]:
        if not any(str(value).strip() for value in row):
            continue
        records.append({
            headers[index] if index < len(headers) and headers[index] else f'column_{index + 1}': value
            for index, value in enumerate(row)
        })
    return sheet_names, records


def normalize_text(value):
    return '' if value is None else str(value).strip()


def parse_date(value):
    """Parse a cell into a date, tolerating Excel serials and ISO strings."""
    if value in (None, ''):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, Decimal):
        return EXCEL_EPOCH + timedelta(days=int(value))
    text = str(value).strip()
    if not text:
        return None
    for pattern in ('%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(text[:10], pattern).date()
        except ValueError:
            continue
    number = _coerce_number(text)
    if number is not None:
        try:
            return EXCEL_EPOCH + timedelta(days=int(number))
        except (OverflowError, ValueError):
            return None
    return None


def parse_decimal(value):
    """Parse a cell into a Decimal, returning None when the value is unusable."""
    if value in (None, ''):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = str(value).strip().replace(',', '')
    if text.startswith('(') and text.endswith(')'):
        text = f'-{text[1:-1]}'
    number = _coerce_number(text)
    return number