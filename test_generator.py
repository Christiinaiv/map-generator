import unittest
from islands import (
    generate_map,
    _try_generate,
    build_island_graph,
    is_connected,
    graph_stats,
    Region,
    RegionType,
    PLAYER_MIN_AREA,
    PLAYER_AREA_DIFF,
    MIN_AREA,
)

TEST_SEEDS = (42, 7, 99, 123, 2025)


class TestBalance(unittest.TestCase):

    def _get_regions(self, islands=3, clusters=3, seed=42):
        regions, cg = generate_map(islands, clusters, seed=seed)
        self.assertIsNotNone(regions, f"generate_map повернув None (seed={seed})")
        return regions, cg


    def test_player_sectors_are_largest(self):
        for seed in TEST_SEEDS:
            with self.subTest(seed=seed):
                regions, _ = self._get_regions(seed=seed)
                players = [r for r in regions if r.type == "player"]
                others  = [r for r in regions if r.type != "player"]
                self.assertGreater(
                    min(p.area for p in players),
                    max(o.area for o in others),
                    msg=f"Порушення: сектор гравця не найбільший (seed={seed})"
                )

    def test_player_area_difference(self):
        for seed in TEST_SEEDS:
            with self.subTest(seed=seed):
                regions, _ = self._get_regions(seed=seed)
                players = [r for r in regions if r.type == "player"]
                diff = abs(players[0].area - players[1].area)
                self.assertLess(
                    diff, PLAYER_AREA_DIFF,
                    msg=f"Різниця {diff:.4f} > ліміту {PLAYER_AREA_DIFF} (seed={seed})"
                )

    def test_player_min_area(self):
        for seed in TEST_SEEDS:
            with self.subTest(seed=seed):
                regions, _ = self._get_regions(seed=seed)
                players = [r for r in regions if r.type == "player"]
                for p in players:
                    self.assertGreaterEqual(
                        p.area, 0.030,
                        msg=f"Гравець занадто маленький: {p.area:.4f} (seed={seed})"
                    )

    def test_no_degenerate_sectors(self):
        regions, _ = self._get_regions(islands=4, clusters=4, seed=7)
        for r in regions:
            self.assertGreater(
                r.area, 0.003,
                msg=f"Вироджений сектор типу '{r.type}': площа {r.area:.6f}"
            )


    def test_correct_island_count(self):
        for n in (3, 4, 5):
            for seed in (10, 55, 200):
                with self.subTest(n=n, seed=seed):
                    regions, _ = self._get_regions(islands=n, clusters=3, seed=seed)
                    count = sum(1 for r in regions if r.type == "island")
                    self.assertEqual(
                        count, n,
                        msg=f"Очікувалось {n} островів, отримано {count} (seed={seed})"
                    )

    def test_correct_cluster_count(self):
        for n in (3, 4, 5):
            for seed in (10, 55, 200):
                with self.subTest(n=n, seed=seed):
                    regions, _ = self._get_regions(islands=3, clusters=n, seed=seed)
                    centers = sum(1 for r in regions if r.type == "cluster_center")
                    self.assertEqual(
                        centers, n,
                        msg=f"Очікувалось {n} кластерів, отримано {centers} (seed={seed})"
                    )

    def test_always_two_players(self):
        for seed in TEST_SEEDS:
            with self.subTest(seed=seed):
                regions, _ = self._get_regions(seed=seed)
                count = sum(1 for r in regions if r.type == "player")
                self.assertEqual(count, 2, msg=f"Гравців {count} != 2 (seed={seed})")


    def test_reproducibility(self):
        for seed in TEST_SEEDS:
            with self.subTest(seed=seed):
                r1, _ = generate_map(3, 3, seed=seed)
                r2, _ = generate_map(3, 3, seed=seed)
                areas1 = sorted(r.area for r in r1)
                areas2 = sorted(r.area for r in r2)
                self.assertEqual(
                    areas1, areas2,
                    msg=f"Різні результати при однаковому seed={seed}"
                )


    def test_graph_has_nodes(self):
        regions, _ = self._get_regions(islands=3, clusters=3, seed=42)
        from shapely.geometry import box
        fake_islands = [
            ("player", box(0.0, 0.0, 0.2, 0.2), True),
            ("island", box(0.25, 0.25, 0.45, 0.45), True),
            ("island", box(0.3, 0.3, 0.5, 0.5), False),
        ]
        g = build_island_graph(fake_islands, max_dist=0.20)
        self.assertEqual(len(g), 3)

    def test_is_connected_true(self):
        graph = {0: [1, 2], 1: [0], 2: [0, 3], 3: [2]}
        self.assertTrue(is_connected(graph))

    def test_is_connected_false(self):
        graph = {0: [1], 1: [0], 2: [3], 3: [2]}   
        self.assertFalse(is_connected(graph))

    def test_graph_stats_keys(self):
        graph = {0: [1], 1: [0, 2], 2: [1]}
        stats = graph_stats(graph)
        for key in ("nodes", "edges", "avg_degree", "max_degree",
                    "min_degree", "connected"):
            self.assertIn(key, stats, msg=f"Відсутнє поле '{key}' у graph_stats")


    def test_generation_fails_gracefully(self):
        result, cg = _try_generate(
            island_number=3, cluster_number=3,
            player_min_area=0.99,   
            player_area_diff=0.001,
            min_area=0.5,
            attempts=5,             
        )
        self.assertIsNone(result)
        self.assertIsNone(cg)


    def test_region_is_dataclass(self):
        regions, _ = self._get_regions(seed=42)
        for r in regions:
            self.assertIsInstance(
                r, Region,
                msg=f"Очікувався Region, отримано {type(r)}"
            )

    def test_region_type_is_string(self):
        allowed = {rt.value for rt in RegionType}
        regions, _ = self._get_regions(seed=42)
        for r in regions:
            self.assertIn(
                r.type, allowed,
                msg=f"Невідомий тип регіону: '{r.type}'"
            )

    def test_region_area_positive(self):
        regions, _ = self._get_regions(seed=42)
        for r in regions:
            self.assertGreater(r.area, 0, msg=f"Нульова площа у регіоні {r.type}")


unittest.main(verbosity=2)