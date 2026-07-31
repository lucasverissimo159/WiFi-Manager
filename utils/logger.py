#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Configuração centralizada de logging.

- Rotação por tempo (diária/semanal/mensal)
- Nome do arquivo rotacionado inclui YYYY-MM-DD: wifi_manager_2026-03-02.log.zip
- Compactação automática (ZIP) para economizar espaço
- Limpeza inteligente: mantém apenas `retention` arquivos .zip mais recentes
"""

import sys
import logging
import re
from datetime import datetime
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler
from zipfile import ZipFile, ZIP_DEFLATED


# ──────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────

def _zip_rotator(source: str, dest: str) -> None:
    """Compacta o log rotacionado em ZIP e remove o original."""
    src = Path(source)
    dst = Path(dest)
    dst.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(dst, mode="w", compression=ZIP_DEFLATED, compresslevel=9) as zf:
        zf.write(src, arcname=src.name)

    try:
        src.unlink(missing_ok=True)
    except Exception:
        pass


def _make_namer(log_file: Path):
    """
    Retorna uma função namer que converte:
        /path/wifi_manager.log.2026-03-02
        -> /path/wifi_manager_2026-03-02.log.zip

    O TimedRotatingFileHandler entrega o path com sufixo de data acoplado
    ao final: <base>.<suffix>. Aqui separamos e reformatamos.
    """
    base_stem = log_file.stem          # "wifi_manager"
    log_dir   = log_file.parent

    def namer(default_name: str) -> str:
        p = Path(default_name)
        name = p.name  # ex.: "wifi_manager.log.2026-03-02"

        # Tenta extrair sufixo de data (YYYY-MM-DD ou YYYY-MM-DD_HH-MM-SS)
        match = re.search(r'(\d{4}-\d{2}-\d{2}(?:[_-]\d{2}-\d{2}-\d{2})?)', name)
        date_tag = match.group(1).replace('_', '-') if match else datetime.now().strftime('%Y-%m-%d')

        new_name = f"{base_stem}_{date_tag}.log.zip"
        return str(log_dir / new_name)

    return namer


def _purge_old_zips(log_dir: Path, base_stem: str, retention: int) -> None:
    """Remove ZIPs mais antigos, mantendo apenas os `retention` mais recentes."""
    pattern = f"{base_stem}_*.log.zip"
    zips = sorted(log_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in zips[retention:]:
        try:
            old.unlink()
            logging.debug(f"[LOG] Rotação: removido {old.name}")
        except Exception as e:
            logging.warning(f"[LOG] Não foi possível remover {old.name}: {e}")


# ──────────────────────────────────────────────────────────
#  Setup principal
# ──────────────────────────────────────────────────────────

def setup_logging(
    log_dir: Path,
    rotation: str = "daily",    # daily | weekly | monthly
    retention: int = 30,
    level: int | str = logging.INFO,
    log_name: str = "wifi_manager",
) -> None:
    """Configura logging para arquivo e console com rotação + compactação ZIP.

    Arquivo ativo:     <log_name>.log
    Arquivo rotacionado: <log_name>_YYYY-MM-DD.log.zip

    Nota: .rar requer WinRAR externo; usamos .zip (nativo Python) com
    compressão DEFLATE nível 9, equivalente em economia de espaço.
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    rotation_map = {
        "daily":   ("midnight", 1),
        "weekly":  ("W0",       1),   # toda segunda-feira
        "monthly": ("midnight", 30),  # aprox. 30 dias
    }
    when, interval = rotation_map.get((rotation or "daily").lower(), ("midnight", 1))

    log_file  = log_dir / f"{log_name}.log"
    base_stem = log_file.stem

    handler = TimedRotatingFileHandler(
        filename=log_file,
        when=when,
        interval=interval,
        backupCount=max(int(retention), 1),
        encoding="utf-8",
        utc=False,
    )

    handler.namer   = _make_namer(log_file)   # wifi_manager_YYYY-MM-DD.log.zip
    handler.rotator = _zip_rotator             # compacta + remove .log original

    # Limpeza inicial de ZIPs além do limite de retenção
    _purge_old_zips(log_dir, base_stem, int(retention))

    fmt = logging.Formatter(
        "%(asctime)s - %(levelname)-8s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    # Evitar handlers duplicados se chamado mais de uma vez
    for h in list(root.handlers):
        root.removeHandler(h)

    handler.setFormatter(fmt)

    root.addHandler(handler)

    # sys.stdout é None quando compilado com --windowed (sem console).
    # Só adiciona o StreamHandler se stdout estiver disponível.
    if sys.stdout is not None:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(fmt)
        root.addHandler(console)

    logging.info(
        f"[LOG] Configurado — rotação: {rotation} | "
        f"retenção: {retention} arquivo(s) | nível: {logging.getLevelName(level)}"
    )