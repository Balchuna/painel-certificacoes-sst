"""Gera uma imagem PNG de cada página do PDF exportado pelo Power BI Desktop.

Uso:
    python scripts/imagens_do_pdf.py

Lê docs/painel/painel.pdf e grava docs/painel/1-visao-geral.png e as seguintes, uma por
página, com 1992 pixels de largura. O PDF sai do Power BI Desktop em Arquivo > Exportar >
Exportar em PDF (passo 12 de docs/MONTAGEM.md).
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

import pypdfium2

RAIZ = Path(__file__).resolve().parents[1]
PASTA = RAIZ / "docs" / "painel"
PDF = PASTA / "painel.pdf"
PAGINAS = ["Visão geral", "Matriz farol", "Agenda de reciclagem", "Qualidade dos dados"]
ESCALA = 2  # o PDF tem 996 x 576 pontos; em dobro, a imagem fica com 1992 x 1152 pixels


def nome_de_arquivo(posicao: int, titulo: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode()
    return f"{posicao}-{re.sub(r'[^a-z0-9]+', '-', sem_acento.lower()).strip('-')}.png"


def main() -> int:
    documento = pypdfium2.PdfDocument(PDF)
    if len(documento) != len(PAGINAS):
        print(f"{PDF.name} tem {len(documento)} páginas; o painel tem {len(PAGINAS)}.", file=sys.stderr)
        return 1
    for posicao, (pagina, titulo) in enumerate(zip(documento, PAGINAS), start=1):
        destino = PASTA / nome_de_arquivo(posicao, titulo)
        pagina.render(scale=ESCALA).to_pil().save(destino, optimize=True)
        print(destino.relative_to(RAIZ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
