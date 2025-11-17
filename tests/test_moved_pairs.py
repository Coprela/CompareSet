import unittest

try:
    from compare_set_gui import suppress_moved_pairs
    _IMPORT_OK = True
except Exception as exc:  # pragma: no cover - environment-dependent
    suppress_moved_pairs = None
    _IMPORT_OK = False
    _IMPORT_ERROR = exc


@unittest.skipUnless(_IMPORT_OK, "compare_set_gui dependencies unavailable: %s" % _IMPORT_ERROR)
class SuppressMovedPairsTest(unittest.TestCase):
    def test_small_shift_is_suppressed(self):
        removed = [(0.0, 0.0, 10.0, 10.0)]
        added = [(1.5, 1.0, 11.5, 11.0)]

        kept_removed, kept_added, suppressed = suppress_moved_pairs(removed, added)

        self.assertEqual(suppressed, 1)
        self.assertEqual(kept_removed, [])
        self.assertEqual(kept_added, [])

    def test_different_size_not_suppressed(self):
        removed = [(0.0, 0.0, 10.0, 10.0)]
        added = [(20.0, 20.0, 40.0, 40.0)]

        kept_removed, kept_added, suppressed = suppress_moved_pairs(removed, added)

        self.assertEqual(suppressed, 0)
        self.assertEqual(kept_removed, removed)
        self.assertEqual(kept_added, added)


if __name__ == "__main__":
    unittest.main()
