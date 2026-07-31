#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Model: Mapa de IPs da rede de lojas."""

# Subnets do range 103–168 que NÃO existem
_EXCLUDED_SUBNETS = {109, 110, 126, 131, 135, 163, 167}


def gerar_ips_lojas(porta: str = "8443", custom_ips: list[str] | None = None) -> list[dict]:
    """
    Gera a lista completa de IPs dos controllers.
    custom_ips: IPs adicionais cadastrados pelo usuário.
    """
    lojas = []

    # Range principal de exemplo (faixa RFC 5737 de documentacao): .103 ate .168
    # Os IPs reais das lojas devem ser cadastrados em custom_ips (config local).
    for subnet in range(103, 169):
        if subnet not in _EXCLUDED_SUBNETS:
            lojas.append({
                "ip": f"203.0.113.{subnet}",
                "port": porta,
                "label": f"203.0.113.{subnet}",
            })

    # IPs fixos extras (exemplos RFC 5737)
    for ip, label in [("198.51.100.40", "198.51.100.40"), ("192.0.2.27", "192.0.2.27"),
                       ("192.0.2.202", "192.0.2.202"), ("192.0.2.231", "192.0.2.231")]:
        lojas.append({"ip": ip, "port": porta, "label": label})

    # IPs personalizados do usuário
    existing = {l["ip"] for l in lojas}
    if custom_ips:
        for ip in custom_ips:
            ip = ip.strip()
            if ip and ip not in existing:
                lojas.append({"ip": ip, "port": porta, "label": ip})
                existing.add(ip)

    return lojas
