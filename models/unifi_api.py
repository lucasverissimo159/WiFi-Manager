#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Model: Cliente para a API do UniFi Network Controller."""

import logging
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class UniFiController:
    """Cliente HTTP para a API REST do UniFi Controller."""

    def __init__(self, host: str, port: str, username: str, password: str, site: str = 'default'):
        self.base_url = f"https://{host}:{port}"
        self.username = username
        self.password = password
        self.site = site
        self.session = requests.Session()
        self.session.verify = False
        self.logged_in = False

    # ---- Autenticação ----

    def login(self) -> tuple[bool, str]:
        """Realizar login no controller. Retorna (sucesso, mensagem)."""
        url = f"{self.base_url}/api/login"
        payload = {"username": self.username, "password": self.password, "remember": True}
        try:
            resp = self.session.post(url, json=payload, timeout=15)
            if resp.status_code == 200:
                self.logged_in = True
                logging.info(f"[LOGIN] Sucesso em {self.base_url}")
                return True, "Login realizado com sucesso!"
            elif resp.status_code == 401:
                return False, "Usuário ou senha incorretos."
            else:
                return False, f"Erro HTTP {resp.status_code}"
        except requests.exceptions.ConnectionError:
            return False, "Não foi possível conectar ao controller.\nVerifique o IP e a porta."
        except requests.exceptions.Timeout:
            return False, "Tempo limite de conexão excedido."
        except Exception as e:
            return False, f"Erro: {str(e)}"

    def logout(self):
        """Realizar logout."""
        try:
            self.session.post(f"{self.base_url}/api/logout", timeout=5)
        except Exception:
            pass
        self.logged_in = False

    # ---- WLAN (Redes Wi-Fi) ----

    def get_wlans(self) -> list[dict]:
        """Obter todas as redes Wi-Fi configuradas."""
        return self._get(f"/api/s/{self.site}/rest/wlanconf")

    def enable_wlan(self, wlan_id: str, wlan_name: str) -> bool:
        """Habilitar uma rede Wi-Fi."""
        url = f"{self.base_url}/api/s/{self.site}/rest/wlanconf/{wlan_id}"
        try:
            resp = self.session.put(url, json={"enabled": True}, timeout=10)
            if resp.status_code == 200:
                logging.info(f"[WLAN] '{wlan_name}' HABILITADA")
                return True
            logging.error(f"[WLAN] Falha ao habilitar '{wlan_name}': HTTP {resp.status_code}")
            return False
        except Exception as e:
            logging.error(f"[WLAN] Erro ao habilitar '{wlan_name}': {e}")
            return False

    def disable_wlan(self, wlan_id: str, wlan_name: str) -> bool:
        """Desabilitar uma rede Wi-Fi."""
        url = f"{self.base_url}/api/s/{self.site}/rest/wlanconf/{wlan_id}"
        try:
            resp = self.session.put(url, json={"enabled": False}, timeout=10)
            if resp.status_code == 200:
                logging.info(f"[WLAN] '{wlan_name}' DESABILITADA")
                return True
            return False
        except Exception as e:
            logging.error(f"[WLAN] Erro: {e}")
            return False

    # ---- Clientes / Dispositivos conectados ----

    def get_online_clients(self) -> list[dict]:
        """Obter clientes atualmente conectados."""
        return self._get(f"/api/s/{self.site}/stat/sta")

    # ---- Devices (APs, Switches, Gateways) ----

    def get_devices(self) -> list[dict]:
        """Obter todos os dispositivos de rede (APs, switches, etc.)."""
        return self._get(f"/api/s/{self.site}/stat/device")

    # ---- Vouchers ----

    def get_vouchers(self) -> list[dict]:
        """Obter todos os vouchers do hotspot."""
        return self._get(f"/api/s/{self.site}/stat/voucher")

    def delete_voucher(self, voucher_id: str) -> bool:
        """Deletar um voucher pelo ID."""
        url = f"{self.base_url}/api/s/{self.site}/cmd/hotspot"
        payload = {"cmd": "delete-voucher", "_id": voucher_id}
        try:
            resp = self.session.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                logging.info(f"[VOUCHER] {voucher_id} DELETADO")
                return True
            logging.error(f"[VOUCHER] Falha ao deletar {voucher_id}: HTTP {resp.status_code}")
            return False
        except Exception as e:
            logging.error(f"[VOUCHER] Erro: {e}")
            return False

    # ---- Guests ----

    def get_guests(self) -> list[dict]:
        """Obter guests ativos no hotspot."""
        return self._get(f"/api/s/{self.site}/stat/guest")

    # ---- Helper ----

    def _get(self, path: str) -> list[dict]:
        """GET genérico que retorna o campo 'data' da resposta."""
        url = f"{self.base_url}{path}"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.json().get('data', [])
            return []
        except Exception as e:
            logging.error(f"[API] Erro em GET {path}: {e}")
            return []
