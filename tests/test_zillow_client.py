"""
Unit tests for utils.zillow_client (hermetic — no network).

Run: python -m unittest tests.test_zillow_client
"""

import unittest
from unittest import mock

import config
from utils import zillow_client


def _fake_response(status_code=200, payload=None, text=""):
    resp = mock.Mock()
    resp.status_code = status_code
    resp.json.return_value = payload if payload is not None else {}
    resp.text = text
    return resp


class IsEnabledTests(unittest.TestCase):
    def test_disabled_without_flag_or_key(self):
        with mock.patch.object(config, "ZILLOW_SEARCH_ENABLED", False), \
             mock.patch.object(config, "ZILLOW_RAPIDAPI_KEY", ""):
            self.assertFalse(zillow_client.is_enabled())

    def test_enabled_needs_both_flag_and_key(self):
        with mock.patch.object(config, "ZILLOW_SEARCH_ENABLED", True), \
             mock.patch.object(config, "ZILLOW_RAPIDAPI_KEY", ""):
            self.assertFalse(zillow_client.is_enabled())
        with mock.patch.object(config, "ZILLOW_SEARCH_ENABLED", True), \
             mock.patch.object(config, "ZILLOW_RAPIDAPI_KEY", "k"):
            self.assertTrue(zillow_client.is_enabled())


class NormalizeTests(unittest.TestCase):
    def test_full_record_relative_url_is_prefixed(self):
        rec = zillow_client._normalize_prop({
            "zpid": 12345,
            "detailUrl": "/homedetails/123-Main/12345_zpid/",
            "address": "123 Main St, San Francisco, CA 94103",
            "price": 3200, "bedrooms": 2, "bathrooms": 1.5,
            "livingArea": 820, "latitude": 37.77, "longitude": -122.4,
            "imgSrc": "http://img", "propertyType": "APARTMENT",
        })
        self.assertEqual(rec.zpid, "12345")
        self.assertEqual(rec.zillow_url,
                         "https://www.zillow.com/homedetails/123-Main/12345_zpid/")
        self.assertEqual(rec.price, 3200)
        self.assertEqual(rec.sqft, 820)
        self.assertEqual(rec.bathrooms, 1.5)

    def test_absolute_url_is_kept(self):
        rec = zillow_client._normalize_prop({
            "zpid": "9", "detailUrl": "https://www.zillow.com/x/9_zpid/",
            "address": "1 A St",
        })
        self.assertEqual(rec.zillow_url, "https://www.zillow.com/x/9_zpid/")

    def test_missing_zpid_returns_none(self):
        self.assertIsNone(zillow_client._normalize_prop({"address": "1 A St"}))

    def test_missing_address_returns_none(self):
        self.assertIsNone(zillow_client._normalize_prop({"zpid": "9"}))

    def test_address_assembled_from_parts(self):
        rec = zillow_client._normalize_prop({
            "zpid": "9",
            "addressStreet": "123 Main St", "addressCity": "San Francisco",
            "addressState": "CA", "addressZipcode": "94103",
        })
        self.assertEqual(rec.address,
                         "123 Main St, San Francisco, CA, 94103")

    def test_sqft_falls_back_to_sqft_field(self):
        rec = zillow_client._normalize_prop(
            {"zpid": "9", "address": "1 A St", "sqft": "700"})
        self.assertEqual(rec.sqft, 700)


class ToApartmentDataTests(unittest.TestCase):
    def test_only_present_fields_included(self):
        rec = zillow_client.ListingResult(
            zpid="9", address="1 A St", zillow_url="http://x")
        data = rec.to_apartment_data()
        self.assertEqual(data["address"], "1 A St")
        self.assertEqual(data["availability_status"], "Available")
        self.assertNotIn("price", data)
        self.assertNotIn("sqft", data)

    def test_present_numeric_fields_included(self):
        rec = zillow_client.ListingResult(
            zpid="9", address="1 A St", zillow_url="http://x",
            price=3200, bedrooms=2, bathrooms=1.0, sqft=800)
        data = rec.to_apartment_data()
        self.assertEqual(data["price"], 3200)
        self.assertEqual(data["bedrooms"], 2)
        self.assertEqual(data["sqft"], 800)


class SearchListingsTests(unittest.TestCase):
    def test_raises_when_disabled(self):
        with mock.patch.object(zillow_client, "is_enabled", return_value=False):
            with self.assertRaises(zillow_client.ZillowSearchError):
                zillow_client.search_listings("San Francisco, CA")

    def test_maps_params_and_normalizes(self):
        payload = {"props": [
            {"zpid": "1", "address": "1 A St", "price": 3000},
            {"zpid": "2", "address": "2 B St", "price": 3500},
            {"address": "no zpid — skipped"},
        ]}
        with mock.patch.object(zillow_client, "is_enabled", return_value=True), \
             mock.patch.object(config, "ZILLOW_RAPIDAPI_KEY", "k"), \
             mock.patch.object(config, "ZILLOW_RAPIDAPI_HOST", "host.example"), \
             mock.patch.object(zillow_client.requests, "get",
                               return_value=_fake_response(payload=payload)) as g:
            out = zillow_client.search_listings(
                "San Francisco, CA", max_rent=4000, min_beds=2, min_sqft=600,
                use_cache=False)
        self.assertEqual([r.zpid for r in out], ["1", "2"])  # junk dropped
        params = g.call_args.kwargs["params"]
        self.assertEqual(params["rentMaxPrice"], 4000)
        self.assertEqual(params["bedsMin"], 2)
        self.assertEqual(params["sqftMin"], 600)
        self.assertEqual(params["status_type"], "ForRent")

    def test_limit_truncates(self):
        payload = {"props": [{"zpid": str(i), "address": f"{i} St"}
                             for i in range(10)]}
        with mock.patch.object(zillow_client, "is_enabled", return_value=True), \
             mock.patch.object(config, "ZILLOW_RAPIDAPI_KEY", "k"), \
             mock.patch.object(zillow_client.requests, "get",
                               return_value=_fake_response(payload=payload)):
            out = zillow_client.search_listings(
                "SF", limit=3, use_cache=False)
        self.assertEqual(len(out), 3)

    def test_non_200_raises(self):
        with mock.patch.object(zillow_client, "is_enabled", return_value=True), \
             mock.patch.object(config, "ZILLOW_RAPIDAPI_KEY", "k"), \
             mock.patch.object(zillow_client.requests, "get",
                               return_value=_fake_response(status_code=429, text="rate limited")):
            with self.assertRaises(zillow_client.ZillowSearchError):
                zillow_client.search_listings("SF", use_cache=False)


if __name__ == "__main__":
    unittest.main()
