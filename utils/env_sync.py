"""
Cross-environment data sync.

The prod and staging deployments each own a *separate* Google Sheet but share
the same service account. This module lets one deployment read the *other*
environment's data, compute a diff against the current user's data, and import
missing apartments / reconcile differences.

Design notes / scope (see issue #8):
- Primary, well-defined direction is **import** (peer → the requesting user).
  Prod is single-user (base tab names); staging is multi-user (per-user tabs).
  Pushing a staging user's data into prod would collapse one user's data into
  prod's single dataset and risks clobbering, so it is intentionally NOT
  supported in v1.
- Apartments are matched by a stable key: the Zillow listing id (zpid) when
  available, otherwise a normalized address. This keeps false "mismatch" rates
  low when the same listing was entered in both environments.
- Applying a plan is **additive by default** (never deletes target rows),
  **previewable** (the same diff doubles as the dry-run), and **idempotent**
  (re-running with no changes is a no-op).
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import config


# Columns that are *derived* by the analysis pipeline (scores, cached lookups,
# timestamps, JSON blobs). These are recomputed per-environment and would
# generate noisy, meaningless "differences", so they're excluded from the
# field-level diff. Everything else (the listing facts a user actually enters)
# is compared.
_DERIVED_COLUMN_KEYS = {
    "commute_time_you", "commute_route", "commute_time_partner",
    "route_annoyingness", "commute_details", "commute_score",
    "safety_score_opendata", "combined_safety", "crime_details",
    "wfh_quality_score",
    "happening_score", "restaurants_nearby", "restaurants_list",
    "cafes_nearby", "cafes_list", "parks_nearby", "parks_list", "pois_list",
    "avg_walk_to_poi_mins", "nearest_poi_count", "pois_within_1_mile",
    "parking_score", "laundry_score", "gym_score", "space_luxury_score",
    "gym_within_10min", "gym_walk_time_mins", "gym_bike_time_mins",
    "gym_effective_time_mins", "gym_quality",
    "weighted_score", "score_min", "score_max", "score_certainty",
    "score_vs_max", "value_ratio", "last_updated", "last_analyzed",
    "apartment_elevation", "elevation_to_gym", "elevation_to_work",
}


def _derived_column_names() -> set:
    names = set()
    for key in _DERIVED_COLUMN_KEYS:
        col = config.SHEET_COLUMNS.get(key)
        if col:
            names.add(col)
    return names


def normalize_address(address: Any) -> str:
    """Normalize an address into a stable comparison key.

    Lower-cases, strips punctuation, expands a handful of common street-type
    abbreviations, and collapses whitespace so cosmetic differences ("123 Main
    St." vs "123 main street") don't register as a mismatch.
    """
    if not address:
        return ""
    text = str(address).lower().strip()
    # Drop punctuation that varies cosmetically.
    text = re.sub(r"[.,#]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Expand common abbreviations to a canonical long form (word-boundary only).
    replacements = {
        r"\bst\b": "street", r"\bave\b": "avenue", r"\bav\b": "avenue",
        r"\bblvd\b": "boulevard", r"\brd\b": "road", r"\bdr\b": "drive",
        r"\bln\b": "lane", r"\bct\b": "court", r"\bpl\b": "place",
        r"\bter\b": "terrace", r"\bhwy\b": "highway", r"\bpkwy\b": "parkway",
        r"\bapt\b": "apartment", r"\bste\b": "suite", r"\bunit\b": "unit",
        r"\bn\b": "north", r"\bs\b": "south", r"\be\b": "east", r"\bw\b": "west",
    }
    for pattern, repl in replacements.items():
        text = re.sub(pattern, repl, text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_zillow_url(url: Any) -> str:
    """Return a stable key for a Zillow URL, preferring the zpid.

    Zillow listing URLs embed a stable numeric id as ``<n>_zpid``; when present
    that's the most reliable key. Otherwise fall back to the lower-cased path.
    Returns "" when there's no usable URL.
    """
    if not url:
        return ""
    text = str(url).strip()
    if not text:
        return ""
    match = re.search(r"(\d+)_zpid", text)
    if match:
        return f"zpid:{match.group(1)}"
    # Fall back to host+path without query/fragment.
    text = text.split("?", 1)[0].split("#", 1)[0].rstrip("/").lower()
    text = re.sub(r"^https?://(www\.)?", "", text)
    return text


_HYPERLINK_RE = re.compile(r'=HYPERLINK\(\s*"([^"]+)"', re.IGNORECASE)


def _extract_url_from_formula(formula: Any) -> str:
    """Pull the URL out of an ``=HYPERLINK("url","text")`` formula, else ""."""
    if not formula or not isinstance(formula, str):
        return ""
    match = _HYPERLINK_RE.search(formula)
    return match.group(1) if match else ""


def _values_equal(a: Any, b: Any) -> bool:
    """Compare two sheet values for the diff, tolerant of type/format noise."""
    sa = "" if a is None else str(a).strip()
    sb = "" if b is None else str(b).strip()
    if sa == sb:
        return True
    # Numeric equivalence: "3000" == "3000.0" == "3,000".
    try:
        fa = float(sa.replace(",", "").replace("$", ""))
        fb = float(sb.replace(",", "").replace("$", ""))
        return fa == fb
    except (ValueError, AttributeError):
        return False


def _col_index_to_letter(col_idx: int) -> str:
    """0-indexed column number -> Excel-style column letter."""
    letter = ""
    col_idx += 1
    while col_idx > 0:
        col_idx -= 1
        letter = chr(65 + (col_idx % 26)) + letter
        col_idx //= 26
    return letter


class EnvSyncManager:
    """Detects and reconciles data differences with a peer environment."""

    def __init__(self, sheets_client,
                 peer_sheet_id: Optional[str] = None,
                 peer_is_multi_user: Optional[bool] = None,
                 peer_label: Optional[str] = None):
        self.sheets_client = sheets_client
        self.peer_sheet_id = (
            peer_sheet_id if peer_sheet_id is not None
            else config.PEER_GOOGLE_SHEET_ID
        )
        self.peer_is_multi_user = (
            peer_is_multi_user if peer_is_multi_user is not None
            else config.PEER_IS_MULTI_USER
        )
        self.peer_label = peer_label or config.PEER_ENV_LABEL

    def is_enabled(self) -> bool:
        """The feature is available only when a peer sheet is configured."""
        return bool(self.peer_sheet_id) and self.sheets_client is not None

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------
    def _address_col_name(self) -> str:
        return config.SHEET_COLUMNS["address"]

    def _read_worksheet_apartments(self, worksheet) -> Tuple[List[str], List[Dict[str, Any]], List[str]]:
        """Read a main-data worksheet.

        Returns ``(headers, records, zillow_urls)`` where ``records`` is the
        list of row dicts (as ``get_all_records`` returns) and ``zillow_urls``
        is the URL embedded in each row's address HYPERLINK formula (parallel to
        ``records``; "" when the address is a plain string).
        """
        headers = worksheet.row_values(1)
        records = worksheet.get_all_records()

        zillow_urls = ["" for _ in records]
        address_col = self._address_col_name()
        if records and address_col in headers:
            col_letter = _col_index_to_letter(headers.index(address_col))
            last_row = len(records) + 1  # +1 for header row
            try:
                formulas = worksheet.get(
                    f"{col_letter}2:{col_letter}{last_row}",
                    value_render_option="FORMULA",
                )
                for i in range(len(records)):
                    if i < len(formulas) and formulas[i]:
                        zillow_urls[i] = _extract_url_from_formula(formulas[i][0])
            except Exception as e:  # pragma: no cover - best-effort enrichment
                print(f"  ⚠️  Could not read address formulas for Zillow URLs: {e}")

        return headers, records, zillow_urls

    def _read_my_apartments(self) -> Tuple[List[str], List[Dict[str, Any]], List[str]]:
        """Read the current user's main-data worksheet (own environment)."""
        client = self.sheets_client
        worksheet = client.spreadsheet.worksheet(client.MAIN_SHEET_NAME)
        return self._read_worksheet_apartments(worksheet)

    def _read_peer_apartments(self, peer_username: Optional[str]) -> Tuple[List[str], List[Dict[str, Any]], List[str]]:
        """Read the peer environment's main-data worksheet."""
        client = self.sheets_client
        peer_spreadsheet = client.open_spreadsheet(self.peer_sheet_id)
        base_main = client.BASE_TAB_NAMES["main"]
        peer_tab = client.scoped_tab_name(base_main, peer_username)
        worksheet = peer_spreadsheet.worksheet(peer_tab)
        return self._read_worksheet_apartments(worksheet)

    def _peer_username_for(self, my_username: Optional[str]) -> Optional[str]:
        """Which username namespaces the peer's tabs.

        If the peer is multi-user, its tabs are namespaced by the requesting
        user's name; if single-user (prod), there is no namespace.
        """
        return my_username if self.peer_is_multi_user else None

    # ------------------------------------------------------------------
    # Diff
    # ------------------------------------------------------------------
    @staticmethod
    def _record_key(record: Dict[str, Any], zillow_url: str) -> Tuple[str, str, str]:
        """Return (match_key, address, zillow_url) for a record.

        Prefer the Zillow zpid as the match key (most stable); fall back to the
        normalized address.
        """
        address = str(record.get(config.SHEET_COLUMNS["address"], "") or "").strip()
        z_key = normalize_zillow_url(zillow_url)
        a_key = normalize_address(address)
        match_key = z_key or a_key
        return match_key, address, zillow_url

    def compute_diff(self, my_username: Optional[str] = None) -> Dict[str, Any]:
        """Compute the diff between the current user's data and the peer sheet.

        Returns a JSON-serializable dict with categorized apartments:
        ``only_in_peer`` (importable), ``only_here``, ``differ`` (present in
        both, some listing fields differ), and ``identical`` (count only).
        """
        if not self.is_enabled():
            return {"enabled": False}

        peer_username = self._peer_username_for(my_username)

        my_headers, my_records, my_zillow = self._read_my_apartments()
        peer_headers, peer_records, peer_zillow = self._read_peer_apartments(peer_username)

        # Build a lookup of peer rows by match key (and a secondary address key,
        # so an address match still works when only one side has a Zillow URL).
        peer_by_key: Dict[str, Dict[str, Any]] = {}
        peer_by_addr: Dict[str, Dict[str, Any]] = {}
        peer_entries = []
        for idx, rec in enumerate(peer_records):
            z = peer_zillow[idx] if idx < len(peer_zillow) else ""
            key, address, zurl = self._record_key(rec, z)
            if not key:
                continue  # skip blank rows
            entry = {"key": key, "address": address, "zillow_url": zurl,
                     "record": rec, "addr_key": normalize_address(address)}
            peer_entries.append(entry)
            peer_by_key.setdefault(key, entry)
            if entry["addr_key"]:
                peer_by_addr.setdefault(entry["addr_key"], entry)

        # Compare the columns present on both sides, excluding derived columns.
        derived = _derived_column_names()
        comparable_cols = [
            h for h in my_headers
            if h and h not in derived and h in peer_headers
            and h != self._address_col_name()
        ]

        only_here: List[Dict[str, Any]] = []
        differ: List[Dict[str, Any]] = []
        identical = 0
        matched_peer_keys = set()

        for idx, rec in enumerate(my_records):
            z = my_zillow[idx] if idx < len(my_zillow) else ""
            key, address, zurl = self._record_key(rec, z)
            if not key:
                continue
            addr_key = normalize_address(address)

            peer_entry = peer_by_key.get(key) or (peer_by_addr.get(addr_key) if addr_key else None)
            if peer_entry is None:
                only_here.append({"key": key, "address": address, "zillow_url": zurl,
                                  "price": rec.get(config.SHEET_COLUMNS["price"], "")})
                continue

            matched_peer_keys.add(peer_entry["key"])

            field_diffs = []
            for col in comparable_cols:
                mine_val = rec.get(col, "")
                peer_val = peer_entry["record"].get(col, "")
                if not _values_equal(mine_val, peer_val):
                    field_diffs.append({
                        "column": col,
                        "mine": "" if mine_val is None else str(mine_val),
                        "peer": "" if peer_val is None else str(peer_val),
                    })

            # Zillow URL itself can differ (one side missing the link).
            if zurl or peer_entry["zillow_url"]:
                if normalize_zillow_url(zurl) != normalize_zillow_url(peer_entry["zillow_url"]):
                    field_diffs.append({
                        "column": self._address_col_name() + " (Zillow link)",
                        "mine": zurl or "",
                        "peer": peer_entry["zillow_url"] or "",
                    })

            if field_diffs:
                differ.append({
                    "key": key,
                    "address": address,
                    "my_row": idx + 2,  # 1-indexed + header
                    "fields": field_diffs,
                })
            else:
                identical += 1

        only_in_peer = []
        for entry in peer_entries:
            if entry["key"] in matched_peer_keys:
                continue
            # Guard against duplicate peer keys being reported twice.
            if any(o["key"] == entry["key"] for o in only_in_peer):
                continue
            only_in_peer.append({
                "key": entry["key"],
                "address": entry["address"],
                "zillow_url": entry["zillow_url"],
                "price": entry["record"].get(config.SHEET_COLUMNS["price"], ""),
            })

        return {
            "enabled": True,
            "peer_label": self.peer_label,
            "summary": {
                "only_in_peer": len(only_in_peer),
                "only_here": len(only_here),
                "differ": len(differ),
                "identical": identical,
            },
            "only_in_peer": only_in_peer,
            "only_here": only_here,
            "differ": differ,
        }

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------
    def _build_row(self, my_headers: List[str], peer_record: Dict[str, Any]) -> List[Any]:
        """Build a row (aligned to my headers) from a peer record.

        Values are copied by matching column *name*. The address column is left
        blank here — it's written separately as a HYPERLINK formula so the
        Zillow link is preserved.
        """
        address_col = self._address_col_name()
        row = []
        for h in my_headers:
            if h == address_col:
                row.append("")  # filled in separately as a formula
            else:
                val = peer_record.get(h, "")
                row.append("" if val is None else val)
        return row

    def _snapshot_target(self, worksheet) -> Optional[str]:
        """Duplicate the target worksheet as a timestamped backup. Best-effort."""
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_name = f"{worksheet.title} - backup {stamp}"
        try:
            worksheet.duplicate(new_sheet_name=backup_name)
            return backup_name
        except Exception as e:  # pragma: no cover - non-fatal
            print(f"  ⚠️  Could not snapshot '{worksheet.title}': {e}")
            return None

    def apply_plan(self, plan: Dict[str, Any], my_username: Optional[str] = None) -> Dict[str, Any]:
        """Apply a sync plan.

        plan = {
            "direction": "import",                # only "import" supported in v1
            "snapshot": bool,                     # back up target tab first
            "import_new": ["key1", ...],          # only_in_peer keys to add
            "conflicts": {"key": "peer"|"mine"|"skip"},  # per-item resolution
        }
        Returns a summary of what changed. Additive by default (never deletes),
        and idempotent (re-applying an already-applied plan is a no-op).
        """
        if not self.is_enabled():
            return {"success": False, "error": "Cross-environment sync is not configured."}

        direction = (plan.get("direction") or "import").strip().lower()
        if direction != "import":
            return {
                "success": False,
                "error": ("Only 'import' (peer → you) is supported. Pushing into "
                          "the peer environment is disabled to avoid clobbering "
                          "its data."),
            }

        import_new_keys = set(plan.get("import_new") or [])
        conflicts = plan.get("conflicts") or {}
        do_snapshot = bool(plan.get("snapshot", False))

        peer_username = self._peer_username_for(my_username)

        # Read both sides fresh so we act on current state (idempotency).
        my_headers, my_records, my_zillow = self._read_my_apartments()
        peer_headers, peer_records, peer_zillow = self._read_peer_apartments(peer_username)

        # Index peer entries by key.
        peer_by_key: Dict[str, Dict[str, Any]] = {}
        peer_by_addr: Dict[str, Dict[str, Any]] = {}
        for idx, rec in enumerate(peer_records):
            z = peer_zillow[idx] if idx < len(peer_zillow) else ""
            key, address, zurl = self._record_key(rec, z)
            if not key:
                continue
            entry = {"key": key, "address": address, "zillow_url": zurl, "record": rec}
            peer_by_key.setdefault(key, entry)
            addr_key = normalize_address(address)
            if addr_key:
                peer_by_addr.setdefault(addr_key, entry)

        # Index my rows by key -> row number.
        my_key_to_row: Dict[str, int] = {}
        my_addr_to_row: Dict[str, int] = {}
        my_keys = set()
        for idx, rec in enumerate(my_records):
            z = my_zillow[idx] if idx < len(my_zillow) else ""
            key, address, zurl = self._record_key(rec, z)
            if not key:
                continue
            my_keys.add(key)
            my_key_to_row[key] = idx + 2
            addr_key = normalize_address(address)
            if addr_key:
                my_addr_to_row[addr_key] = idx + 2

        client = self.sheets_client
        worksheet = client.spreadsheet.worksheet(client.MAIN_SHEET_NAME)

        snapshot_name = None
        will_write = bool(import_new_keys) or any(
            r == "peer" for r in conflicts.values()
        )
        if do_snapshot and will_write:
            snapshot_name = self._snapshot_target(worksheet)

        address_col = self._address_col_name()
        added, updated, skipped = [], [], []

        # ---- 1) Import new apartments (append rows) ----------------------
        next_row = len(my_records) + 2
        rows_to_append = []
        append_meta = []  # (row_number, address, zillow_url)
        for key in import_new_keys:
            entry = peer_by_key.get(key)
            if entry is None:
                skipped.append({"key": key, "reason": "not found in peer"})
                continue
            # Idempotency: if it already exists locally, skip.
            addr_key = normalize_address(entry["address"])
            if key in my_keys or (addr_key and addr_key in my_addr_to_row):
                skipped.append({"key": key, "address": entry["address"],
                                "reason": "already present"})
                continue
            row = self._build_row(my_headers, entry["record"])
            rows_to_append.append(row)
            append_meta.append((next_row, entry["address"], entry["zillow_url"]))
            added.append({"key": key, "address": entry["address"], "row": next_row})
            next_row += 1

        if rows_to_append:
            worksheet.append_rows(rows_to_append, value_input_option="USER_ENTERED")
            # Write address column as HYPERLINK (or plain) per appended row.
            if address_col in my_headers:
                col_letter = _col_index_to_letter(my_headers.index(address_col))
                addr_updates = []
                for (row_num, address, zurl) in append_meta:
                    if zurl:
                        safe_addr = str(address).replace('"', '""')
                        value = f'=HYPERLINK("{zurl}", "{safe_addr}")'
                    else:
                        value = address
                    addr_updates.append({"range": f"{col_letter}{row_num}",
                                         "values": [[value]]})
                if addr_updates:
                    worksheet.batch_update(addr_updates, value_input_option="USER_ENTERED")

        # ---- 2) Resolve conflicts (update differing columns) ------------
        derived = _derived_column_names()
        comparable_cols = [
            h for h in my_headers
            if h and h not in derived and h in peer_headers and h != address_col
        ]
        for key, resolution in conflicts.items():
            resolution = (resolution or "skip").strip().lower()
            if resolution in ("mine", "skip"):
                skipped.append({"key": key, "reason": f"kept {resolution}"})
                continue
            if resolution != "peer":
                skipped.append({"key": key, "reason": f"unknown resolution '{resolution}'"})
                continue

            entry = peer_by_key.get(key)
            row_num = my_key_to_row.get(key)
            if row_num is None:
                # Try address fallback.
                if entry is not None:
                    row_num = my_addr_to_row.get(normalize_address(entry["address"]))
            if entry is None or row_num is None:
                skipped.append({"key": key, "reason": "no matching row to update"})
                continue

            cell_updates = []
            changed_cols = []
            for col in comparable_cols:
                mine_idx = row_num - 2
                mine_val = my_records[mine_idx].get(col, "") if 0 <= mine_idx < len(my_records) else ""
                peer_val = entry["record"].get(col, "")
                if not _values_equal(mine_val, peer_val):
                    col_letter = _col_index_to_letter(my_headers.index(col))
                    cell_updates.append({
                        "range": f"{col_letter}{row_num}",
                        "values": [["" if peer_val is None else peer_val]],
                    })
                    changed_cols.append(col)

            # Address hyperlink: adopt peer's Zillow link if it differs.
            mine_z = my_zillow[row_num - 2] if 0 <= (row_num - 2) < len(my_zillow) else ""
            if entry["zillow_url"] and normalize_zillow_url(mine_z) != normalize_zillow_url(entry["zillow_url"]):
                if address_col in my_headers:
                    col_letter = _col_index_to_letter(my_headers.index(address_col))
                    safe_addr = str(entry["address"]).replace('"', '""')
                    cell_updates.append({
                        "range": f"{col_letter}{row_num}",
                        "values": [[f'=HYPERLINK("{entry["zillow_url"]}", "{safe_addr}")']],
                    })
                    changed_cols.append(address_col)

            if cell_updates:
                worksheet.batch_update(cell_updates, value_input_option="USER_ENTERED")
                updated.append({"key": key, "address": entry["address"],
                                "row": row_num, "columns": changed_cols})
            else:
                skipped.append({"key": key, "address": entry["address"],
                                "reason": "already up to date"})

        return {
            "success": True,
            "direction": direction,
            "snapshot": snapshot_name,
            "added": added,
            "updated": updated,
            "skipped": skipped,
            "summary": {
                "added": len(added),
                "updated": len(updated),
                "skipped": len(skipped),
            },
        }
