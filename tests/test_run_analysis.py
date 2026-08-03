"""Tests for the /run_analysis (batch) and /reanalyze (single) endpoints.

Regression coverage for the "Analyzed 0 apartments" bug: analyze_apartment()
reports failures by *returning* ``{'error': ...}`` rather than raising, and the
batch endpoint used to silently drop those, reporting ``analyzed: 0`` with
``success: true`` and no explanation. These tests pin the contract that every
apartment that was picked up but not scored/written is surfaced in ``failed``.

No Google Sheets / network access: the sheets client and analyzer are faked.
"""
import pytest

import config
import main
import web_app

ADDR_COL = config.SHEET_COLUMNS['address']
AVAIL_COL = config.SHEET_COLUMNS.get('availability_status', 'availability_status')


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class FakeSheetsClient:
    """Minimal stand-in for GoogleSheetsClient used by the endpoints."""

    def __init__(self, apartments=None, records=None, write_error=None):
        self._apartments = apartments or []
        self._records = records if records is not None else []
        self._write_error = write_error
        self.written = []

    # run_analysis
    def get_apartments_needing_analysis(self):
        return self._apartments

    def write_apartment_data(self, row_number, result):
        if self._write_error is not None:
            raise self._write_error
        self.written.append((row_number, result))

    def update_scatter_plot_data(self):
        pass

    def update_criteria_matrix(self, criteria_results):
        pass

    # reanalyze
    def read_main_sheet(self):
        return self._records


def make_analyzer(behaviour):
    """behaviour: 'ok' -> valid result, 'error' -> {'error': ...}, 'raise' -> throws."""

    class _Analyzer:
        def analyze_apartment(self, apartment, *args, **kwargs):
            if behaviour == 'ok':
                return {
                    'address': apartment.get(ADDR_COL),
                    'weighted_score': 82.0,
                    'scorecard': {'components': {}},
                }
            if behaviour == 'error':
                return {'error': 'Could not geocode address'}
            if behaviour == 'raise':
                raise RuntimeError('unexpected boom')
            raise AssertionError(f'unknown behaviour {behaviour!r}')

    return _Analyzer


