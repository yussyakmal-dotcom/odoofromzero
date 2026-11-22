"""Read-only pure test for YYYY-Mon-DD RO and Packing date format."""
from datetime import date, datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'addons/ya_store_ro/models/date_labels.py'
spec = spec_from_file_location('ya_ro_date_labels', path)
module = module_from_spec(spec)
spec.loader.exec_module(module)

for day, expected in [
    (date(2026, 11, 22), '2026-Nov-22'),
    (date(2026, 1, 2), '2026-Jan-02'),
    (date(2027, 12, 31), '2027-Dec-31'),
]:
    assert module.format_ymondd(day) == expected
    assert module.parse_ymondd(expected) == day
    print('DATE_FORMAT_OK:', expected)

assert module.format_ymondd(datetime(2026, 11, 22, 18, 20)) == '2026-Nov-22'
for bad in ('20261122', 'Nov 22', '2026-11-22', '2026-Nov-32',
            '2026-Foo-22', '2026-nov-22', '2026-Feb-29'):
    try:
        module.parse_ymondd(bad)
    except ValueError:
        print('INVALID_DATE_REJECT_OK:', bad)
    else:
        raise AssertionError('Expected invalid date: %s' % bad)
print('RO_DATE_LABELS_PURE_OK')
