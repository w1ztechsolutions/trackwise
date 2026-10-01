"""Minimal dependency-free XLSX workbook generation for report exports."""

from io import BytesIO
from decimal import Decimal
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


def create_xlsx(rows):
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
            {'name': 'Budget Variance', 'sheetId': '1', f'{{{_REL_NS}}}id': 'rId1'},
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
