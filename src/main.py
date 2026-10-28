"""Nyxal Search — CLI do MVP (terminal, 100% offline).

Uso:
    python src/main.py index [pasta ...]        # padrão: ~/Downloads
    python src/main.py buscar <palavras...>     # busca semântica
    python src/main.py status                   # tamanho do índice
"""
import sys
import time
from pathlib import Path

# garante que os módulos locais sejam encontrados mesmo empacotado
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help", "ajuda"}:
        print(__doc__)
        return

    comando = sys.argv[1]

    if comando == "ui":
        # abre o Spotlight; --residente deixa escondido esperando Ctrl+Espaço
        from ui import NyxalApp

        NyxalApp(residente="--residente" in sys.argv).run()

    if comando == "index":
        from indexer import indexar

        pastas = [Path(a) for a in sys.argv[2:]] or [Path.home() / "Downloads"]
        indexar(pastas)

    elif comando == "buscar":
        from search import buscar, imprimir

        consulta = " ".join(sys.argv[2:])
        if not consulta:
            print("Digite a pergunta. Ex.: python src/main.py buscar contrato da santos")
            return
        inicio = time.time()
        imprimir(buscar(consulta))
        print(f"\n({time.time() - inicio:.2f}s, tudo local)")

    elif comando == "status":
        import store
        from paths import pasta_dados

        con = store.abrir()
        vetores, _ = store.carregar_matriz(con)
        print(f"Arquivos indexados: {store.total_arquivos(con)}")
        print(f"Trechos no banco:   {len(vetores)}")
        print(f"Banco:              {pasta_dados() / 'busca.db'}")

    else:
        print(f"Comando desconhecido: {comando}\n\n{__doc__}")


if __name__ == "__main__":
    main()
