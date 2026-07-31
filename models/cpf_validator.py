#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Model: Validação avançada de CPF com múltiplas camadas.

Camadas de verificação:
  1. Formato (11 dígitos)
  2. Dígitos repetidos (111.111.111-11)
  3. Dígitos verificadores (algoritmo oficial)
  4. CPFs de teste conhecidos
  5. Padrões sequenciais (heurística anti-gerador)
  6. Consulta online — BrasilAPI (SOMENTE confirmação positiva)

IMPORTANTE: A consulta online na BrasilAPI é instável. Muitos CPFs reais
retornam 404 porque a Receita Federal bloqueia consultas automatizadas.
Por isso, a consulta online NUNCA penaliza um CPF — ela só adiciona
confirmação positiva quando encontra o CPF na base.
"""

import re
import logging

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# ============ DADOS DE REFERÊNCIA ============

# Regiões fiscais por dígito (posição 8, base-0)
UF_FISCAL_REGIONS = {
    0: "RS",
    1: "DF, GO, MS, MT, TO",
    2: "AC, AM, AP, PA, RO, RR",
    3: "CE, MA, PI",
    4: "AL, PB, PE, RN",
    5: "BA, SE",
    6: "MG",
    7: "ES, RJ",
    8: "SP",
    9: "PR, SC",
}

# CPFs conhecidos usados em testes / geradores
CPFS_TESTE = {
    "12345678909", "01234567890", "98765432100",
    "11144477735", "00000000191",
    *(f"{d}" * 11 for d in range(10)),
}

# Padrões sequenciais comuns em CPFs gerados
SEQUENTIAL_PATTERNS = [
    re.compile(r'^0{5,}'),
    re.compile(r'^(\d)\1{4,}\d+'),
    re.compile(r'01234567'),
    re.compile(r'98765432'),
    re.compile(r'^(\d)\1(\d)\2(\d)\3(\d)\4'),
]


# ============ RESULTADO DA VALIDAÇÃO ============

class CPFValidationResult:
    """Resultado detalhado da validação de CPF."""

    def __init__(self):
        self.is_valid_format: bool = False
        self.is_valid_checksum: bool = False
        self.is_all_same: bool = False
        self.is_known_test: bool = False
        self.is_sequential: bool = False
        self.is_online_confirmed: bool = False    # True = CPF confirmado na Receita
        self.online_name: str | None = None
        self.online_status: str | None = None     # "found", "not_queried", "unavailable", "error"
        self.fiscal_region: str = ""
        self.cpf_formatted: str = ""
        self.cpf_raw: str = ""
        self.risk_level: str = "unknown"          # "valid", "suspect", "invalid"
        self.risk_reasons: list[str] = []

    @property
    def is_definitely_invalid(self) -> bool:
        """CPF que falha em verificações matemáticas."""
        return not self.is_valid_format or not self.is_valid_checksum or self.is_all_same

    @property
    def is_suspect_by_heuristic(self) -> bool:
        """CPF passa no checksum mas tem indicadores de geração artificial."""
        return self.is_known_test or self.is_sequential


# ============ FUNÇÃO PRINCIPAL ============

def validar_cpf(cpf_str: str, tentar_online: bool = True) -> CPFValidationResult:
    """
    Validação completa de CPF.

    A consulta online na BrasilAPI só CONFIRMA positivamente.
    Nunca marca um CPF como suspeito/inválido por causa de 404.
    """
    result = CPFValidationResult()
    cpf = re.sub(r'\D', '', cpf_str)
    result.cpf_raw = cpf

    # ── Camada 1: Formato ──
    if len(cpf) != 11:
        result.risk_level = "invalid"
        result.risk_reasons.append(f"Formato inválido ({len(cpf)} dígitos)")
        return result

    result.is_valid_format = True
    result.cpf_formatted = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
    result.fiscal_region = UF_FISCAL_REGIONS.get(int(cpf[8]), "Desconhecida")

    # ── Camada 2: Dígitos iguais ──
    if cpf == cpf[0] * 11:
        result.is_all_same = True
        result.risk_level = "invalid"
        result.risk_reasons.append("Todos os dígitos são iguais")
        return result

    # ── Camada 3: Dígitos verificadores ──
    for peso_inicial, pos_verificador in [(10, 9), (11, 10)]:
        soma = sum(int(cpf[i]) * (peso_inicial - i) for i in range(pos_verificador))
        resto = (soma * 10) % 11
        if resto == 10:
            resto = 0
        if resto != int(cpf[pos_verificador]):
            result.risk_level = "invalid"
            label = "Primeiro" if pos_verificador == 9 else "Segundo"
            result.risk_reasons.append(f"{label} dígito verificador inválido")
            return result

    result.is_valid_checksum = True

    # ── Camada 4: CPFs de teste ──
    if cpf in CPFS_TESTE:
        result.is_known_test = True
        result.risk_reasons.append("CPF presente na lista de testes conhecidos")

    # ── Camada 5: Padrões sequenciais ──
    for pattern in SEQUENTIAL_PATTERNS:
        if pattern.search(cpf):
            result.is_sequential = True
            result.risk_reasons.append("Padrão sequencial detectado (possível gerador)")
            break

    # ── Camada 6: Consulta online (BrasilAPI) ──
    # SOMENTE confirmação positiva — nunca penaliza
    if tentar_online and HAS_REQUESTS:
        result.online_status = _consultar_brasil_api(cpf, result)
    else:
        result.online_status = "not_queried"

    # ── Classificação final ──
    if result.is_definitely_invalid:
        result.risk_level = "invalid"
    elif result.is_suspect_by_heuristic:
        # Se a API confirmou o CPF, confia na API mesmo com heurística
        if result.is_online_confirmed:
            result.risk_level = "valid"
            result.risk_reasons.clear()
            result.risk_reasons.append("CPF confirmado na Receita Federal (heurística ignorada)")
        else:
            result.risk_level = "suspect"
    else:
        result.risk_level = "valid"

    return result


def _consultar_brasil_api(cpf: str, result: CPFValidationResult) -> str:
    """
    Consulta a BrasilAPI. Retorna o status da consulta.

    IMPORTANTE: NÃO marca como suspeito se retornar 404.
    A API é instável e retorna 404 para CPFs reais.
    """
    try:
        resp = requests.get(
            f"https://brasilapi.com.br/api/cpf/v1/{cpf}",
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            result.is_online_confirmed = True
            result.online_name = data.get('nome', '')
            return "found"
        elif resp.status_code == 404:
            # NÃO penalizar — API instável
            return "unavailable"
        else:
            return "unavailable"
    except requests.exceptions.Timeout:
        return "unavailable"
    except requests.exceptions.ConnectionError:
        return "unavailable"
    except Exception as e:
        logging.debug(f"[CPF] Erro na consulta online: {e}")
        return "error"


def extrair_cpf_de_notes(notes: str) -> str | None:
    """Tenta extrair um CPF do campo notes do voucher."""
    if not notes:
        return None
    # XXX.XXX.XXX-XX
    match = re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', notes)
    if match:
        return match.group()
    # 11 dígitos consecutivos
    match = re.search(r'\d{11}', notes)
    if match:
        return match.group()
    return None
