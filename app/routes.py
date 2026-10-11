from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import game

router = APIRouter(prefix="/game")


class QueryRequest(BaseModel):
    session_id: str
    sql: str


class GuessRequest(BaseModel):
    session_id: str
    name: str


@router.post("/start")
def start():
    return game.start_game()


@router.post("/query")
def query(req: QueryRequest):
    try:
        return game.run_query(req.session_id, req.sql)
    except KeyError:
        raise HTTPException(status_code=404, detail="sessão não encontrada")


@router.post("/guess")
def guess(req: GuessRequest):
    try:
        return game.make_guess(req.session_id, req.name)
    except KeyError:
        raise HTTPException(status_code=404, detail="sessão não encontrada")


@router.get("/state")
def state(session_id: str):
    try:
        return game.get_state(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="sessão não encontrada")


@router.get("/schema")
def schema():
    return game.get_schema()
