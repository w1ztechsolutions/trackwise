"""Minimal dependency-free XLSX workbook generation for report exports."""

from io import BytesIO
from decimal import Decimal
import json
from xml.etree.ElementTree import Element, SubElement, tostring
from zipfile import ZIP_DEFLATED, ZipFile


_MAIN_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
_REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
_PKG_REL_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
_CONTENT_NS = 'http://schemas.openxmlformats.org/package/2006/content-types'


def _column_name(number):
    result = ''
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _worksheet_xml(rows):
    worksheet = Element(f'{{{_MAIN_NS}}}worksheet')
    sheet_data = SubElement(worksheet, f'{{{_MAIN_NS}}}sheetData')
    for row_number, values in enumerate(rows, start=1):
        row = SubElement(sheet_data, f'{{{_MAIN_NS}}}row', {'r': str(row_number)})
        for column_number, value in enumerate(values, start=1):
            cell = SubElement(
                row,
                f'{{{_MAIN_NS}}}c',
                {'r': f'{_column_name(column_number)}{row_number}'},
            )
            if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
                number = format(value, 'f') if isinstance(value, Decimal) else str(value)
                SubElement(cell, f'{{{_MAIN_NS}}}v').text = number
            else:
                cell.set('t', 'inlineStr')
                inline = SubElement(cell, f'{{{_MAIN_NS}}}is')
                SubElement(inline, f'{{{_MAIN_NS}}}t').text = '' if value is None else str(value)
    return tostring(worksheet, encoding='utf-8', xml_declaration=True)


def create_xlsx(rows, sheet_name='Budget Variance'):
    """Create a single-sheet XLSX file with numeric cells kept numeric."""
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as workbook:
        content_types = Element(f'{{{_CONTENT_NS}}}Types')
        SubElement(
            content_types,
            f'{{{_CONTENT_NS}}}Default',
            {'Extension': 'rels', 'ContentType': 'application/vnd.openxmlformats-package.relationships+xml'},
        )
        SubElement(
            content_types,
            f'{{{_CONTENT_NS}}}Default',
            {'Extension': 'xml', 'ContentType': 'application/xml'},
        )
        SubElement(
            content_types,
            f'{{{_CONTENT_NS}}}Override',
            {
                'PartName': '/xl/workbook.xml',
                'ContentType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml',
            },
        )
        SubElement(
            content_types,
            f'{{{_CONTENT_NS}}}Override',
            {
                'PartName': '/xl/worksheets/sheet1.xml',
                'ContentType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml',
            },
        )
        workbook.writestr('[Content_Types].xml', tostring(content_types, encoding='utf-8', xml_declaration=True))

        package_rels = Element(f'{{{_PKG_REL_NS}}}Relationships')
        SubElement(
            package_rels,
            f'{{{_PKG_REL_NS}}}Relationship',
            {
                'Id': 'rId1',
                'Type': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument',
                'Target': 'xl/workbook.xml',
            },
        )
        workbook.writestr('_rels/.rels', tostring(package_rels, encoding='utf-8', xml_declaration=True))

        book = Element(f'{{{_MAIN_NS}}}workbook')
        book.set('xmlns:r', _REL_NS)
        sheets = SubElement(book, f'{{{_MAIN_NS}}}sheets')
        SubElement(
            sheets,
            f'{{{_MAIN_NS}}}sheet',
            {'name': sheet_name[:31], 'sheetId': '1', f'{{{_REL_NS}}}id': 'rId1'},
        )
        workbook.writestr('xl/workbook.xml', tostring(book, encoding='utf-8', xml_declaration=True))

        book_rels = Element(f'{{{_PKG_REL_NS}}}Relationships')
        SubElement(
            book_rels,
            f'{{{_PKG_REL_NS}}}Relationship',
            {
                'Id': 'rId1',
                'Type': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet',
                'Target': 'worksheets/sheet1.xml',
            },
        )
        workbook.writestr('xl/_rels/workbook.xml.rels', tostring(book_rels, encoding='utf-8', xml_declaration=True))
        workbook.writestr('xl/worksheets/sheet1.xml', _worksheet_xml(rows))
    output.seek(0)
    return output


