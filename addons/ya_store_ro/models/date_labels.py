"""Deterministic English date labels, independent of server locale."""
from datetime import date

MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


def format_ymondd(value):
    """date/datetime -> 2026-Nov-22; empty value -> empty string."""
    return '%04d-%s-%02d' % (value.year, MONTHS[value.month - 1], value.day) if value else ''


def parse_ymondd(text):
    """Strict 2026-Nov-22 -> date. Reject swapped order or bad dates."""
    if not isinstance(text, str) or len(text) != 11 or text[4] != '-' or text[8] != '-':
        raise ValueError('Expected YYYY-Mon-DD')
    year, month, day = text[:4], text[5:8], text[9:11]
    if not (year.isascii() and year.isdigit() and day.isascii() and day.isdigit()):
        raise ValueError('Invalid date digits')
    if month not in MONTHS:
        raise ValueError('Invalid English month abbreviation')
    result = date(int(year), MONTHS.index(month) + 1, int(day))
    if format_ymondd(result) != text:
        raise ValueError('Invalid date format')
    return result
