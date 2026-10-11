from . import db
from .sql_guard import validate_select

MYSTERY_TABLES = (
    "mystery_pokemon_stats",
    "mystery_pokemon_abilities",
    "mystery_pokemon_moves",
    "mystery_pokemon",
)

# corta resultados gigantes pra não travar o navegador
MAX_ROWS = 200

# tabelas do banco que o jogador pode consultar livremente, para comparar
PUBLIC_TABLES = [
    "pokemon",
    "pokemon_species",
    "pokemon_types",
    "types",
    "pokemon_stats",
    "stats",
    "pokemon_abilities",
    "abilities",
    "moves",
    "pokemon_moves",
    "pokemon_move_methods",
    "pokemon_egg_groups",
    "egg_groups",
    "pokemon_dex_numbers",
    "generations",
    "pokemon_colors",
    "pokemon_shapes",
    "pokemon_habitats",
    "pokemon_evolution",
    "evolution_chains",
]

MYSTERY_VIEWS = {
    "mystery_pokemon": (
        "Características do pokémon secreto",
        ["height", "weight", "generation", "type_1", "type_2", "evolution_chain_length"],
    ),
    "mystery_pokemon_stats": (
        "Stats base do pokémon secreto",
        ["stat_name", "base_value"],
    ),
    "mystery_pokemon_abilities": (
        "Habilidades do pokémon secreto",
        ["ability_name", "is_hidden"],
    ),
    "mystery_pokemon_moves": (
        "Movimentos do pokémon secreto",
        ["move_name", "learn_method"],
    ),
}

SPRITE_URL = (
    "https://raw.githubusercontent.com/PokeAPI/sprites/master/"
    "sprites/pokemon/other/official-artwork/{dex}.png"
)


def start_game():
    session_id, session = db.create_session()
    return {
        "session_id": session_id,
        "score": session["score"],
        "sudden_death": session["sudden_death"],
    }


def run_query(session_id: str, sql: str):
    session = db.get_session(session_id)

    if session["game_over"]:
        with session["lock"]:
            score = session["score"]
        return {"error": "o jogo já acabou, comece uma nova partida", "score": score}

    try:
        clean_sql = validate_select(sql)
    except ValueError as e:
        with session["lock"]:
            score = session["score"]
        return {"error": str(e), "score": score}

    touches_mystery = "mystery_" in clean_sql.lower()

    try:
        with session["lock"]:
            cur = session["conn"].execute(clean_sql)
            rows = cur.fetchmany(MAX_ROWS + 1)
            columns = [d[0] for d in cur.description] if cur.description else []
            truncated = len(rows) > MAX_ROWS
            rows = rows[:MAX_ROWS]
            if touches_mystery:
                _spend_point(session)
            score = session["score"]
            sudden_death = session["sudden_death"]
            game_over = session["game_over"]
    except Exception as e:
        with session["lock"]:
            score = session["score"]
        return {"error": f"erro no SQL: {e}", "score": score}

    return {
        "columns": columns,
        "rows": rows,
        "truncated": truncated,
        "score": score,
        "sudden_death": sudden_death,
        "game_over": game_over,
    }


def make_guess(session_id: str, name: str):
    session = db.get_session(session_id)

    with session["lock"]:
        if session["game_over"]:
            return {
                "error": "o jogo já acabou, comece uma nova partida",
                "score": session["score"],
            }

        correct = name.strip().lower() == session["secret_name"].lower()

        if correct:
            session["game_over"] = True
            return {
                "correct": True,
                "score": session["score"],
                "sudden_death": session["sudden_death"],
                "game_over": True,
                "message": f"você acertou! era o {session['secret_name']}",
                "secret_name": session["secret_name"],
                "secret_dex": session["secret_dex"],
                "sprite_url": SPRITE_URL.format(dex=session["secret_dex"]),
            }

        was_sudden_death = session["sudden_death"]
        _spend_point(session)

        if was_sudden_death:
            session["game_over"] = True
            return {
                "correct": False,
                "score": session["score"],
                "sudden_death": True,
                "game_over": True,
                "message": f"errou a chance final! era o {session['secret_name']}",
                "secret_name": session["secret_name"],
                "secret_dex": session["secret_dex"],
                "sprite_url": SPRITE_URL.format(dex=session["secret_dex"]),
            }

        return {
            "correct": False,
            "score": session["score"],
            "sudden_death": session["sudden_death"],
            "game_over": False,
            "message": "errado, tente de novo",
        }


def _spend_point(session):
    if session["sudden_death"]:
        return
    session["score"] -= 1
    if session["score"] <= 0:
        session["score"] = 0
        session["sudden_death"] = True


def get_state(session_id: str):
    session = db.get_session(session_id)
    with session["lock"]:
        return {
            "score": session["score"],
            "sudden_death": session["sudden_death"],
            "game_over": session["game_over"],
        }


def get_schema():
    """Lista as tabelas liberadas e suas colunas, para o painel de ajuda."""
    conn = db._new_connection()
    try:
        tables = []
        for name in PUBLIC_TABLES:
            try:
                cols = [r[1] for r in conn.execute(f"PRAGMA table_info({name})")]
            except Exception:
                continue
            if cols:
                tables.append({"name": name, "columns": cols})
        views = [
            {"name": name, "description": description, "columns": columns}
            for name, (description, columns) in MYSTERY_VIEWS.items()
        ]
    finally:
        conn.close()
    return {"tables": tables, "mystery_views": views}
