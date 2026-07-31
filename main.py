#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UniFi Wi-Fi Manager
Entry point da aplicação.

Estrutura MVC:
    models/         → Dados, API, validação
    views/          → Interface gráfica
    controllers/    → Lógica de negócio
    utils/          → Relatórios, logging
    resources/icon/ → Coloque aqui o ícone (.ico para Windows, .png para geral)

Dependências:
    pip install customtkinter requests reportlab pillow
"""

import sys
import os
from pathlib import Path

# Configurar UTF-8 no Windows + ícone na barra de tarefas
if sys.platform == 'win32':
    import codecs
    # sys.stdout/stderr são None com --windowed (sem console).
    # Só redireciona para UTF-8 se o console estiver disponível.
    if sys.stdout is not None:
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    if sys.stderr is not None:
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "unifi.wifimanager.app.1")
    except Exception:
        pass

# Garantir que o diretório do projeto esteja no path
#
# Quando empacotado com PyInstaller (--onefile), __file__ aponta para a pasta
# temporária de extração (_MEIPASS), que é apagada ao fechar o .exe.
# Nesse caso usamos sys.executable para obter o diretório real do .exe,
# garantindo que config.json e logs sejam salvos ao lado do executável.
if getattr(sys, 'frozen', False):
    # Rodando como .exe gerado pelo PyInstaller
    APP_DIR = Path(sys.executable).parent
else:
    # Rodando direto como script .py
    APP_DIR = Path(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, str(APP_DIR))

from utils.logger import setup_logging
from models.config import ConfigManager
from controllers.app_controller import AppController

# ============ PATHS ============
# Recursos ficam junto ao .exe (pasta compartilhada, read-only)
ICON_DIR = APP_DIR / "resources" / "icon"
ICON_DIR.mkdir(parents=True, exist_ok=True)

# Config e logs ficam no %APPDATA% do usuário local
# → Cada usuário tem seu próprio config.json e logs
# → Permite múltiplos usuários rodando o mesmo .exe de uma pasta compartilhada
if sys.platform == 'win32':
    _USER_DATA = Path(os.environ.get("APPDATA", "")) / "UniFiWiFiManager"
else:
    _USER_DATA = Path.home() / ".unifi-wifi-manager"

_USER_DATA.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = _USER_DATA / "config.json"
LOG_DIR = APP_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# ── Migração automática: se existe config.json antigo ao lado do .exe, migra ──
_OLD_CONFIG = APP_DIR / "config.json"
if _OLD_CONFIG.exists() and not CONFIG_FILE.exists():
    try:
        import shutil
        shutil.copy2(_OLD_CONFIG, CONFIG_FILE)
        # Não remove o antigo para não afetar outros usuários que ainda não migraram
    except Exception:
        pass


def main():
    """Inicializa e executa a aplicação."""
    # Carregar configurações (precisa vir antes do logging para pegar preferências)
    config = ConfigManager(CONFIG_FILE)

    # Configurar logging (tenta usar rotação/compactação; cai no modo simples se estiver usando logger antigo)
    rotation = config.get("log_rotation", "daily")
    retention = config.get("log_retention", 30)
    level = config.get("log_level", "INFO")

    # Nome do log inclui o usuário Windows para não conflitar na pasta compartilhada
    # Ex: wifi_manager_lucasv.log, wifi_manager_maria.log
    win_user = os.environ.get("USERNAME", os.environ.get("USER", "default")).lower()
    log_name = f"wifi_manager_{win_user}"

    try:
        setup_logging(LOG_DIR, rotation=rotation, retention=retention, level=level, log_name=log_name)
    except TypeError:
        setup_logging(LOG_DIR)
    # Criar controller (que cria a window internamente)
    controller = AppController(APP_DIR, config)

    # Executar
    controller.run()


if __name__ == "__main__":
    main()