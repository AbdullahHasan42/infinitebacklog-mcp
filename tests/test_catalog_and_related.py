"""Lessons from the 2026-09-11 public catalog smoke test."""
from __future__ import annotations

import unittest

from infinitebacklog_mcp.config import (
    CATALOG_QUERY_PARAM,
    GAME_SEARCH_SELECTORS,
    catalog_search_path,
    is_filter_search_box,
    is_parent_game_url,
)


class CatalogSearchSelectorTests(unittest.TestCase):
    def test_game_search_id_is_first(self):
        self.assertEqual(GAME_SEARCH_SELECTORS[0], "#game-search")

    def test_does_not_use_generic_search_placeholder(self):
        joined = " ".join(GAME_SEARCH_SELECTORS)
        self.assertNotIn('placeholder*="Search"', joined)
        self.assertNotIn('input[type="search"]', joined)

    def test_platform_filter_is_skipped(self):
        self.assertTrue(is_filter_search_box("platforms-search", "Search for platform"))
        self.assertTrue(is_filter_search_box("genres-search", "Search for genre"))

    def test_game_search_is_not_a_filter(self):
        self.assertFalse(is_filter_search_box("game-search", "Search for a game"))
        self.assertFalse(is_filter_search_box("", "Search for a game"))

    def test_live_query_param_is_q_not_search(self):
        self.assertEqual(CATALOG_QUERY_PARAM, "q")
        self.assertEqual(catalog_search_path("Tomb Raider"), "/games?q=Tomb%20Raider")
        self.assertNotIn("search=", catalog_search_path("Hades"))


class ParentGameUrlTests(unittest.TestCase):
    def test_hades_2020_is_not_1995_or_edition(self):
        parent = "https://infinitebacklog.net/games/hades--1"
        self.assertTrue(is_parent_game_url(parent, "hades--1"))
        self.assertFalse(is_parent_game_url(parent, "hades"))
        self.assertFalse(
            is_parent_game_url(
                "https://infinitebacklog.net/games/hades-limited-edition",
                "hades--1",
            )
        )

    def test_strips_games_prefix(self):
        self.assertTrue(
            is_parent_game_url("https://infinitebacklog.net/games/hades--1", "games/hades--1")
        )


if __name__ == "__main__":
    unittest.main()
