# 📶 UniFi WiFi Manager

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

## 📄 Licença

Distribuído sob a licença MIT. Veja [LICENSE](LICENSE).
