# src/ui.py — Nyxal Search Spotlight (janela escura sem borda, Ctrl+Espaço)
#
# Mesma arquitetura que você mandou, mas ligada na API real do projeto:
#   search.buscar(query)      -> [{caminho, score, preview, trecho_melhor}]
#   indexer.indexar(pastas)   -> reindexa Downloads (nova pasta = botão extra)
#   store.get_stats()         -> {"files": ..., "chunks": ...}
import logging
import os
import subprocess
import sys
import threading
import warnings
from pathlib import Path

import customtkinter as ctk

sys.path.insert(0, str(Path(__file__).resolve().parent))
import indexer  # noqa: E402
import search   # noqa: E402
import store    # noqa: E402

warnings.simplefilter("ignore")
logging.getLogger("pypdf").setLevel(logging.ERROR)

BG = "#0a0a0f"
BG_INPUT = "#15151f"
BG_CARD = "#1c1c28"
BG_CARD_SEL = "#232336"
ACCENT = "#3b82ff"
TEXT = "#e6e6ff"
TEXT_DIM = "#7a7a9a"
TEXT_BODY = "#b8b8d0"

LARGURA, ALTURA = 720, 480


class NyxalApp:
    def __init__(self, residente: bool = False):
        # residente=True → abre escondido e espera Ctrl+Espaço (estilo Raycast)
        self.residente = residente
        self.resultados: list[dict] = []
        self.cards: list[ctk.CTkFrame] = []
        self.sel = -1
        self.geracao = 0          # descarta resultados de buscas antigas
        self._debounce = None
        self._arrastar = None     # origem do arrastar-janela-sem-borda

        ctk.set_appearance_mode("dark")

        self.root = ctk.CTk()
        self.root.title("Nyxal Search")
        self.root.configure(fg_color=BG)
        self.root.overrideredirect(True)               # sem borda, Spotlight
        self.root.geometry(self._geo_central())
        self.root.attributes("-topmost", True)
        try:                                           # leve transparência
            self.root.attributes("-alpha", 0.97)
        except Exception:
            pass

        self.root.bind("<Escape>", self._on_escape)
        self.build_ui()

        if residente:
            self.root.withdraw()
        else:
            self.root.after(100, self.focus_input)
        self.iniciar_hotkey()

    # ---------- janela ----------
    def _geo_central(self) -> str:
        """Centro horizontal, um terço acima — fica bom em ultrawide."""
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x = (sw - LARGURA) // 2
        y = int(sh * 0.22)
        return f"{LARGURA}x{ALTURA}+{x}+{y}"

    def build_ui(self):
        topo = ctk.CTkFrame(self.root, fg_color=BG, corner_radius=0)
        topo.pack(fill="x", padx=20, pady=(16, 4))

        self.entry_var = ctk.StringVar()
        self.entry = ctk.CTkEntry(
            topo, textvariable=self.entry_var, height=52,
            font=("Segoe UI", 20), fg_color=BG_INPUT, text_color=TEXT,
            placeholder_text="descreva o arquivo que você procura…",
            border_color="#2a2a3a", border_width=1, corner_radius=12,
        )
        self.entry.pack(fill="x")
        self.entry.bind("<KeyRelease>", self._on_digitar)
        self.entry.bind("<Return>", self._abrir_selecionado)
        self.entry.bind("<Down>", lambda e: self._mover(1))
        self.entry.bind("<Up>", lambda e: self._mover(-1))
        self.entry.bind("<Control-r>", lambda e: self.reindexar())

        # arrastar a janela puxando o topo (overrideredirect não tem barra)
        topo.bind("<ButtonPress-1>", self._press)
        topo.bind("<B1-Motion>", self._mover_janela)

        stats = store.get_stats()
        dica = "Ctrl+Espaço abre • setas escolhem • Enter abre o arquivo • ESC fecha"
        if stats["files"] == 0:
            dica = "índice vazio — Ctrl+R para indexar Downloads"
        self.status = ctk.CTkLabel(
            self.root,
            text=f"{stats['files']} arquivos • 100% offline • {dica}",
            font=("Segoe UI", 9), text_color=TEXT_DIM, anchor="w",
        )
        self.status.pack(fill="x", padx=22, pady=(2, 6))

        self.list_frame = ctk.CTkFrame(self.root, fg_color=BG, corner_radius=0)
        self.list_frame.pack(fill="both", expand=True, padx=15, pady=(0, 12))

    # ---------- busca ----------
    def _on_digitar(self, event=None):
        """Debounce de 150 ms: não rebusca a cada tecla."""
        if self._debounce:
            self.root.after_cancel(self._debounce)
        self._debounce = self.root.after(150, self._disparar)

    def _disparar(self):
        self._debounce = None
        consulta = self.entry_var.get().strip()
        if len(consulta) < 2:
            self._limpar()
            return
        self.geracao += 1
        gen = self.geracao
        threading.Thread(target=self._buscar_bg, args=(consulta, gen), daemon=True).start()

    def _buscar_bg(self, consulta: str, gen: int):
        try:
            resultados = search.buscar(consulta, top_k=5)
        except Exception as exc:                      # nunca derrubar a UI
            self.root.after(0, lambda: self._sem_resultado(f"erro: {exc}"))
            return
        self.root.after(0, lambda: self._mostrar(resultados, gen))

    def _mostrar(self, resultados, gen):
        if gen != self.geracao:                     # veio de busca já superada
            return
        self.resultados = resultados
        self._limpar_cards()
        self.sel = 0 if resultados else -1
        if not resultados:
            self._sem_resultado("nada encontrado — tente outras palavras")
            return
        for r in resultados:
            card = ctk.CTkFrame(self.list_frame, fg_color=BG_CARD, corner_radius=10,
                                border_width=1, border_color=BG_CARD)
            card.pack(fill="x", pady=4, padx=2)

            nome = os.path.basename(r["caminho"])
            titulo = ctk.CTkLabel(card, text=nome, font=("Segoe UI", 12, "bold"),
                                  text_color=TEXT, anchor="w")
            titulo.pack(fill="x", padx=12, pady=(8, 0))
            linha2 = ctk.CTkLabel(
                card, text=f"{r['caminho']}  •  {r['score']:.3f}",
                font=("Segoe UI", 8), text_color=TEXT_DIM, anchor="w")
            linha2.pack(fill="x", padx=12)
            preview = ctk.CTkLabel(
                card, text=r["preview"][:150], font=("Segoe UI", 9),
                text_color=TEXT_BODY, anchor="w", justify="left")
            preview.pack(fill="x", padx=12, pady=(2, 8))

            i = len(self.cards)
            for w in (card, titulo, linha2, preview):
                w.bind("<Button-1>", lambda e, idx=i: self._abrir_indice(idx))
                w.bind("<Enter>", lambda e, idx=i: self._selecionar(idx))
            self.cards.append(card)
        self._pintar_selecao()

    def _sem_resultado(self, msg: str):
        self._limpar_cards()
        ctk.CTkLabel(self.list_frame, text=msg, font=("Segoe UI", 11),
                     text_color=TEXT_DIM).pack(pady=24)

    def _limpar(self):
        self._limpar_cards()
        self.resultados = []
        self.sel = -1

    def _limpar_cards(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.cards = []

    # ---------- seleção por teclado ----------
    def _mover(self, passo: int):
        if not self.resultados:
            return
        self.sel = max(0, min(len(self.resultados) - 1, self.sel + passo))
        self._pintar_selecao()

    def _selecionar(self, idx: int):
        self.sel = idx
        self._pintar_selecao()

    def _pintar_selecao(self):
        for i, card in enumerate(self.cards):
            card.configure(fg_color=BG_CARD_SEL if i == self.sel else BG_CARD,
                           border_color=ACCENT if i == self.sel else BG_CARD)

    def _abrir_selecionado(self, event=None):
        if 0 <= self.sel < len(self.resultados):
            self._abrir_indice(self.sel)

    def _abrir_indice(self, idx: int):
        self.sel = idx
        self._pintar_selecao()
        self.abrir_arquivo(self.resultados[idx]["caminho"])

    def abrir_arquivo(self, caminho: str):
        try:
            if sys.platform == "win32":
                os.startfile(caminho)  # noqa: S606 — API nativa Windows
            else:
                subprocess.Popen(["xdg-open", caminho])
        except Exception:
            pass
        self._esconder()

    # ---------- indexação ----------
    def reindexar(self):
        """Ctrl+R: reindexa Downloads em background sem travar a janela."""
        pasta = Path.home() / "Downloads"
        self.status.configure(text=f"indexando {pasta} … 100% local")

        def fundo():
            resumo = indexer.indexar([pasta], verboso=False)
            stats = store.get_stats()
            self.root.after(0, lambda: self.status.configure(
                text=f"{stats['files']} arquivos • {resumo['novos']} novos em "
                     f"{resumo['tempo']:.1f}s • Ctrl+Espaço / setas / Enter / ESC"))
        threading.Thread(target=fundo, daemon=True).start()

    # ---------- hotkey global ----------
    def iniciar_hotkey(self):
        """Ctrl+Espaço abre/fecha de qualquer app, estilo Raycast."""
        try:
            from pynput import keyboard

            def on_activar():
                # callbacks do pynput vêm de outra thread → always after()
                self.root.after(0, self._toggle)

            teclado = keyboard.GlobalHotKeys({"<ctrl>+<space>": on_activar})
            teclado.daemon = True
            teclado.start()
            self.teclado = teclado
        except Exception:
            # sem hotkey global (ex.: sessão sem X11) — a janela segue abrindo normal
            pass

    def _toggle(self):
        if self.root.state() == "withdrawn":
            self.root.deiconify()
            self.focus_input()
        else:
            self._esconder()

    def _esconder(self):
        if self.residente:
            self.root.withdraw()          # vive escondido, revive no Ctrl+Espaço
        else:
            self.root.destroy()           # modo simples: ESC encerra o processo

    def _on_escape(self, event=None):
        self._esconder()

    def focus_input(self):
        self.entry.focus_force()
        self.entry.icursor("end")

    # ---------- arrastar ----------
    def _press(self, event):
        self._arrastar = (event.x_root - self.root.winfo_x(),
                          event.y_root - self.root.winfo_y())

    def _mover_janela(self, event):
        if self._arrastar:
            ox, oy = self._arrastar
            self.root.geometry(f"+{event.x_root - ox}+{event.y_root - oy}")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    NyxalApp(residente="--residente" in sys.argv).run()
