import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path

DB_PATH = os.environ.get(
    "POKEDEX_DB",
    str(Path(__file__).resolve().parent / "data" / "pokedex.sqlite"),
)

# limite de partidas vivas ao mesmo tempo; as mais antigas são descartadas
MAX_SESSIONS = int(os.environ.get("POKEDEX_MAX_SESSIONS", "200"))
# partida sem atividade por este tempo é descartada (segundos)
SESSION_TTL = int(os.environ.get("POKEDEX_SESSION_TTL", str(60 * 60)))

# sessões ativas: session_id -> dict com a conexão e o estado da partida
sessions = {}
_sessions_lock = threading.Lock()

MYSTERY_VIEWS_SQL = """
CREATE TEMP VIEW mystery_pokemon AS
SELECT
    p.height,
    p.weight,
    sp.generation_id AS generation,
    (SELECT t.identifier FROM pokemon_types pt JOIN types t ON t.id = pt.type_id
     WHERE pt.pokemon_id = p.id AND pt.slot = 1) AS type_1,
    (SELECT t.identifier FROM pokemon_types pt JOIN types t ON t.id = pt.type_id
     WHERE pt.pokemon_id = p.id AND pt.slot = 2) AS type_2,
    (SELECT COUNT(*) FROM pokemon_species s2
     WHERE s2.evolution_chain_id = sp.evolution_chain_id) AS evolution_chain_length
FROM pokemon p
JOIN pokemon_species sp ON sp.id = p.species_id
WHERE p.id = {secret_id};

CREATE TEMP VIEW mystery_pokemon_stats AS
SELECT s.identifier AS stat_name, ps.base_stat AS base_value
FROM pokemon_stats ps
JOIN stats s ON s.id = ps.stat_id
WHERE ps.pokemon_id = {secret_id};

CREATE TEMP VIEW mystery_pokemon_abilities AS
SELECT a.identifier AS ability_name, pa.is_hidden AS is_hidden
FROM pokemon_abilities pa
JOIN abilities a ON a.id = pa.ability_id
WHERE pa.pokemon_id = {secret_id};

CREATE TEMP VIEW mystery_pokemon_moves AS
SELECT DISTINCT m.identifier AS move_name, pmm.identifier AS learn_method
FROM pokemon_moves pm
JOIN moves m ON m.id = pm.move_id
JOIN pokemon_move_methods pmm ON pmm.id = pm.pokemon_move_method_id
WHERE pm.pokemon_id = {secret_id};
"""


def _pick_random_pokemon_id(conn):
    cur = conn.execute(
        "SELECT id FROM pokemon WHERE is_default = 1 AND id <= 721 "
        "ORDER BY RANDOM() LIMIT 1"
    )
    return cur.fetchone()[0]


def _new_connection():
    return sqlite3.connect(
        f"file:{DB_PATH}?mode=ro", uri=True, check_same_thread=False
    )


def _sweep_locked(now):
    """Remove partidas expiradas. Chamar com _sessions_lock adquirido."""
    for sid in list(sessions):
        if now - sessions[sid]["touched"] > SESSION_TTL:
            _close_locked(sid)


def _close_locked(sid):
    session = sessions.pop(sid, None)
    if session:
        try:
            session["conn"].close()
        except sqlite3.Error:
            pass


def create_session():
    """Cria uma nova partida: abre conexão somente leitura, sorteia um
    pokémon e cria as mystery views escondidas nessa conexão."""
    now = time.time()
    conn = _new_connection()

    secret_id = _pick_random_pokemon_id(conn)
    dex_row = conn.execute(
        "SELECT sp.id, sp.identifier FROM pokemon p "
        "JOIN pokemon_species sp ON sp.id = p.species_id "
        "WHERE p.id = ?",
        (secret_id,),
    ).fetchone()
    secret_dex, secret_name = dex_row

    conn.executescript(MYSTERY_VIEWS_SQL.format(secret_id=secret_id))

    session_id = str(uuid.uuid4())
    session = {
        "conn": conn,
        "lock": threading.Lock(),
        "secret_id": secret_id,
        "secret_dex": secret_dex,
        "secret_name": secret_name,
        "score": 10,
        "sudden_death": False,
        "game_over": False,
        "touched": now,
    }

    with _sessions_lock:
        _sweep_locked(now)
        while len(sessions) >= MAX_SESSIONS:
            oldest = min(sessions, key=lambda s: sessions[s]["touched"])
            _close_locked(oldest)
        sessions[session_id] = session

    return session_id, session


def get_session(session_id):
    with _sessions_lock:
        session = sessions.get(session_id)
        if session is None:
            raise KeyError("sessão não encontrada")
        session["touched"] = time.time()
        return session


def close_all():
    """Fecha todas as conexões (usado ao desligar o servidor)."""
    with _sessions_lock:
        for sid in list(sessions):
            _close_locked(sid)
