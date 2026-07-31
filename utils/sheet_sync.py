"""
Cross-environment data sync (issue #8).

Detect data mismatches between this deployment's Google Sheet and a *peer*
environment's sheet, and reconcile them.

Topology this is designed for (see README / issue #8):
  - Production: single-user, uses BASE tab names ("Apartment Data", ...) on the
    prod sheet.
  - Staging: multi-user, uses PER-USER tabs ("<username> - Apartment Data", ...)
    on a different sheet.
The shared service account is already an Editor on both sheets, so a single
deployment can open both and translate between the two tab-naming schemes.

The "local" side is always the current deployment's sheet, scoped to the active
user (via GoogleSheetsClient's per-user context). The "peer" side is assumed to
use BASE (un-namespaced) tab names — i.e. the peer is a single-dataset/prod-style
sheet. This matches the primary use case: a staging user importing their data
from prod.

Directions:
  - "import"  (peer -> me):  the primary, well-defined case.
  - "push"    (me -> peer):  collapses this user's data into the peer's single
                             dataset; risky, so gated behind explicit confirmation.

Matching key: normalized embedded Zillow URL, falling back to normalized address.
Records that share EITHER key are treated as the same apartment.

Apply is additive by default (never deletes on the target unless explicitly
opted in), previewable (the diff is the dry-run), and idempotent (re-running with
no changes writes nothing).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import config
from gspread.exceptions import WorksheetNotFound


# Columns excluded from the field-level "differs" comparison because they are
# volatile bookkeeping timestamps rather than meaningful data.
_VOLATILE_COLUMNS = {
    config.SHEET_COLUMNS.get("last_updated"),
    config.SHEET_COLUMNS.get("last_analyzed"),
}

_ZILLOW_URL_COL = config.SHEET_COLUMNS.get("zillow_url", "Zillow URL")
_ADDRESS_COL = config.SHEET_COLUMNS.get("address", "Address")
_PRICE_COL = config.SHEET_COLUMNS.get("price", "Price")
_BEDROOMS_COL = config.SHEET_COLUMNS.get("bedrooms", "Bedrooms")
_SCORE_COL = config.SHEET_COLUMNS.get("weighted_score", "Weighted Score")


# ---------------------------------------------------------------------------
# Normalization / keying
# ---------------------------------------------------------------------------

def _norm_url(url: str) -> str:
    """Normalize a Zillow URL for matching: strip protocol/query/trailing slash."""
    u = (url or "").strip().lower()
    if not u:
        return ""
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    u = u.split("?", 1)[0].split("#", 1)[0]
    u = u.rstrip("/")
    return u


def _norm_address(addr: str) -> str:
    """Normalize an address for matching: lowercase, collapse whitespace, drop
    trailing punctuation. Deliberately conservative to avoid false merges."""
    a = (addr or "").strip().lower()
    if not a:
        return ""
    a = re.sub(r"\s+", " ", a)
    a = a.strip(" ,.;")
    return a


def _url_key(record: Dict[str, Any]) -> str:
    return _norm_url(str(record.get(_ZILLOW_URL_COL, "") or ""))


def _addr_key(record: Dict[str, Any]) -> str:
    return _norm_address(str(record.get(_ADDRESS_COL, "") or ""))


def _identity(item: Dict[str, Any]) -> Optional[str]:
    """Stable identity string for an apartment item (url preferred, else addr)."""
    if item.get("url_key"):
        return "url:" + item["url_key"]
    if item.get("addr_key"):
        return "addr:" + item["addr_key"]
    return None


def _cell(value: Any) -> Any:
    """Coerce a value for writing back to a sheet cell."""
    if value is None:
        return ""
    return value


def _summary(record: Dict[str, Any]) -> Dict[str, Any]:
    """Compact, UI-friendly summary of an apartment record."""
    return {
        "address": str(record.get(_ADDRESS_COL, "") or ""),
        "zillow_url": str(record.get(_ZILLOW_URL_COL, "") or ""),
        "price": record.get(_PRICE_COL, ""),
        "bedrooms": record.get(_BEDROOMS_COL, ""),
        "weighted_score": record.get(_SCORE_COL, ""),
    }


class SyncDisabledError(RuntimeError):
    """Raised when a sync operation is attempted but no peer sheet is configured."""


class CrossEnvSync:
    """Computes diffs and applies reconciliation plans between the local
    (current-user) sheet and the configured peer sheet."""

    def __init__(self, client):
        """
        Args:
            client: an initialized GoogleSheetsClient. Its current-user context
                (set_current_user) determines which local tabs are read/written.
        """
        self.client = client

    # -- enablement ------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return bool(getattr(config, "PEER_GOOGLE_SHEET_ID", ""))

    def _require_peer(self):
        if not self.enabled:
            raise SyncDisabledError(
                "Cross-environment sync is disabled (PEER_GOOGLE_SHEET_ID unset)."
            )
        peer = self.client.get_peer_spreadsheet()
        if peer is None:
            raise SyncDisabledError(
                "Cross-environment sync is disabled (PEER_GOOGLE_SHEET_ID unset)."
            )
        return peer

    # -- worksheet access ------------------------------------------------

    def _local_worksheet(self, base_name: str):
        """Open the current user's scoped worksheet for a base tab name.

        Returns None if it doesn't exist yet (a brand-new user may have empty
        tabs)."""
        name = self.client._scoped_name(base_name)
        try:
            return self.client.spreadsheet.worksheet(name)
        except WorksheetNotFound:
            return None

    def _peer_worksheet(self, base_name: str):
        """Open the peer's worksheet for a base tab name. The peer is assumed to
        use BASE (un-namespaced) tab names. Returns None if absent."""
        peer = self._require_peer()
        try:
            return peer.worksheet(base_name)
        except WorksheetNotFound:
            return None

    # -- reading ---------------------------------------------------------

    @staticmethod
    def _read_indexed(worksheet) -> List[Dict[str, Any]]:
        """Read a worksheet into indexed items carrying the source row number and
        match keys. Unkeyable rows (no url and no address) are dropped."""
        if worksheet is None:
            return []
        records = worksheet.get_all_records()
        indexed: List[Dict[str, Any]] = []
        for i, rec in enumerate(records):
            uk = _url_key(rec)
            ak = _addr_key(rec)
            if not uk and not ak:
                continue  # can't identify or copy this row meaningfully
            indexed.append({
                "record": rec,
                "row": i + 2,  # 1-indexed + header row
                "url_key": uk,
                "addr_key": ak,
            })
        return indexed

    @staticmethod
    def _build_lookup(indexed: List[Dict[str, Any]]) -> Tuple[Dict[str, Dict], Dict[str, Dict]]:
        by_url: Dict[str, Dict] = {}
        by_addr: Dict[str, Dict] = {}
        for item in indexed:
            if item["url_key"] and item["url_key"] not in by_url:
                by_url[item["url_key"]] = item
            if item["addr_key"] and item["addr_key"] not in by_addr:
                by_addr[item["addr_key"]] = item
        return by_url, by_addr

    @staticmethod
    def _find_match(item: Dict[str, Any], by_url: Dict[str, Dict], by_addr: Dict[str, Dict]) -> Optional[Dict]:
        if item["url_key"] and item["url_key"] in by_url:
            return by_url[item["url_key"]]
        if item["addr_key"] and item["addr_key"] in by_addr:
            return by_addr[item["addr_key"]]
        return None

    @staticmethod
    def _field_diffs(here_rec: Dict[str, Any], peer_rec: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return per-field differences between two records over shared columns,
        excluding volatile bookkeeping columns."""
        fields: List[Dict[str, Any]] = []
        shared = set(here_rec.keys()) & set(peer_rec.keys())
        for col in sorted(shared):
            if col in _VOLATILE_COLUMNS:
                continue
            here_v = "" if here_rec.get(col) is None else str(here_rec.get(col)).strip()
            peer_v = "" if peer_rec.get(col) is None else str(peer_rec.get(col)).strip()
            if here_v != peer_v:
                fields.append({"field": col, "here": here_v, "peer": peer_v})
        return fields

    # -- diff ------------------------------------------------------------

    def diff_apartments(self) -> Dict[str, Any]:
        """Compute the apartment diff between the current user's tab and the peer.

        Categories:
          - only_in_peer: apartments present in peer but not locally.
          - only_here:    apartments present locally but not in peer.
          - differ:       matched apartments whose fields differ.
          - in_sync_count: matched apartments that are identical.
        """
        base = self.client._BASE_MAIN_SHEET_NAME
        here = self._read_indexed(self._local_worksheet(base))
        peer = self._read_indexed(self._peer_worksheet(base))

        here_by_url, here_by_addr = self._build_lookup(here)

        only_in_peer: List[Dict[str, Any]] = []
        differ: List[Dict[str, Any]] = []
        in_sync = 0
        matched_here_ids = set()

        for p in peer:
            match = self._find_match(p, here_by_url, here_by_addr)
            if match is None:
                only_in_peer.append({
                    "key": _identity(p),
                    **_summary(p["record"]),
                })
            else:
                matched_here_ids.add(id(match))
                field_diffs = self._field_diffs(match["record"], p["record"])
                if field_diffs:
                    differ.append({
                        "key": _identity(p),
                        **_summary(p["record"]),
                        "fields": field_diffs,
                    })
                else:
                    in_sync += 1

        only_here: List[Dict[str, Any]] = []
        for h in here:
            if id(h) not in matched_here_ids:
                only_here.append({
                    "key": _identity(h),
                    **_summary(h["record"]),
                })

        return {
            "only_in_peer": only_in_peer,
            "only_here": only_here,
            "differ": differ,
            "in_sync_count": in_sync,
        }

    def _diff_kv_tab(self, base_name: str, key_col: str, value_col: str) -> Dict[str, Any]:
        """Generic diff for a simple key/value tab (used for Settings/weights).

        Compares by key_col; reports keys only in peer, only here, and differing
        values."""
        here_ws = self._local_worksheet(base_name)
        peer_ws = self._peer_worksheet(base_name)
        here_recs = here_ws.get_all_records() if here_ws else []
        peer_recs = peer_ws.get_all_records() if peer_ws else []

        here_map = {str(r.get(key_col, "")).strip(): r for r in here_recs if str(r.get(key_col, "")).strip()}
        peer_map = {str(r.get(key_col, "")).strip(): r for r in peer_recs if str(r.get(key_col, "")).strip()}

        only_in_peer = []
        only_here = []
        differ = []
        for k, pr in peer_map.items():
            if k not in here_map:
                only_in_peer.append({"key": k, "peer": str(pr.get(value_col, "")).strip()})
            else:
                hv = str(here_map[k].get(value_col, "")).strip()
                pv = str(pr.get(value_col, "")).strip()
                if hv != pv:
                    differ.append({"key": k, "here": hv, "peer": pv})
        for k, hr in here_map.items():
            if k not in peer_map:
                only_here.append({"key": k, "here": str(hr.get(value_col, "")).strip()})
        return {"only_in_peer": only_in_peer, "only_here": only_here, "differ": differ}

    def diff(self, include_extras: bool = True) -> Dict[str, Any]:
        """Full diff payload for the /sync/diff endpoint (doubles as dry-run)."""
        if not self.enabled:
            return {"enabled": False}

        from utils.google_sheets import get_current_user
        current_user = get_current_user()

        result: Dict[str, Any] = {
            "enabled": True,
            "here_label": current_user or "this environment",
            "peer_label": "the other environment",
            "apartments": self.diff_apartments(),
        }

        if include_extras:
            # Settings / weights — a simple Component/Weight key-value tab.
            try:
                result["settings"] = self._diff_kv_tab(
                    self.client._BASE_SETTINGS_SHEET_NAME, "Component", "Weight"
                )
            except Exception as e:
                result["settings"] = {"error": str(e)}

        return result

    # -- apply -----------------------------------------------------------

    def _snapshot(self, worksheet, base_name: str) -> Optional[str]:
        """Best-effort duplicate of a worksheet before a destructive merge.
        Returns the snapshot tab name, or None on failure."""
        try:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            new_name = f"{base_name} (backup {stamp})"
            worksheet.spreadsheet.duplicate_sheet(
                source_sheet_id=worksheet.id,
                new_sheet_name=new_name,
            )
            return new_name
        except Exception as e:
            print(f"⚠️  Could not snapshot '{base_name}': {e}")
            return None

    @staticmethod
    def _col_letter(idx0: int) -> str:
        letter = ""
        n = idx0
        while n >= 0:
            letter = chr(n % 26 + ord("A")) + letter
            n = n // 26 - 1
        return letter

    def _append_record(self, worksheet, headers: List[str], record: Dict[str, Any]) -> None:
        row = [_cell(record.get(h, "")) for h in headers]
        worksheet.append_row(row, value_input_option="USER_ENTERED")

    def _overwrite_row(self, worksheet, headers: List[str], row_number: int, record: Dict[str, Any]) -> None:
        row = [_cell(record.get(h, "")) for h in headers]
        last_col = self._col_letter(len(headers) - 1)
        worksheet.update(
            range_name=f"A{row_number}:{last_col}{row_number}",
            values=[row],
            value_input_option="USER_ENTERED",
        )

    def apply(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a reconciliation plan.

        plan = {
          "direction": "import" | "push",
          "add_keys": [str, ...],          # source-only apartments to copy over
          "conflict_resolutions": {key: "peer"|"mine"|"skip"},  # for differ items
          "delete_keys": [str, ...],       # target-only apartments to delete
          "allow_delete": bool,            # required for any deletion
          "confirm_push": bool,            # required when direction == "push"
          "snapshot": bool,                # snapshot target before destructive writes
        }

        Resolution semantics (independent of direction):
          "peer" = the peer's version wins, "mine" = my (local) version wins,
          "skip" = leave both as-is.

        Returns a summary of what changed. Additive by default; idempotent.
        """
        if not self.enabled:
            raise SyncDisabledError(
                "Cross-environment sync is disabled (PEER_GOOGLE_SHEET_ID unset)."
            )

        direction = plan.get("direction", "import")
        if direction not in ("import", "push"):
            raise ValueError(f"Invalid direction: {direction!r}")
        if direction == "push" and not plan.get("confirm_push"):
            raise PermissionError(
                "Pushing local data to the peer environment requires explicit "
                "confirmation (confirm_push=true)."
            )

        add_keys = set(plan.get("add_keys") or [])
        resolutions: Dict[str, str] = plan.get("conflict_resolutions") or {}
        delete_keys = set(plan.get("delete_keys") or [])
        allow_delete = bool(plan.get("allow_delete"))
        snapshot_requested = plan.get("snapshot", True)

        base = self.client._BASE_MAIN_SHEET_NAME

        # Read both sides fresh so we act on server-truth, not client-submitted data.
        here_ws = self._local_worksheet(base)
        peer_ws = self._peer_worksheet(base)
        here = self._read_indexed(here_ws)
        peer = self._read_indexed(peer_ws)

        if direction == "import":
            source_items, target_items = peer, here
            source_ws, target_ws = peer_ws, here_ws
            source_side = "peer"
        else:  # push
            source_items, target_items = here, peer
            source_ws, target_ws = here_ws, peer_ws
            source_side = "mine"

        if target_ws is None:
            # The current user's local tab may not exist yet — create it via the
            # normal initializer so headers are present, then re-open.
            if direction == "import":
                self.client.initialize_sheets()
                target_ws = self._local_worksheet(base)
            if target_ws is None:
                raise RuntimeError(f"Target worksheet '{base}' is unavailable.")
        if source_ws is None:
            # Nothing to copy from.
            source_items = []

        target_by_url, target_by_addr = self._build_lookup(target_items)
        source_by_url, source_by_addr = self._build_lookup(source_items)

        headers = target_ws.row_values(1)

        summary = {
            "direction": direction,
            "added": [],
            "overwritten": [],
            "deleted": [],
            "skipped": 0,
            "snapshot": None,
        }

        # Pre-compute planned destructive operations to decide on snapshotting.
        planned_overwrites = 0
        planned_deletes = 0
        for s in source_items:
            match = self._find_match(s, target_by_url, target_by_addr)
            if match is not None and _identity(s) and resolutions.get(_identity(s)) == source_side:
                planned_overwrites += 1
        if allow_delete:
            planned_deletes = len(delete_keys)

        if snapshot_requested and (planned_overwrites > 0 or planned_deletes > 0):
            summary["snapshot"] = self._snapshot(target_ws, base)

        # 1) Additions: source-only apartments the user asked to bring over.
        for s in source_items:
            sid = _identity(s)
            if sid is None:
                continue
            match = self._find_match(s, target_by_url, target_by_addr)
            if match is None and sid in add_keys:
                self._append_record(target_ws, headers, s["record"])
                summary["added"].append(_summary(s["record"]))

        # 2) Conflicts: matched apartments with differing fields.
        #    Overwrite target with source only when the source side wins.
        for s in source_items:
            sid = _identity(s)
            if sid is None:
                continue
            match = self._find_match(s, target_by_url, target_by_addr)
            if match is None:
                continue
            resolution = resolutions.get(sid, "skip")
            if resolution == source_side:
                # Only write if something actually differs (keep idempotent).
                if self._field_diffs(match["record"], s["record"]):
                    self._overwrite_row(target_ws, headers, match["row"], s["record"])
                    summary["overwritten"].append(_summary(s["record"]))
            else:
                summary["skipped"] += 1

        # 3) Deletions (opt-in only): target-only apartments the user chose to drop.
        if allow_delete and delete_keys:
            # Delete from the bottom up so row numbers stay valid.
            to_delete = []
            for t in target_items:
                tid = _identity(t)
                match = self._find_match(t, source_by_url, source_by_addr)
                if match is None and tid in delete_keys:
                    to_delete.append(t)
            for t in sorted(to_delete, key=lambda x: x["row"], reverse=True):
                target_ws.delete_rows(t["row"])
                summary["deleted"].append(_summary(t["record"]))

        return summary
