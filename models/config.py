#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Model: Gerenciamento de configurações persistentes em JSON."""

import json
import base64
import logging
from pathlib import Path


class ConfigManager:
    """Gerencia configurações salvas em arquivo JSON com ofuscação de senha."""

    _KEY = b"wifi-manager-obfuscation-key"

    DEFAULTS = {
        "username": "",
        "password": "",
        "port": "8443",
        "last_ip": "",
        "wlan_company_filter": "",  # palavra-chave do SSID da empresa (local)
        "validate_cpf_online": True,
        "theme": "dark",
        "custom_ips": [],
        "excluded_ips": [],
        "hosts_initialized": False,  # True após migração dos IPs padrão
        "excluded_ips": [],
        # Logging
        "log_rotation": "daily",   # daily | weekly | monthly
        "log_retention": 30,       # quantos arquivos compactados manter
        "log_level": "INFO",
    }

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.data: dict = dict(self.DEFAULTS)
        self.load()

    def load(self):
        """Carrega configurações do arquivo."""
        if not self.filepath.exists():
            return
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            if raw.get("_pw"):
                try:
                    raw["password"] = self._deobfuscate(raw.pop("_pw"))
                except Exception:
                    raw["password"] = ""
            self.data.update(raw)
        except Exception as e:
            logging.warning(f"[CONFIG] Erro ao carregar: {e}")

    def save(self):
        """Salva configurações no arquivo."""
        to_save = dict(self.data)
        pw = to_save.pop("password", "")
        if pw:
            to_save["_pw"] = self._obfuscate(pw)
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(to_save, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"[CONFIG] Erro ao salvar: {e}")

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value):
        self.data[key] = value

    def update(self, **kwargs):
        self.data.update(kwargs)

    def _obfuscate(self, text: str) -> str:
        key = self._KEY
        result = bytes([ord(c) ^ key[i % len(key)] for i, c in enumerate(text)])
        return base64.b64encode(result).decode()

    def _deobfuscate(self, encoded: str) -> str:
        key = self._KEY
        raw = base64.b64decode(encoded.encode())
        return ''.join(chr(b ^ key[i % len(key)]) for i, b in enumerate(raw))