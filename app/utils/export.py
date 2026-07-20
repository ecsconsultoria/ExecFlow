"""CSV export utility — gera arquivos CSV compatíveis com Excel (UTF-8 BOM)."""
import csv
import io
from flask import Response


def csv_response(filename: str, headers: list[str], rows: list[list[str]]) -> Response:
    """Gera uma Flask Response com conteúdo CSV.

    Args:
        filename: Nome do arquivo para download (ex: 'rfqs_2026-07-20.csv').
        headers: Lista de colunas (ex: ['Nº RFQ', 'Cliente', ...]).
        rows: Lista de linhas, cada linha é uma lista de strings.
    """
    buf = io.StringIO()
    # UTF-8 BOM para Excel reconhecer acentos
    buf.write("﻿")
    writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    buf.seek(0)
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": "text/csv; charset=utf-8",
        },
    )
