from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from geodata import fields, merge, message_field, read_entries, varint


def entry(name, kind="geosite", extra=b"", domain=b"example.org"):
    if kind == "geosite":
        # Root-domain record with an attribute and an unknown fixed32 field.
        record = b"\x08\x02" + message_field(2, domain) + message_field(3, message_field(1, b"ads") + b"\x10\x01") + b"\x4d\x01\x02\x03\x04"
    else:
        record = message_field(1, bytes([192, 0, 2, 0])) + b"\x10\x18"
    return message_field(1, message_field(1, name.encode()) + message_field(2, record) + extra)


class MergeTests(unittest.TestCase):
    def test_sources_keep_same_category_separate_and_preserve_payload(self):
        data = entry("YOUTUBE") + entry("CN")
        output, catalog = merge([("v2fly", data), ("refilter", entry("youtube")), ("shvetsov", entry("ALL"))], {"cn": "v2fly-cn"}, "geosite")
        result = read_entries(output, "geosite")
        self.assertEqual(set(result), {"v2fly-youtube", "v2fly-cn", "refilter-youtube", "shvetsov-all", "cn"})
        before = [f.raw for f in fields(read_entries(data, "geosite")["youtube"].payload) if f.number != 1]
        after = [f.raw for f in fields(result["v2fly-youtube"].payload) if f.number != 1]
        self.assertEqual(before, after)
        self.assertEqual(result["shvetsov-all"].records, 1)
        self.assertEqual(len(catalog), 5)

    def test_geoip_payload_is_preserved(self):
        output, _ = merge([("v2fly", entry("CN", "geoip")), ("shvetsov", entry("ALL", "geoip"))], {"cn": "v2fly-cn"}, "geoip")
        self.assertEqual(read_entries(output, "geoip")["shvetsov-all"].records, 1)

    def test_case_insensitive_duplicate_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate geodata"):
            read_entries(entry("ALL") + entry("all"), "geosite")

    def test_missing_alias_cannot_publish_partial_database(self):
        with self.assertRaisesRegex(ValueError, "target is missing"):
            merge([("v2fly", entry("CN"))], {"cn": "v2fly-missing"}, "geosite")

    def test_reverse_match_is_not_silently_lost(self):
        with self.assertRaisesRegex(ValueError, "reverse_match"):
            read_entries(entry("NOT-CN", "geoip", b"\x18\x01"), "geoip")

    def test_truncated_input_is_rejected(self):
        for data in (b"\x0a\x80", entry("ALL")[:-1], b"\x00", b"\x0b"):
            with self.subTest(data=data), self.assertRaises(ValueError):
                read_entries(data, "geosite")

    def test_invalid_ip_is_rejected(self):
        bad = message_field(1, b"\x0a\x02CN" + message_field(2, message_field(1, b"short") + b"\x10\x18"))
        with self.assertRaisesRegex(ValueError, "Invalid CIDR"):
            read_entries(bad, "geoip")

    def test_missing_cn_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "CN category"):
            merge([("shvetsov", entry("ALL"))], {}, "geosite")

    def test_varint_overflow_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "overflows"):
            list(fields(b"\x08" + b"\xff" * 9 + b"\x02"))

    def test_output_is_deterministic_for_category_order(self):
        sources = [("v2fly", entry("CN") + entry("YOUTUBE"))]
        reversed_sources = [("v2fly", entry("YOUTUBE") + entry("CN"))]
        self.assertEqual(merge(sources, {"cn": "v2fly-cn"}, "geosite"), merge(reversed_sources, {"cn": "v2fly-cn"}, "geosite"))


if __name__ == "__main__":
    unittest.main()
