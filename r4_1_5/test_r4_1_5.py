"""Small deterministic checks for the offline R4-1.5 definitions."""
import unittest

from r4_1_5_analysis import cohort, path_available, match_clusters


class OfflineDefinitions(unittest.TestCase):
    def test_generation_cohort_includes_losses_and_pending(self):
        rows = [
            {'outcome': 'delivered', 'e2e_delay_us': '2000'},
            {'outcome': 'PacketLifetime', 'e2e_delay_us': ''},
            {'outcome': 'IncompleteAtHorizon', 'e2e_delay_us': ''},
        ]
        x = cohort(rows)
        self.assertEqual(x['total'], 3)
        self.assertEqual(x['pdr_lower'], 1 / 3)
        self.assertEqual(x['pdr_upper'], 2 / 3)
        self.assertEqual(x['resolved_pdr'], 1 / 2)
        self.assertEqual(x['delivered_delay_ms'], 2)

    def test_path_requires_bs_endpoint(self):
        x = {'paths_to_bs': {'1': [1, 8, 0], '2': [2, 8]}}
        self.assertTrue(path_available(x, 1))
        self.assertFalse(path_available(x, 2))
        self.assertFalse(path_available(x, 3))

    def test_member_match_survives_cluster_id_change(self):
        pairs, split, merge = match_clusters({1: {1, 2, 3}}, {9: {2, 3, 4}})
        self.assertEqual([(a, b) for a, b, _ in pairs], [(1, 9)])
        self.assertEqual((split, merge), ([], []))

    def test_split_is_separate_from_one_to_one_match(self):
        pairs, split, merge = match_clusters({1: {1, 2, 3, 4}},
                                             {7: {1, 2}, 8: {3, 4}})
        self.assertEqual(len(pairs), 1)
        self.assertEqual(split, [1])
        self.assertEqual(merge, [])


if __name__ == '__main__':
    unittest.main()
