# 📶 UniFi WiFi Manager

Aplicação desktop para **gerenciamento e monitoramento de redes Wi-Fi** baseadas
em controladores **UniFi (Ubiquiti)**. Permite verificar o status dos controllers
de várias unidades/lojas, listar WLANs e clientes conectados, validar CPF de
acesso de visitantes e gerar relatórios.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![CustomTkinter](https://img.shields.io/badge/CustomTkinter-5.2+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## ✨ Funcionalidades

- 🔎 Descoberta e status de múltiplos controladores UniFi (mapa de rede)
- 📡 Listagem de WLANs (SSIDs) e clientes online por controlador
- 🧾 Validação de CPF (offline + confirmação opcional via BrasilAPI)
- 📊 Geração de relatórios (PDF via `reportlab`, com fallback para TXT)
- 🎨 Interface moderna (CustomTkinter), tema claro/escuro

## 🚀 Instalação

```bash
pip install -r requirements.txt
python main.py
```

## ⚙️ Configuração

As credenciais e os IPs **não** ficam no repositório. Na primeira execução,
informe host/usuário/senha do controlador pela própria interface — as
configurações são salvas em `config.json` (que está no `.gitignore`).

Você também pode partir do template:

```bash
cp config.example.json config.json
# edite config.json com os valores reais
```

| Campo                 | Descrição                                                        |
|-----------------------|------------------------------------------------------------------|
| `username` / senha    | Credenciais do UniFi Controller (a senha é ofuscada no arquivo). |
| `port`                | Porta do controlador (padrão `8443`).                            |
| `last_ip`             | Último controlador acessado.                                     |
| `custom_ips`          | IPs adicionais de controladores a monitorar.                     |
| `wlan_company_filter` | Palavra-chave do SSID da empresa usada para filtrar as WLANs.    |

O mapa de rede padrão (`models/network_map.py`) usa endereços de exemplo das
faixas reservadas para documentação (**RFC 5737**). Cadastre os IPs reais das
suas unidades em `custom_ips` no `config.json` local.

## 🗂️ Estrutura

```
wifi_manager/
├── main.py                 # Ponto de entrada
├── config.example.json     # Template de configuração (sem segredos)
├── controllers/            # Orquestração (app_controller)
├── models/                 # config, unifi_api, network_map, cpf_validator
├── views/                  # Interface (CustomTkinter)
├── utils/                  # logger, reports
└── resources/icon/         # Ícone
```

## 🔒 Segurança

- Credenciais, IPs reais e logs **não** são versionados (veja `.gitignore`).
- A "ofuscação" da senha em `config.json` é apenas para evitar exibição em texto
  claro — **não** é criptografia forte. Proteja o arquivo no ambiente de uso.

## 📄 Licença

> ⚠️ **Repositório disponibilizado apenas para portfólio.** O código pode
> ser visualizado, mas **não** pode ser copiado, baixado, usado ou
> reaproveitado em outros projetos. Veja a seção [Licença](#-licença) e o
> arquivo [`LICENSE`](./LICENSE).
