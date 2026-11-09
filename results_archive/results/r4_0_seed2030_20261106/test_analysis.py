import unittest

from analysis import jaccard, match_clusters, lifetimes


class OfflineDiagnosticsTests(unittest.TestCase):
    def test_jaccard(self):
        self.assertEqual(jaccard({1, 2}, {2, 3}), 1 / 3)
        self.assertEqual(jaccard({1}, {1}), 1)

    def test_matching_ignores_cluster_id(self):
        pairs, splits, merges = match_clusters({1: {1, 2, 3}, 2: {4, 5, 6}},
                                               {20: {4, 5, 6}, 10: {1, 2, 3}})
        self.assertEqual({(a, b) for a, b, _ in pairs}, {(1, 10), (2, 20)})
        self.assertEqual(splits, [])
        self.assertEqual(merges, [])

    def test_split_and_merge_use_full_overlap_graph(self):
        _, splits, _ = match_clusters({1: {1, 2, 3, 4}},
                                     {10: {1, 2}, 20: {3, 4}})
        self.assertEqual(splits, [1])
        _, _, merges = match_clusters({1: {1, 2}, 2: {3, 4}},
                                     {10: {1, 2, 3, 4}})
        self.assertEqual(merges, [10])

    def test_lifetime_boundaries(self):
        rows = lifetimes([('old', 1_000_000, 4_000_000, True),
                          ('active', 4_000_000, None, False)], 10_000_000)
        self.assertEqual(rows[0]['duration_s'], 3)
        self.assertTrue(rows[0]['left_boundary_unknown'])
        self.assertFalse(rows[0]['right_censored'])
        self.assertEqual(rows[1]['duration_s'], 6)
        self.assertTrue(rows[1]['right_censored'])


if __name__ == '__main__':
    unittest.main()
