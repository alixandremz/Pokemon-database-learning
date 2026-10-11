import re

BLOCKED_KEYWORDS = [
    "drop", "delete", "update", "insert", "alter", "attach", "detach",
    "pragma", "vacuum", "replace", "create", "trigger", "reindex",
    "analyze",
]

# funções que abrem arquivos ou carregam código nativo
BLOCKED_FUNCTIONS = [
    "load_extension", "readfile", "writefile", "edit", "fts3_tokenizer",
]

_STRING_OR_IDENTIFIER = re.compile(r"'[^']*'|\"[^\"]*\"")
_IDENTIFIER_START = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


def _without_literals(sql: str) -> str:
    """Remove strings e identificadores entre aspas antes de procurar
    palavras-chave, para não bloquear valores como 'update'."""
    return _STRING_OR_IDENTIFIER.sub("''", sql)


def validate_select(sql: str) -> str:
    """Valida que o SQL é um único comando de leitura seguro.
    Retorna o SQL limpo ou lança ValueError com o motivo da rejeição."""
    cleaned = sql.strip()
    if not cleaned:
        raise ValueError("a query está vazia")
    if "\x00" in cleaned:
        raise ValueError("a query contém caracteres inválidos")

    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].rstrip()
    if ";" in cleaned:
        raise ValueError("só é permitido 1 comando por vez")

    # comentários não têm uso numa consulta de leitura e servem para esconder
    # palavras-chave, então são recusados
    if "--" in cleaned or "/*" in cleaned:
        raise ValueError("comentários não são permitidos")

    if not _IDENTIFIER_START.match(cleaned):
        raise ValueError("só comandos SELECT (ou WITH ... SELECT) são permitidos")

    scan = _without_literals(cleaned).lower()

    if re.search(r"\bsqlite_", scan):
        raise ValueError("acesso às tabelas internas do SQLite é bloqueado")
    if re.search(r"\bexplain\b", scan):
        raise ValueError("comando não permitido: explain")

    for word in BLOCKED_KEYWORDS:
        if re.search(rf"\b{word}\b", scan):
            raise ValueError(f"palavra bloqueada na query: {word}")

    for func in BLOCKED_FUNCTIONS:
        if re.search(rf"\b{func}\s*\(", scan):
            raise ValueError(f"função bloqueada na query: {func}")

    return cleaned
