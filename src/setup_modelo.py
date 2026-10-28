"""Baixa o modelo all-MiniLM-L6-v2 em ONNX para models/minilm (executar UMA vez).

Depois deste passo o app é 100% offline: nenhum outro módulo toca a rede.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import projeto_dir  # noqa: E402

ARQUIVOS = [
    "onnx/model.onnx",           # pesos (~90 MB)
    "tokenizer.json",            # tokenizador BERT uncased
    "tokenizer_config.json",
    "special_tokens_map.json",
    "vocab.txt",
]
REPO = "https://huggingface.co/onnx-community/all-MiniLM-L6-v2-ONNX/resolve/main"


def main() -> None:
    import urllib.request

    destino = projeto_dir() / "models" / "minilm"
    destino.mkdir(parents=True, exist_ok=True)
    for remoto in ARQUIVOS:
        alvo = destino / Path(remoto).name
        if alvo.exists() and alvo.stat().st_size > 1000:
            print(f"já existe: {alvo.name}")
            continue
        print(f"baixando: {remoto} …")
        urllib.request.urlretrieve(f"{REPO}/{remoto}", alvo)
        print(f"  ok: {alvo} ({alvo.stat().st_size // 1024} KB)")
    print("\nModelo pronto. A partir daqui, tudo roda offline.")


if __name__ == "__main__":
    main()
