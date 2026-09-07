# 📶 UniFi WiFi Manager (English)

Desktop application for **managing and monitoring Wi-Fi networks** based
on **UniFi (Ubiquiti)** controllers. It allows checking the status of controllers
from multiple units/stores, listing WLANs and connected clients, validating visitor
access CPFs, and generating reports.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![CustomTkinter](https://img.shields.io/badge/CustomTkinter-5.2+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## ✨ Features

- 🔎 Discovery and status of multiple UniFi controllers (network map)
- 📡 Listing of WLANs (SSIDs) and online clients per controller
- 🧾 CPF validation (offline + optional confirmation via BrasilAPI)
- 📊 Report generation (PDF via `reportlab`, with fallback to TXT)
- 🎨 Modern interface (CustomTkinter), light/dark theme

## 🚀 Installation

```bash
pip install -r requirements.txt
python main.py
```

## ⚙️ Configuration

Credentials and IPs are **not** kept in the repository. On the first run,
inform the controller's host/username/password through the interface itself — the
settings are saved in `config.json` (which is in `.gitignore`).

You can also start from the template:

```bash
cp config.example.json config.json
# edit config.json with the real values
```

| Field                 | Description                                                      |
|-----------------------|------------------------------------------------------------------|
| `username` / password | UniFi Controller credentials (password is obfuscated in file).   |
| `port`                | Controller port (default `8443`).                                |
| `last_ip`             | Last accessed controller.                                        |
| `custom_ips`          | Additional controller IPs to monitor.                            |
| `wlan_company_filter` | Company SSID keyword used to filter WLANs.                       |

The default network map (`models/network_map.py`) uses example addresses from
ranges reserved for documentation (**RFC 5737**). Register the real IPs of
your units in `custom_ips` in the local `config.json`.

## 🗂️ Structure

```
wifi_manager/
├── main.py                 # Entry point
├── config.example.json     # Configuration template (no secrets)
├── controllers/            # Orchestration (app_controller)
├── models/                 # config, unifi_api, network_map, cpf_validator
├── views/                  # Interface (CustomTkinter)
├── utils/                  # logger, reports
└── resources/icon/         # Icon
```

## 🔒 Security

- Credentials, real IPs, and logs are **not** versioned (see `.gitignore`).
- Password "obfuscation" in `config.json` is only to prevent display in plain
  text — it is **not** strong encryption. Protect the file in the usage environment.

## 📄 License

> ⚠️ **Repository made available for portfolio purposes only.** The code can
> be viewed, but **cannot** be copied, downloaded, used, or
> reused in other projects. See the [License](#-license) section and the
> [`LICENSE`](./LICENSE) file.

---

# 📶 UniFi WiFi Manager (Português)

Aplicação desktop para **gerenciamento e monitoramento de redes Wi-Fi** baseadas
em controladores **UniFi (Ubiquiti)**. Permite verificar o status dos controllers
de várias unidades/lojas, listar WLANs e clientes conectados, validar CPF de
acesso de visitantes e gerar relatórios.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![CustomTkinter](https://img.shields.io/badge/CustomTkinter-5.2+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## ✨ Funcionalidades

- 🔀 **Dois modos de conexão:**
  - **Controlador** — uma loja por controlador/IP fixo (cada loja é uma LAN).
  - **Site** — um **controlador central** e cada loja é um **site** do UniFi,
    acessada pelo **código do site**.
- 🔎 Descoberta e status de múltiplos controladores/sites UniFi (mapa de rede)
- 📡 Listagem de WLANs (SSIDs) e clientes online por controlador/site
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
| `mode`                | `controller` (IP por loja) ou `site` (controlador central).      |
| `central_host`        | IP/host do controlador central (usado no modo `site`).           |
| `sites`               | Lista de `{ "name", "code" }` — lojas cadastradas no modo `site`.|

O mapa de rede padrão (`models/network_map.py`) usa endereços de exemplo das
faixas reservadas para documentação (**RFC 5737**). Cadastre os IPs reais das
suas unidades em `custom_ips` no `config.json` local.

### 🔀 Modos de conexão

Alterne o modo no topo da área **Conexão** (segmentos **Controlador** / **Site**):

- **Controlador** (padrão): informe o **IP** do controlador da loja e conecte.
  Cada loja é uma LAN com seu próprio controlador (site `default`).
- **Site** (controlador centralizado): na aba **Configurações**, informe o
  **IP do controlador central** e cadastre cada loja como **nome + código do
  site**. O código é o trecho após `/site/` na URL do UniFi, por exemplo:

  ```
  https://192.0.2.1:8443/manage/site/ab12cd34/dashboard
                                     └── código do site ──┘
  ```

  Você pode colar o **código** ou a **URL inteira** no campo de código — o
  sistema extrai o código automaticamente. Depois, na área **Conexão**, escolha
  a loja no seletor e conecte. O usuário/senha são os mesmos para todos os
  sites (a troca é apenas de site, como no seletor "Current site" do UniFi).
  Internamente, cada requisição usa `/api/s/<código>/…`.

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

### Logs da aplicação

As mensagens exibidas na aba **Log** são salvas em arquivos `.txt` diários,
separados pelo usuário do Windows que executou o programa. Ao iniciar o
aplicativo, semanas já encerradas são agrupadas em um `.zip` por usuário,
considerando a semana de segunda-feira a domingo. Os arquivos ficam na pasta
`logs` ao lado do executável.

## 📄 Licença

> ⚠️ **Repositório disponibilizado apenas para portfólio.** O código pode
> ser visualizado, mas **não** pode ser copiado, baixado, usado ou
> reaproveitado em outros projetos. Veja a seção [Licença](#-licença) e o
> arquivo [`LICENSE`](./LICENSE).
