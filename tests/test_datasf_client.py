"""
Unit tests for utils.datasf_client.

Hermetic by default (no network). One opt-in live smoke test hits the real
DataSF API when RUN_LIVE_DATASF_TESTS=1 is set.

Run: python -m unittest tests.test_datasf_client
Live: RUN_LIVE_DATASF_TESTS=1 python -m unittest tests.test_datasf_client
"""

import os
import unittest
from unittest import mock

import config
from utils import datasf_client


class AddressParsingTests(unittest.TestCase):
    def test_normalize_street_strips_unit_and_uppercases(self):
        self.assertEqual(
            datasf_client._normalize_street("123 Main St Apt 4B, San Francisco, CA"),
            "123 MAIN ST")

    def test_parse_address_zero_pads_and_drops_type(self):
        self.assertEqual(
            datasf_client._parse_address("749 Filbert St, San Francisco"),
            ("0749", "FILBERT"))

    def test_parse_address_no_type_suffix(self):
        self.assertEqual(
            datasf_client._parse_address("2000 Broadway, San Francisco, CA"),
            ("2000", "BROADWAY"))

    def test_parse_address_multiword_street(self):
        self.assertEqual(
            datasf_client._parse_address("1 South Van Ness Ave"),
            ("0001", "SOUTH VAN NESS"))

    def test_parse_address_without_number_returns_none(self):
        self.assertIsNone(datasf_client._parse_address("not an address"))


class NormalizeRecordTests(unittest.TestCase):
    def test_maps_roll_field_names(self):
        rec = datasf_client._normalize_record({
            "parcel_number": "0713165",
            "property_location": "0000 1200 GOUGH               ST0024C",
            "year_property_built": "1966",
            "property_area": "840",
            "lot_area": "1000",
            "number_of_units": "1",
            "use_definition": "Single Family Residential",
            "closed_roll_year": "2025",
        })
        self.assertEqual(rec.year_built, 1966)
        self.assertEqual(rec.building_sqft, 840)
        self.assertEqual(rec.number_of_units, 1)
        self.assertEqual(rec.closed_roll_year, 2025)


class RentControlTests(unittest.TestCase):
    def _rec(self, year):
        return datasf_client.PropertyRecord(
            parcel_number="x", property_location="x", year_built=year)

    def test_before_cutoff_is_controlled(self):
        with mock.patch.object(config, "SF_RENT_CONTROL_CUTOFF_YEAR", 1979):
            self.assertTrue(self._rec(1966).is_rent_controlled)

    def test_at_or_after_cutoff_not_controlled(self):
        with mock.patch.object(config, "SF_RENT_CONTROL_CUTOFF_YEAR", 1979):
            self.assertFalse(self._rec(1979).is_rent_controlled)
            self.assertFalse(self._rec(2005).is_rent_controlled)

    def test_unknown_year_is_none(self):
        self.assertIsNone(self._rec(None).is_rent_controlled)


class ToApartmentDataTests(unittest.TestCase):
    def _rec(self, year=None, sqft=None, units=None):
        return datasf_client.PropertyRecord(
            parcel_number="x", property_location="x",
            year_built=year, building_sqft=sqft, number_of_units=units)

    def test_single_unit_surfaces_sqft(self):
        data = self._rec(year=1966, sqft=840, units=1).to_apartment_data()
        self.assertEqual(data["year_built"], 1966)
        self.assertTrue(data["rent_control"])
        self.assertEqual(data["sqft"], 840)

    def test_multi_unit_withholds_sqft(self):
        data = self._rec(year=1974, sqft=165485, units=222).to_apartment_data()
        self.assertEqual(data["year_built"], 1974)
        self.assertNotIn("sqft", data)

    def test_zero_units_withholds_sqft(self):
        data = self._rec(year=1959, sqft=656844, units=0).to_apartment_data()
        self.assertNotIn("sqft", data)

    def test_no_year_still_surfaces_single_unit_sqft(self):
        # year/rent_control need a year, but authoritative single-unit sqft is
        # useful on its own.
        self.assertEqual(
            self._rec(units=1, sqft=800).to_apartment_data(), {"sqft": 800})

    def test_nothing_usable_is_empty(self):
        self.assertEqual(self._rec().to_apartment_data(), {})


class LookupTests(unittest.TestCase):
    def test_lookup_by_address_builds_padded_spaced_like(self):
        with mock.patch.object(datasf_client, "_query",
                               return_value=[{"parcel_number": "1",
                                              "property_location": "0000 0749 FILBERT ST0000",
                                              "year_property_built": "1907"}]) as q:
            rec = datasf_client.lookup_by_address(
                "749 Filbert St, San Francisco", use_cache=False)
        where = q.call_args.args[0]
        self.assertEqual(where, "upper(property_location) like '% 0749 FILBERT%'")
        self.assertEqual(rec.year_built, 1907)

    def test_lookup_by_address_no_rows_returns_none(self):
        with mock.patch.object(datasf_client, "_query", return_value=[]):
            self.assertIsNone(datasf_client.lookup_by_address(
                "9999 Nowhere St", use_cache=False))

    def test_lookup_by_address_unparseable_returns_none_without_query(self):
        with mock.patch.object(datasf_client, "_query") as q:
            self.assertIsNone(datasf_client.lookup_by_address(
                "not an address", use_cache=False))
            q.assert_not_called()

    def test_lookup_by_parcel_escapes_quotes(self):
        with mock.patch.object(datasf_client, "_query",
                               return_value=[{"parcel_number": "12'34",
                                              "property_location": "x"}]) as q:
            datasf_client.lookup_by_parcel("12'34", use_cache=False)
        self.assertEqual(q.call_args.args[0], "parcel_number = '12''34'")

    def test_lookup_by_parcel_empty_returns_none(self):
        with mock.patch.object(datasf_client, "_query") as q:
            self.assertIsNone(datasf_client.lookup_by_parcel("", use_cache=False))
            q.assert_not_called()


@unittest.skipUnless(os.getenv("RUN_LIVE_DATASF_TESTS") == "1",
                     "set RUN_LIVE_DATASF_TESTS=1 to hit the live DataSF API")
class LiveSmokeTests(unittest.TestCase):
    def test_known_sf_apartment_building(self):
        rec = datasf_client.lookup_by_address(
            "2000 Broadway, San Francisco, CA", use_cache=False)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.year_built, 1974)
        self.assertGreater(rec.number_of_units, 1)
        self.assertTrue(rec.is_rent_controlled)


if __name__ == "__main__":
    unittest.main()
