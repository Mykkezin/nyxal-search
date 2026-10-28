"""Geração de embeddings 100% locais com ONNX Runtime (all-MiniLM-L6-v2).

Nenhuma chamada de rede: o modelo é carregado de models/minilm e roda em CPU.
"""
from functools import lru_cache

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

from paths import pasta_modelo

MAX_TOKENS = 250  # janela curta: embeddings de frases, não de documentos inteiros


@lru_cache(maxsize=1)
def _sessao() -> tuple[Tokenizer, ort.InferenceSession]:
    """Carrega tokenizer + sessão ONNX uma única vez (lazy, ~1s)."""
    m = pasta_modelo()
    tok = Tokenizer.from_file(str(m / "tokenizer.json"))
    tok.no_padding()            # padding manual por lote (o do config é fixo em 128)
    tok.enable_truncation(MAX_TOKENS)
    opts = ort.SessionOptions()
    sess = ort.InferenceSession(
        str(m / "model.onnx"), sess_options=opts, providers=["CPUExecutionProvider"]
    )
    return tok, sess


def _pad(lote: list, mlen: int):
    """Monta input_ids + attention_mask com padding explícito até o maior do lote."""
    ids, mask = [], []
    for e in lote:
        n = len(e)
        ids.append(e + [0] * (mlen - n))
        mask.append([1] * n + [0] * (mlen - n))
    return np.array(ids, "int64"), np.array(mask, "int64")


def embeddings(textos: list[str], batch: int = 16) -> np.ndarray:
    """Codifica listas de texto em vetores L2-normalizados (384 dimensões)."""
    tok, sess = _sessao()
    saida = np.empty((len(textos), 384), dtype="float32")
    for i in range(0, len(textos), batch):
        encs = [tok.encode(t) for t in textos[i : i + batch]]
        mlen = max(len(e.ids) for e in encs)
        ids, mask = _pad([e.ids for e in encs], mlen)
        out = sess.run(
            None,
            {"input_ids": ids, "attention_mask": mask, "token_type_ids": np.zeros_like(ids)},
        )[0]
        # mean pooling respeitando a máscara (ignora [PAD]) + normalização L2
        m = mask[:, :, None].astype("float32")
        v = (out * m).sum(1) / m.sum(1)
        saida[i : i + len(encs)] = v / np.linalg.norm(v, axis=1, keepdims=True)
    return saida


def embedding(texto: str) -> np.ndarray:
    """Atalho para um único texto (usado na busca)."""
    return embeddings([texto])[0]
