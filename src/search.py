"""Busca semântica local: pergunta em português, recebe os arquivos mais prováveis.

Embedding da consulta x cosseno contra todos os trechos no banco; o score de
um arquivo é o melhor trecho dele (max-pooling), com bônus pequeno se o nome
conversa direto com a consulta.
"""
import re
from pathlib import Path

import embeddings
import store


def _palavras(consulta: str) -> set[str]:
    """Palavras-chave da consulta (>=3 letras, minúsculas) para bônus de nome."""
    return {w for w in re.findall(r"\w{3,}", consulta.lower(), re.UNICODE)}


def buscar(consulta: str, top_k: int = 5) -> list[dict]:
    """Retorna top_k arquivos: {caminho, score, preview, trecho_melhor}."""
    con = store.abrir()
    vetores, metadados = store.carregar_matriz(con)
    if len(vetores) == 0:
        return []

    q = embeddings.embedding(consulta)
    scores = vetores @ q  # cosseno puro: vetores já normalizados (L2)

    # agrupa por arquivo mantendo o melhor trecho (max-pooling)
    melhores: dict[str, tuple[float, str, str]] = {}
    for score, (arquivo_id, caminho, texto, preview) in zip(scores, metadados):
        atual = melhores.get(caminho)
        if atual is None or score > atual[0]:
            melhores[caminho] = (float(score), texto, preview)

    # bônus lexical: nome do arquivo contendo palavras da consulta
    chaves = _palavras(consulta)
    ranked = []
    for caminho, (score, texto, preview) in melhores.items():
        nome = Path(caminho).stem.lower()
        bonus = 0.06 * sum(1 for w in chaves if w in nome)
        ranked.append({"caminho": caminho, "score": score + bonus,
                       "preview": preview, "trecho_melhor": texto})
    ranked.sort(key=lambda r: r["score"], reverse=True)
    return ranked[:top_k]


def imprimir(resultados: list[dict]) -> None:
    if not resultados:
        print("Nada encontrado. Rode o indexador primeiro: python src/indexer.py <pasta>")
        return
    for i, r in enumerate(resultados, 1):
        print(f"\n{i}. {Path(r['caminho']).name}   (score {r['score']:.3f})")
        print(f"   {r['caminho']}")
        print(f"   {r['preview'][:160]}…")


if __name__ == "__main__":
    import sys

    imprimir(buscar(" ".join(sys.argv[1:]) or "aquele contrato da Santos que baixei ontem"))
