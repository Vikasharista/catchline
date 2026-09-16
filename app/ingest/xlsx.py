from pathlib import Path

import openpyxl

from app.ingest.router import Chunk, IngestedDoc


def ingest(path: Path) -> IngestedDoc:
    wb = openpyxl.load_workbook(path, data_only=True)
    chunks: list[Chunk] = []

    for ws in wb.worksheets:
        grid = []
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is None:
                    continue
                # Keep values as displayed, including decimal commas — the
                # extraction model reads them exactly as written (PRD §7.4).
                grid.append(f"{cell.coordinate}: {cell.value}")
        if grid:
            chunks.append(
                Chunk(kind="table", content="\n".join(grid), locator=f"{ws.title}!{ws.dimensions}")
            )

    return IngestedDoc(filename=path.name, kind="xlsx", chunks=chunks)
