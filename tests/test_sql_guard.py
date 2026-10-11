import unittest

from app.sql_guard import validate_select


class ValidateSelectTest(unittest.TestCase):
    def test_accepts_plain_select(self):
        self.assertEqual(validate_select("SELECT 1"), "SELECT 1")

    def test_accepts_with_cte(self):
        sql = "WITH t AS (SELECT 1) SELECT * FROM t"
        self.assertEqual(validate_select(sql), sql)

    def test_strips_one_trailing_semicolon(self):
        self.assertEqual(validate_select("SELECT 1;"), "SELECT 1")

    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            validate_select("   ")

    def test_rejects_multiple_statements(self):
        with self.assertRaises(ValueError):
            validate_select("SELECT 1; SELECT 2")

    def test_rejects_non_select(self):
        with self.assertRaises(ValueError):
            validate_select("UPDATE pokemon SET height = 1")

    def test_rejects_blocked_keywords(self):
        for sql in ("DROP TABLE pokemon", "SELECT * FROM sqlite_master",
                    "INSERT INTO pokemon VALUES (1)", "PRAGMA table_info(pokemon)"):
            with self.assertRaises(ValueError, msg=sql):
                validate_select(sql)

    def test_rejects_comments(self):
        with self.assertRaises(ValueError):
            validate_select("SELECT 1 -- comentário")
        with self.assertRaises(ValueError):
            validate_select("SELECT 1 /* comentário */")

    def test_rejects_blocked_functions(self):
        with self.assertRaises(ValueError):
            validate_select("SELECT load_extension('x')")

    def test_keywords_inside_strings_are_allowed(self):
        sql = "SELECT * FROM pokemon WHERE identifier LIKE '%update%'"
        self.assertEqual(validate_select(sql), sql)


if __name__ == "__main__":
    unittest.main()
