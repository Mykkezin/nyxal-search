"""Localizador do projeto e da pasta de dados .nyxal (tudo offline, dentro do usuário)."""
import os
import sys
from pathlib import Path


def projeto_dir() -> Path:
    """Pasta raiz do projeto (funciona em dev e depois no .exe do PyInstaller)."""
    if getattr(sys, "frozen", False):  # empacotado pelo PyInstaller
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def pasta_dados() -> Path:
    """~/.nyxal — banco vetorial e cache, uma pasta só, nunca sai da máquina."""
    p = Path(os.environ.get("NYXAL_DATA_DIR", Path.home() / ".nyxal"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def pasta_modelo() -> Path:
    """Modelo ONNX embutido no projeto (fallback: copia em ~/.nyxal/models)."""
    embutido = projeto_dir() / "models" / "minilm"
    if (embutido / "model.onnx").exists():
        return embutido
    local = pasta_dados() / "models" / "minilm"
    if (local / "model.onnx").exists():
        return local
    raise FileNotFoundError(
        f"Modelo ONNX não encontrado. Espere em: {embutido} ou {local}"
    )
