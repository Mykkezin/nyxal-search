"""Indexador: varre pastas, extrai texto, gera embeddings e salva no banco local.

Rodando sem argumentos, indexa ~/Downloads. Só reprocessa arquivos novos ou
modificados (mtime), então passadas repetidas são rápidas.
"""
import time
from pathlib import Path

import embeddings
import store
from extractors import EXTENSOES, dividir_em_trechos, extrair_texto

# cache de navegadores/dependências — o AppData cobre o "Download" do navegador
IGNORAR_DIR = {"appdata", "node_modules", "__pycache__", ".venv", "venv", "$recycle.bin"}


def arquivos_indexaveis(raiz: Path):
    """Gera (caminho, mtime) de cada arquivo com extensão suportada."""
    for caminho in raiz.rglob("*"):
        if caminho.suffix.lower() not in EXTENSOES or not caminho.is_file():
            continue
        if any(p.lower() in IGNORAR_DIR for p in caminho.parts):
            continue
        try:
            yield caminho, caminho.stat().st_mtime
        except OSError:
            continue


def indexar(pastas: list[Path], verboso: bool = True) -> dict:
    """Indexa todas as pastas; retorna estatísticas da rodada."""
    con = store.abrir()
    resumo = {"novos": 0, "ignorados": 0, "sem_texto": 0, "tempo": 0.0}
    inicio = time.time()

    for raiz in pastas:
        raiz = Path(raiz).expanduser().resolve()
        if not raiz.is_dir():
            print(f"Pula (não existe): {raiz}")
            continue
        for caminho, mtime in arquivos_indexaveis(raiz):
            if not store.precisa_reindexar(con, caminho, mtime):
                resumo["ignorados"] += 1
                continue

            texto = extrair_texto(caminho)
            # o nome do arquivo sempre entra como trecho — "baixei ontem" ajuda
            # a achar pelo nome mesmo quando o PDF não tem texto extraível
            trechos = dividir_em_trechos(texto) or ([caminho.name] if texto == "" else [])
            corpo = (texto or caminho.name).replace("\n", " ")
            preview = (caminho.name + " — " + " ".join(corpo.split()))[:200]
            # nome + conteúdo juntos no embedding melhora a recall por assunto
            vetores = embeddings.embeddings(
                [f"{caminho.name}. {t}" for t in trechos] or [caminho.name]
            )
            store.salvar_arquivo(con, caminho, mtime, preview, trechos or [caminho.name], vetores)
            resumo["novos"] += 1
            if texto == "":
                resumo["sem_texto"] += 1
            if verboso:
                print(f"[{resumo['novos']}] indexado: {caminho.name}")

    resumo["tempo"] = time.time() - inicio
    if verboso:
        print(
            f"\nTotal no banco: {store.total_arquivos(con)} arquivos | "
            f"novos: {resumo['novos']} | já indexados: {resumo['ignorados']} | "
            f"sem texto extraível (só nome): {resumo['sem_texto']} | "
            f"tempo: {resumo['tempo']:.1f}s"
        )
    return resumo


if __name__ == "__main__":
    import sys

    alvos = [Path(a) for a in sys.argv[1:]] or [Path.home() / "Downloads"]
    indexar(alvos)
