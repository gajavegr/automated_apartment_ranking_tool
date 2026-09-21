"""Tests for cross-environment data sync (utils/env_sync.py + endpoints).

No Google Sheets / network access: a small in-memory fake stands in for the
gspread worksheet/spreadsheet objects and the GoogleSheetsClient.
"""
import re

import pytest

import config
import web_app
from utils.env_sync import (
    EnvSyncManager, normalize_address, normalize_zillow_url,
)

ADDR = config.SHEET_COLUMNS["address"]
PRICE = config.SHEET_COLUMNS["price"]
BEDS = config.SHEET_COLUMNS["bedrooms"]

BASE_TABS = {
    "main": "Apartment Data",
    "scatter_plot": "Price vs Score",
    "criteria_matrix": "Criteria Matrix",
    "places_of_interest": "Places of Interest",
    "excluded_places": "Excluded Places",
    "user_edits_log": "User Edits Log",
    "settings": "Settings",
}

HEADERS = [ADDR, PRICE, BEDS]


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
def _col_letter_to_index(letter):
    idx = 0
    for ch in letter:
        idx = idx * 26 + (ord(ch.upper()) - ord("A") + 1)
    return idx - 1


class FakeWorksheet:
    def __init__(self, title, headers, rows):
        """rows: list of dicts. A '_zillow' key (if present) makes the address
        cell a HYPERLINK formula."""
        self.title = title
        self.id = abs(hash(title)) % 100000
        self._headers = list(headers)
        self._grid = []  # list of list of cells (scalar or {'f':..,'d':..})
        for row in rows:
            self._grid.append(self._row_to_cells(row))

    def _row_to_cells(self, row):
        cells = []
        zurl = row.get("_zillow")
        for h in self._headers:
            if h == ADDR and zurl:
                addr = row.get(ADDR, "")
                cells.append({"f": f'=HYPERLINK("{zurl}", "{addr}")', "d": addr})
            else:
                cells.append(row.get(h, ""))
        return cells

    @staticmethod
    def _display(cell):
        return cell["d"] if isinstance(cell, dict) else cell

    @staticmethod
    def _formula(cell):
        return cell["f"] if isinstance(cell, dict) else cell

    def row_values(self, n):
        assert n == 1
        return list(self._headers)

    def get_all_records(self):
        records = []
        for cells in self._grid:
            rec = {}
            for i, h in enumerate(self._headers):
                rec[h] = self._display(cells[i]) if i < len(cells) else ""
            records.append(rec)
        return records

    def get(self, a1_range, value_render_option=None):
        # Only single-column ranges like "A2:A5" are used.
        m = re.match(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", a1_range)
        assert m, a1_range
        col = _col_letter_to_index(m.group(1))
        start, end = int(m.group(2)), int(m.group(4))
        out = []
        for r in range(start, end + 1):
            grid_idx = r - 2  # row 2 -> grid[0]
            if 0 <= grid_idx < len(self._grid) and col < len(self._grid[grid_idx]):
                cell = self._grid[grid_idx][col]
                val = self._formula(cell) if value_render_option == "FORMULA" else self._display(cell)
                out.append([val])
            else:
                out.append([])
        return out

    def append_rows(self, rows, value_input_option=None):
        for row in rows:
            cells = list(row) + [""] * (len(self._headers) - len(row))
            self._grid.append(cells[: len(self._headers)])

    def batch_update(self, updates, value_input_option=None):
        for upd in updates:
            m = re.match(r"([A-Z]+)(\d+)", upd["range"])
            col = _col_letter_to_index(m.group(1))
            row = int(m.group(2))
            grid_idx = row - 2
            while len(self._grid) <= grid_idx:
                self._grid.append([""] * len(self._headers))
            value = upd["values"][0][0]
            if isinstance(value, str) and value.startswith("=HYPERLINK("):
                mm = re.search(r'=HYPERLINK\("([^"]+)",\s*"([^"]*)"\)', value)
                self._grid[grid_idx][col] = {"f": value, "d": mm.group(2) if mm else ""}
            else:
                self._grid[grid_idx][col] = value

    def duplicate(self, new_sheet_name=None):
        return FakeWorksheet(new_sheet_name, self._headers, [])


class FakeSpreadsheet:
    def __init__(self, worksheets):
        self._worksheets = {ws.title: ws for ws in worksheets}

    def worksheet(self, name):
        if name not in self._worksheets:
            raise Exception(f"WorksheetNotFound: {name}")
        return self._worksheets[name]


class FakeSheetsClient:
    MAIN_SHEET_NAME = "Apartment Data"  # single-user (no active username)

    def __init__(self, local_ws, peer_ws):
        self.spreadsheet = FakeSpreadsheet([local_ws])
        self._peer_spreadsheet = FakeSpreadsheet([peer_ws])

    @property
    def BASE_TAB_NAMES(self):
        return dict(BASE_TABS)

    @staticmethod
    def scoped_tab_name(base_name, username):
        if username and str(username).strip():
            return f"{str(username).strip()} - {base_name}"
        return base_name

    def open_spreadsheet(self, sheet_id):
        return self._peer_spreadsheet


def make_manager(local_rows, peer_rows, peer_tab="Apartment Data"):
    local_ws = FakeWorksheet("Apartment Data", HEADERS, local_rows)
    peer_ws = FakeWorksheet(peer_tab, HEADERS, peer_rows)
    client = FakeSheetsClient(local_ws, peer_ws)
    mgr = EnvSyncManager(client, peer_sheet_id="peer123",
                         peer_is_multi_user=False, peer_label="production")
    return mgr, client, local_ws, peer_ws


# --------------------------------------------------------------------------- #
# Normalization
# --------------------------------------------------------------------------- #
def test_normalize_address_equivalence():
    assert normalize_address("123 Main St.") == normalize_address("123 main street")
    assert normalize_address("500 W 42nd Ave") == normalize_address("500 west 42nd avenue")


def test_normalize_zillow_prefers_zpid():
    a = "https://www.zillow.com/homedetails/123-Main-St-SF-CA/12345_zpid/"
    b = "https://www.zillow.com/homedetails/different-slug/12345_zpid/?utm=x"
    assert normalize_zillow_url(a) == normalize_zillow_url(b) == "zpid:12345"


# --------------------------------------------------------------------------- #
# Enablement
# --------------------------------------------------------------------------- #
def test_disabled_without_peer_id():
    mgr, *_ = make_manager([], [])
    mgr.peer_sheet_id = ""
    assert mgr.is_enabled() is False
    assert mgr.compute_diff() == {"enabled": False}


# --------------------------------------------------------------------------- #
# Diff
# --------------------------------------------------------------------------- #
def test_diff_categorizes():
    local = [
        {ADDR: "1 Only Here St", PRICE: 1000, BEDS: 1},
        {ADDR: "2 Shared Ave", PRICE: 2000, BEDS: 2},       # identical
        {ADDR: "3 Diff Rd", PRICE: 3000, BEDS: 1},          # differs (beds)
    ]
    peer = [
        {ADDR: "2 Shared Ave", PRICE: 2000, BEDS: 2},
        {ADDR: "3 Diff Rd", PRICE: 3000, BEDS: 3},          # peer has 3 beds
        {ADDR: "4 Only Peer Blvd", PRICE: 4000, BEDS: 2},
    ]
    mgr, *_ = make_manager(local, peer)
    diff = mgr.compute_diff()

    assert diff["enabled"] is True
    assert diff["summary"] == {"only_in_peer": 1, "only_here": 1, "differ": 1, "identical": 1}
    assert diff["only_in_peer"][0]["address"] == "4 Only Peer Blvd"
    assert diff["only_here"][0]["address"] == "1 Only Here St"
    differ = diff["differ"][0]
    assert differ["address"] == "3 Diff Rd"
    assert any(f["column"] == BEDS and f["peer"] == "3" for f in differ["fields"])


def test_diff_matches_by_zpid_despite_address_text():
    z = "https://www.zillow.com/homedetails/whatever/999_zpid/"
    local = [{ADDR: "10 Elm Street", PRICE: 2500, BEDS: 2, "_zillow": z}]
    peer = [{ADDR: "10 Elm St Apt 2", PRICE: 2500, BEDS: 2, "_zillow": z}]
    mgr, *_ = make_manager(local, peer)
    diff = mgr.compute_diff()
    # Same zpid -> matched, not counted as only_in_peer / only_here.
    assert diff["summary"]["only_in_peer"] == 0
    assert diff["summary"]["only_here"] == 0


# --------------------------------------------------------------------------- #
# Apply
# --------------------------------------------------------------------------- #
def test_apply_import_new_appends_and_is_idempotent():
    zurl = "https://www.zillow.com/homedetails/x/555_zpid/"
    local = [{ADDR: "Existing Pl", PRICE: 1000, BEDS: 1}]
    peer = [
        {ADDR: "Existing Pl", PRICE: 1000, BEDS: 1},
        {ADDR: "New Peer St", PRICE: 2200, BEDS: 2, "_zillow": zurl},
    ]
    mgr, client, local_ws, _ = make_manager(local, peer)

    diff = mgr.compute_diff()
    key = diff["only_in_peer"][0]["key"]
    result = mgr.apply_plan({"direction": "import", "snapshot": False, "import_new": [key]})

    assert result["success"] is True
    assert result["summary"]["added"] == 1
    records = local_ws.get_all_records()
    assert any(r[ADDR] == "New Peer St" for r in records)
    # Zillow hyperlink preserved on the imported row.
    formulas = local_ws.get("A2:A3", value_render_option="FORMULA")
    assert any("555_zpid" in (row[0] or "") for row in formulas)

    # Idempotency: re-running the same plan adds nothing.
    result2 = mgr.apply_plan({"direction": "import", "snapshot": False, "import_new": [key]})
    assert result2["summary"]["added"] == 0
    assert len(local_ws.get_all_records()) == len(records)


def test_apply_conflict_keep_peer_updates_row():
    local = [{ADDR: "Shared Rd", PRICE: 3000, BEDS: 1}]
    peer = [{ADDR: "Shared Rd", PRICE: 3500, BEDS: 2}]
    mgr, client, local_ws, _ = make_manager(local, peer)

    diff = mgr.compute_diff()
    key = diff["differ"][0]["key"]

    # keep mine -> no change
    r_mine = mgr.apply_plan({"direction": "import", "snapshot": False,
                             "conflicts": {key: "mine"}})
    assert r_mine["summary"]["updated"] == 0
    assert local_ws.get_all_records()[0][PRICE] == 3000

    # use peer -> row updated
    r_peer = mgr.apply_plan({"direction": "import", "snapshot": False,
                             "conflicts": {key: "peer"}})
    assert r_peer["summary"]["updated"] == 1
    rec = local_ws.get_all_records()[0]
    assert str(rec[PRICE]) == "3500"
    assert str(rec[BEDS]) == "2"


def test_apply_rejects_push_direction():
    mgr, *_ = make_manager([], [])
    result = mgr.apply_plan({"direction": "push"})
    assert result["success"] is False
    assert "import" in result["error"].lower()


def test_apply_snapshots_when_writing():
    local = []
    peer = [{ADDR: "New St", PRICE: 1000, BEDS: 1}]
    mgr, client, local_ws, _ = make_manager(local, peer)
    diff = mgr.compute_diff()
    key = diff["only_in_peer"][0]["key"]
    result = mgr.apply_plan({"direction": "import", "snapshot": True, "import_new": [key]})
    assert result["snapshot"] is not None
    assert result["snapshot"].startswith("Apartment Data - backup")


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
@pytest.fixture
def sync_client(monkeypatch):
    web_app.app.config["TESTING"] = True

    def configure(mgr):
        monkeypatch.setattr(config, "PEER_GOOGLE_SHEET_ID", "peer123")
        monkeypatch.setattr(web_app, "sheets_client", mgr.sheets_client)
        monkeypatch.setattr(web_app, "get_sync_manager", lambda: mgr)

    test_client = web_app.app.test_client()
    with test_client.session_transaction() as sess:
        sess["username"] = "tester"
    return test_client, configure


def test_endpoint_diff_disabled_when_unconfigured(sync_client):
    test_client, _ = sync_client
    # get_sync_manager returns None because PEER id + sheets_client unset here.
    import config as cfg
    cfg_peer = cfg.PEER_GOOGLE_SHEET_ID
    cfg.PEER_GOOGLE_SHEET_ID = ""
    try:
        data = test_client.get("/sync/diff").get_json()
    finally:
        cfg.PEER_GOOGLE_SHEET_ID = cfg_peer
    assert data == {"enabled": False}


def test_endpoint_diff_and_apply(sync_client):
    test_client, configure = sync_client
    local = [{ADDR: "Here Pl", PRICE: 1000, BEDS: 1}]
    peer = [
        {ADDR: "Here Pl", PRICE: 1000, BEDS: 1},
        {ADDR: "Import Me Ave", PRICE: 2000, BEDS: 2},
    ]
    mgr, *_ = make_manager(local, peer)
    configure(mgr)

    diff = test_client.get("/sync/diff").get_json()
    assert diff["success"] is True
    assert diff["summary"]["only_in_peer"] == 1
    key = diff["only_in_peer"][0]["key"]

    resp = test_client.post("/sync/apply", json={
        "direction": "import", "snapshot": False, "import_new": [key],
    })
    result = resp.get_json()
    assert result["success"] is True
    assert result["summary"]["added"] == 1


def test_endpoint_apply_push_rejected(sync_client):
    test_client, configure = sync_client
    mgr, *_ = make_manager([], [])
    configure(mgr)
    resp = test_client.post("/sync/apply", json={"direction": "push"})
    assert resp.status_code == 400
    assert resp.get_json()["success"] is False