def build_report_rows(report_type, report):
    """Convert a report service result to flat, spreadsheet-friendly rows."""
    if report_type == 'income_statement':
        rows = [['Section', 'Account', 'Amount']]
        for account, amount in report['revenue_by_account'].items():
            rows.append(['Revenue', account, amount])
        rows.extend([
            ['Summary', 'Total revenue', report['total_revenue']],
            ['Summary', 'Cost of goods sold', report['total_cogs']],
            ['Summary', 'Gross profit', report['gross_profit']],
        ])
        for account, amount in report['expenses_by_category'].items():
            rows.append(['Expenses', account, amount])
        rows.extend([
            ['Summary', 'Total expenses', report['total_expenses']],
            ['Summary', 'Pre-tax profit', report['pre_tax_profit']],
            ['Tax estimate', f"Tax ({report['tax_rate']}%)", report['tax_amount']],
            ['Summary', 'Net profit', report['net_profit']],
            ['Note', report['tax_note'], ''],
        ])
        return rows

    if report_type == 'balance_sheet':
        rows = [['Section', 'Account', 'Balance']]
        for section, key in (('Assets', 'assets'), ('Liabilities', 'liabilities'), ('Equity', 'equity')):
            rows.extend([[section, item['account'].name, item['balance']] for item in report[key]])
        rows.extend([
            ['Summary', 'Total assets', report['total_assets']],
            ['Summary', 'Total liabilities', report['total_liabilities']],
            ['Summary', 'Total equity', report['total_equity']],
            ['Summary', 'Difference', report['difference']],
            ['Summary', 'Balanced', 'Yes' if report['is_balanced'] else 'No'],
        ])
        return rows

    if report_type == 'cash_flow':
        rows = [['Section', 'Item', 'Amount']]
        operating = report['operating']
        rows.append(['Operating', 'Net income', operating['net_income']])
        rows.extend([['Operating adjustment', item['name'], item['amount']] for item in operating['adjustments']])
        rows.append(['Operating', 'Total operating', operating['total']])
        investing = report['investing']
        rows.extend([['Investing', item['name'], item['amount']] for item in investing['items']])
        rows.append(['Investing', 'Total investing', investing['total']])
        financing = report['financing']
        rows.extend([['Financing', item['name'], item['amount']] for item in financing['items']])
        rows.extend([
            ['Financing', 'Total financing', financing['total']],
            ['Summary', 'Net cash flow', report['net_cash']],
        ])
        return rows

    if report_type == 'trial_balance':
        rows = [['Account Code', 'Account', 'Type', 'Debit', 'Credit', 'Balance']]
        rows.extend([
            [item['account'].code, item['account'].name, item['account'].type,
             item['debit'], item['credit'], item['balance']]
            for item in report['entries']
        ])
        rows.extend([
            ['', 'Total', '', report['total_debits'], report['total_credits'], ''],
            ['', 'Balanced', 'Yes' if report['is_balanced'] else 'No', '', '', report['difference']],
        ])
        return rows

    if report_type == 'general_ledger':
        rows = [[
            'Date', 'Entry ID', 'Description', 'Reference Type', 'Reference ID',
            'Account Code', 'Account', 'Branch', 'Cost Center', 'Debit', 'Credit',
            'Balance', 'Created By',
        ]]
        rows.extend([
            [
                item['date'].isoformat() if item['date'] else '',
                item['entry_id'], item['description'], item['reference_type'] or '',
                item['reference_id'] or '', item['account'].code, item['account'].name,
                item['branch'].name if item['branch'] else '',
                item['cost_center'].name if item['cost_center'] else '',
                item['debit'], item['credit'], item['balance'], item['created_by_name'],
            ]
            for item in report['entries']
        ])
        return rows

    if report_type == 'cashbook':
        rows = [[
            'Date', 'Entry ID', 'Description', 'Reference Type', 'Reference ID',
            'Account Code', 'Account', 'Debit', 'Credit', 'Balance', 'Created By',
        ]]
        rows.extend([
            [
                item['date'].isoformat() if item['date'] else '',
                item['entry_id'], item['description'], item['reference_type'] or '',
                item['reference_id'] or '', item['account_code'], item['account_name'],
                item['debit'], item['credit'], item['balance'], item['created_by_name'],
            ]
            for item in report['entries']
        ])
        rows.extend([
            ['', '', '', '', '', '', 'Opening balance', '', '', report['opening_balance'], ''],
            ['', '', '', '', '', '', 'Total debits', report['total_debits'], '', '', ''],
            ['', '', '', '', '', '', 'Total credits', '', report['total_credits'], '', ''],
            ['', '', '', '', '', '', 'Net cash flow', report['net_cash_flow'], '', '', ''],
            ['', '', '', '', '', '', 'Closing balance', '', '', report['closing_balance'], ''],
        ])
        return rows

    if report_type in {'ar_aging', 'ap_aging'}:
        party_key = 'customer' if report_type == 'ar_aging' else 'supplier'
        party_label = 'Customer' if report_type == 'ar_aging' else 'Supplier'
        rows = [[party_label, 'Current', '1-30 days', '31-60 days', '61-90+ days', 'Total']]
        rows.extend([
            [
                item[party_key].name, item['current'], item['days_30'],
                item['days_60'], item['days_90'], item['total_balance'],
            ]
            for item in report['aging_data']
        ])
        totals = report['totals']
        rows.append([
            'Total', totals['current'], totals['days_30'], totals['days_60'],
            totals['days_90'], totals['total_balance'],
        ])
        return rows

    if report_type == 'audit_log':
        rows = [[
            'Date / Time', 'User', 'Email', 'Action', 'Table', 'Record ID',
            'Old Values', 'New Values',
        ]]
        rows.extend([
            [
                item['timestamp'].isoformat() if item['timestamp'] else '',
                item['user_name'], item['user_email'], item['action'], item['table_name'],
                item['record_id'] or '',
                json.dumps(item['old_values'], sort_keys=True),
                json.dumps(item['new_values'], sort_keys=True),
            ]
            for item in report['entries']
        ])
        return rows

    raise ValueError(f'Unsupported report type: {report_type}')
