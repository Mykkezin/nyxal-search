"""Banco vetorial local em SQLite (dentro de ~/.nyxal), sem serviços externos.

Cada trecho de arquivo vira uma linha com o embedding serializado como blob
float32. A busca carrega tudo em RAM e usa numpy — suficiente para dezenas
de milhares de arquivos no MVP.
"""
import sqlite3
from pathlib import Path

import numpy as np

from paths import pasta_dados

DIM = 384

_SCHEMA = """
CREATE TABLE IF NOT EXISTS arquivos (
    id      INTEGER PRIMARY KEY,
    caminho TEXT    UNIQUE,
    mtime   REAL,             -- modificação para reindexação incremental
    preview TEXT              -- primeiros 200 caracteres, exibidos na busca
);
CREATE TABLE IF NOT EXISTS trechos (
    id        INTEGER PRIMARY KEY,
    arquivo_id INTEGER REFERENCES arquivos(id) ON DELETE CASCADE,
    texto     TEXT,
    embedding BLOB            -- float32[DIM] serializado
);
CREATE INDEX IF NOT EXISTS idx_trechos_arquivo ON trechos(arquivo_id);
"""


def abrir() -> sqlite3.Connection:
    """Abre (ou cria) ~/.nyxal/busca.db com WAL eForeign Keys ligados."""
    con = sqlite3.connect(pasta_dados() / "busca.db")
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(_SCHEMA)
    return con


def precisa_reindexar(con: sqlite3.Connection, caminho: Path, mtime: float) -> bool:
    """True se o arquivo é novo ou mudou desde a última indexação."""
    linha = con.execute(
        "SELECT mtime FROM arquivos WHERE caminho = ?", (str(caminho),)
    ).fetchone()
    return linha is None or linha[0] != mtime


def salvar_arquivo(con: sqlite3.Connection, caminho: Path, mtime: float,
                   preview: str, textos: list[str], vetores: np.ndarray) -> None:
    """Substitui o arquivo e seus trechos no banco (transação única)."""
    con.execute("DELETE FROM arquivos WHERE caminho = ?", (str(caminho),))
    cur = con.execute(
        "INSERT INTO arquivos (caminho, mtime, preview) VALUES (?,?,?)",
        (str(caminho), mtime, preview),
    )
    arquivo_id = cur.lastrowid
    con.executemany(
        "INSERT INTO trechos (arquivo_id, texto, embedding) VALUES (?,?,?)",
        [
            (arquivo_id, texto, vetores[i].astype("float32").tobytes())
            for i, texto in enumerate(textos)
        ],
    )
    con.commit()


def remover_arquivo(con: sqlite3.Connection, caminho: str) -> None:
    con.execute("DELETE FROM arquivos WHERE caminho = ?", (caminho,))
    con.commit()


def carregar_matriz(con: sqlite3.Connection) -> tuple[np.ndarray, list[tuple[int, str]]]:
    """Carrega todos os vetores + metadados (arquivo_id, caminho) para a busca."""
    linhas = con.execute(
        """SELECT t.embedding, t.texto, a.id, a.caminho, a.preview
           FROM trechos t JOIN arquivos a ON a.id = t.arquivo_id"""
    ).fetchall()
    if not linhas:
        return np.empty((0, DIM), "float32"), []
    vetores = np.stack([np.frombuffer(l[0], "float32") for l in linhas])
    metadados = [(l[2], l[3], l[1], l[4]) for l in linhas]
    return vetores, metadados


def total_arquivos(con: sqlite3.Connection) -> int:
    return con.execute("SELECT COUNT(*) FROM arquivos").fetchone()[0]


def get_stats() -> dict:
    """Resumo do índice para a UI (arquivos e trechos indexados)."""
    con = abrir()
    trechos = con.execute("SELECT COUNT(*) FROM trechos").fetchone()[0]
    return {"files": total_arquivos(con), "chunks": trechos}