def apt(row, address, **extra):
    record = {ADDR_COL: address, '_row_number': row, '_analysis_reason': 'no score'}
    record.update(extra)
    return record


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Strip the rate-limiting sleeps so tests run instantly."""
    import time
    monkeypatch.setattr(time, 'sleep', lambda *a, **k: None)


@pytest.fixture
def client(monkeypatch):
    """A logged-in Flask test client. The sheets client / analyzer are injected
    per-test via the returned helper."""
    web_app.app.config['TESTING'] = True

    def configure(sheets_client, analyzer_behaviour):
        monkeypatch.setattr(web_app, 'sheets_client', sheets_client)
        monkeypatch.setattr(main, 'ApartmentAnalyzer', make_analyzer(analyzer_behaviour))

    test_client = web_app.app.test_client()
    with test_client.session_transaction() as sess:
        sess['username'] = 'tester'  # satisfy require_login
    return test_client, configure


# --------------------------------------------------------------------------- #
# /run_analysis
# --------------------------------------------------------------------------- #
def test_run_analysis_all_success(client):
    test_client, configure = client
    sheets = FakeSheetsClient(apartments=[apt(2, '123 Main St')])
    configure(sheets, 'ok')

    data = test_client.post('/run_analysis').get_json()

    assert data['success'] is True
    assert data['found'] == 1
    assert data['analyzed'] == 1
    assert data['failed'] == []
    assert sheets.written == [(2, sheets.written[0][1])]  # was actually written


def test_run_analysis_surfaces_analysis_error(client):
    """The exact bug: a picked-up apartment whose analysis fails must be reported,
    not silently counted as zero."""
    test_client, configure = client
    configure(FakeSheetsClient(apartments=[apt(2, '456 Oak Ave')]), 'error')

    data = test_client.post('/run_analysis').get_json()

    assert data['found'] == 1
    assert data['analyzed'] == 0
    assert len(data['failed']) == 1
    failure = data['failed'][0]
    assert failure['row'] == 2
    assert failure['address'] == '456 Oak Ave'
    assert failure['stage'] == 'analysis'
    assert 'geocode' in failure['reason'].lower()


def test_run_analysis_surfaces_write_failure(client):
    test_client, configure = client
    sheets = FakeSheetsClient(
        apartments=[apt(2, '789 Pine St')],
        write_error=Exception('Sheets 500: backend error'),
    )
    configure(sheets, 'ok')

    data = test_client.post('/run_analysis').get_json()

    assert data['analyzed'] == 0
    assert len(data['failed']) == 1
    assert data['failed'][0]['stage'] == 'write'
    assert 'backend error' in data['failed'][0]['reason']


def test_run_analysis_surfaces_unexpected_exception(client):
    test_client, configure = client
    configure(FakeSheetsClient(apartments=[apt(2, 'Boom Ave')]), 'raise')

    data = test_client.post('/run_analysis').get_json()

    assert data['analyzed'] == 0
    assert len(data['failed']) == 1
    assert 'boom' in data['failed'][0]['reason'].lower()


def test_run_analysis_partial_success(client, monkeypatch):
    """Two apartments, one good one bad: the good one is analyzed, the bad one
    is reported, and the response still succeeds."""
    test_client, configure = client

    class _Mixed:
        def analyze_apartment(self, apartment, *a, **k):
            if apartment.get(ADDR_COL) == 'Good St':
                return {'address': 'Good St', 'weighted_score': 70, 'scorecard': {'components': {}}}
            return {'error': 'no commute data'}

    configure(FakeSheetsClient(apartments=[apt(2, 'Good St'), apt(3, 'Bad St')]), 'ok')
    monkeypatch.setattr(main, 'ApartmentAnalyzer', _Mixed)  # override with mixed behaviour

    data = test_client.post('/run_analysis').get_json()

    assert data['found'] == 2
    assert data['analyzed'] == 1
    assert len(data['failed']) == 1
    assert data['failed'][0]['address'] == 'Bad St'


def test_run_analysis_nothing_to_do(client):
    test_client, configure = client
    configure(FakeSheetsClient(apartments=[]), 'ok')

    data = test_client.post('/run_analysis').get_json()

    assert data['found'] == 0
    assert data['analyzed'] == 0
    assert data['failed'] == []
    assert 'up to date' in data['message'].lower()


def test_run_analysis_never_zero_without_reason(client):
    """Guard the regression directly: if apartments were found but none analyzed,
    there MUST be a failure explaining why (no silent success-with-zero)."""
    test_client, configure = client
    configure(FakeSheetsClient(apartments=[apt(2, 'X'), apt(3, 'Y')]), 'error')

    data = test_client.post('/run_analysis').get_json()

    if data['found'] > 0 and data['analyzed'] == 0:
        assert len(data['failed']) == data['found']


# --------------------------------------------------------------------------- #
# /run_analysis_stream (NDJSON) — the path the Analysis tab actually uses
# --------------------------------------------------------------------------- #
def _stream_events(test_client):
    """POST /run_analysis_stream and parse the NDJSON body into event dicts."""
    import json as _json
    resp = test_client.post('/run_analysis_stream')
    assert resp.status_code == 200
    events = []
    for line in resp.get_data(as_text=True).splitlines():
        line = line.strip()
        if line:
            events.append(_json.loads(line))
    return events


def test_stream_surfaces_analysis_error(client):
    """A returned {'error': ...} (not a raised exception) must still emit an
    `error` event carrying the reason — the streaming variant of the bug."""
    test_client, configure = client
    configure(FakeSheetsClient(apartments=[apt(2, '456 Oak Ave')]), 'error')

    events = _stream_events(test_client)
    by_type = lambda t: [e for e in events if e['type'] == t]

    errors = by_type('error')
    assert len(errors) == 1
    assert errors[0]['fatal'] is False
    assert 'geocode' in errors[0]['message'].lower()

    complete = by_type('complete')[0]
    assert complete['analyzed'] == 0
    assert complete['total'] == 1
    assert 'could not be analyzed' in complete['message'].lower()
    # item marked unsuccessful
    assert by_type('item_done')[0]['success'] is False


def test_stream_success_no_error_events(client):
    test_client, configure = client
    configure(FakeSheetsClient(apartments=[apt(2, '123 Main St')]), 'ok')

    events = _stream_events(test_client)
    assert [e for e in events if e['type'] == 'error'] == []
    complete = [e for e in events if e['type'] == 'complete'][0]
    assert complete['analyzed'] == 1
    assert 'successfully' in complete['message'].lower()


def test_stream_write_failure_surfaces_error(client):
    test_client, configure = client
    configure(
        FakeSheetsClient(apartments=[apt(2, '789 Pine St')],
                         write_error=Exception('Sheets 500: backend error')),
        'ok',
    )
    events = _stream_events(test_client)
    errors = [e for e in events if e['type'] == 'error']
    assert len(errors) == 1
    assert 'backend error' in errors[0]['message']
    assert [e for e in events if e['type'] == 'complete'][0]['analyzed'] == 0


# --------------------------------------------------------------------------- #
# /reanalyze — already surfaces errors (guard that it stays that way)
# --------------------------------------------------------------------------- #
def test_reanalyze_reports_analysis_error(client):
    test_client, configure = client
    records = [apt(2, 'Solo St')]  # row 2 == records[0]
    configure(FakeSheetsClient(records=records), 'error')

    resp = test_client.post('/reanalyze/2')
    data = resp.get_json()

    assert resp.status_code == 500
    assert data['success'] is False
    assert 'geocode' in data['error'].lower()


def test_reanalyze_success(client):
    test_client, configure = client
    sheets = FakeSheetsClient(records=[apt(2, 'Solo St')])
    configure(sheets, 'ok')

    resp = test_client.post('/reanalyze/2')
    data = resp.get_json()

    assert resp.status_code == 200
    assert data['success'] is True
    assert data['weighted_score'] == 82.0
    assert sheets.written  # persisted
