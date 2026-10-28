"""Extração de texto dos formatos suportados: .txt, .md, .pdf, .docx.

Falhou a leitura? Devolve texto vazio e o indexador segue adiante —
o nome do arquivo ainda é indexado e buscável.
"""
from pathlib import Path

EXTENSOES = {".txt", ".md", ".markdown", ".pdf", ".docx"}

MAX_CHARS = 30_000  # teto de conteúdo por arquivo (MVP: não afogar a RAM)


def _texto_pdf(caminho: Path) -> str:
    from pypdf import PdfReader

    leitor = PdfReader(str(caminho))
    pedacos = []
    for pagina in leitor.pages:
        pedacos.append(pagina.extract_text() or "")
        if sum(len(p) for p in pedacos) > MAX_CHARS:
            break
    return "\n".join(pedacos)


def _texto_docx(caminho: Path) -> str:
    import docx

    d = docx.Document(str(caminho))
    return "\n".join(p.text for p in d.paragraphs)


def _texto_plano(caminho: Path) -> str:
    dados = caminho.read_bytes()[: MAX_CHARS * 2]
    for codificacao in ("utf-8", "latin-1"):
        try:
            return dados.decode(codificacao)
        except UnicodeDecodeError:
            continue
    return ""


def extrair_texto(caminho: Path) -> str:
    """Retorna o texto bruto do arquivo (ou '' se ilegível/binário)."""
    ext = caminho.suffix.lower()
    try:
        if ext == ".pdf":
            return _texto_pdf(caminho)
        if ext == ".docx":
            return _texto_docx(caminho)
        if ext in {".txt", ".md", ".markdown"}:
            return _texto_plano(caminho)
    except Exception:
        return ""
    return ""


def dividir_em_trechos(texto: str, tamanho: int = 1200, passo: int = 900) -> list[str]:
    """Janela deslizante de caracteres — o MiniLM trunca em ~250 tokens de qualquer forma."""
    texto = " ".join(texto.split())  # colapsa espaços/quebras do PDF
    if not texto:
        return []
    trechos = []
    for i in range(0, len(texto), passo):
        trecho = texto[i : i + tamanho]
        if len(trecho) > 40 or i == 0:  # descarta apêndices minúsculos do fim
            trechos.append(trecho)
        if i + tamanho >= len(texto):
            break
    return trechos[:24]  # no máximo 24 trechos por arquivo no MVP
