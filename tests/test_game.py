import unittest

from app import db, game


class GameTest(unittest.TestCase):
    def setUp(self):
        self.session_id, self.session = db.create_session()

    def tearDown(self):
        db.sessions.pop(self.session_id, None)

    def test_start_has_full_score(self):
        state = game.start_game()
        self.assertEqual(state["score"], 10)
        self.assertFalse(state["sudden_death"])
        db.sessions.pop(state["session_id"], None)

    def test_mystery_query_costs_a_point(self):
        game.run_query(self.session_id, "SELECT * FROM mystery_pokemon")
        self.assertEqual(self.session["score"], 9)

    def test_public_table_query_is_free(self):
        game.run_query(self.session_id, "SELECT * FROM pokemon LIMIT 5")
        self.assertEqual(self.session["score"], 10)

    def test_invalid_sql_reports_error_without_spending(self):
        result = game.run_query(self.session_id, "DROP TABLE pokemon")
        self.assertIn("error", result)
        self.assertEqual(self.session["score"], 10)

    def test_results_are_row_capped(self):
        result = game.run_query(self.session_id, "SELECT * FROM pokemon")
        self.assertLessEqual(len(result["rows"]), game.MAX_ROWS)
        self.assertTrue(result["truncated"])

    def test_correct_guess_wins_and_reveals(self):
        result = game.make_guess(self.session_id, self.session["secret_name"].upper())
        self.assertTrue(result["correct"])
        self.assertTrue(result["game_over"])
        self.assertEqual(result["secret_name"], self.session["secret_name"])
        self.assertIn("sprite_url", result)

    def test_wrong_guesses_reach_sudden_death_then_loss(self):
        for _ in range(10):
            result = game.make_guess(self.session_id, "definitivamente-errado")
            self.assertFalse(result["game_over"])
        self.assertTrue(self.session["sudden_death"])
        self.assertEqual(self.session["score"], 0)

        final = game.make_guess(self.session_id, "ainda-errado")
        self.assertTrue(final["game_over"])
        self.assertEqual(final["secret_name"], self.session["secret_name"])

    def test_query_after_game_over_is_refused(self):
        game.make_guess(self.session_id, self.session["secret_name"])
        result = game.run_query(self.session_id, "SELECT * FROM mystery_pokemon")
        self.assertIn("error", result)

    def test_schema_lists_tables_and_views(self):
        schema = game.get_schema()
        names = {t["name"] for t in schema["tables"]}
        self.assertIn("pokemon", names)
        self.assertIn("pokemon_species", names)
        self.assertEqual(len(schema["mystery_views"]), 4)


if __name__ == "__main__":
    unittest.main()
