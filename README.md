# Medicalsys-Automation

Automatiza a alteração em massa de status de pacientes no sistema Medicalsys, via interface web, utilizando **Python** e **Playwright** (CDP).

---

## Como funciona

O script conecta-se a um navegador Chromium já aberto (via Chrome DevTools Protocol), localiza a aba do Medicalsys, lê todos os pacientes da tela atual e altera o status de cada um para o destino escolhido. Nenhum dado é digitado às cegas — há uma **prévia com contagens** antes de qualquer alteração.

---

## Pré-requisitos

- Python 3.x instalado
- Um navegador Chromium (Chrome, Brave ou Edge)

---

## Configuração inicial

> Estes passos são executados **uma única vez** ao configurar o projeto.

**1. Crie e ative o ambiente virtual**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**2. Instale as dependências**

```powershell
pip install -r requirements.txt
playwright install chromium
```

---

## Uso

> Estes passos são repetidos **a cada vez** que for executar a automação.

**1. Abra o navegador com depuração remota habilitada**

Execute **apenas um** dos comandos abaixo em um novo terminal PowerShell:

```powershell
# Google Chrome
chrome.exe --remote-debugging-port=9222 --user-data-dir="$HOME\medicalsys_debug_profile"

# Brave Browser
& "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" --remote-debugging-port=9222 --user-data-dir="$HOME\medicalsys_debug_profile"

# Microsoft Edge
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --remote-debugging-port=9222 --user-data-dir="$HOME\medicalsys_debug_profile"
```

> **Por que um perfil separado?** Navegadores Chromium não permitem depuração remota no perfil padrão enquanto ele já está em uso. O `--user-data-dir` cria um perfil isolado só para a automação.

**2. No navegador aberto:** acesse o Medicalsys, faça login e navegue até a tela com a lista de pacientes.

**3. Ative o ambiente virtual** (no terminal onde vai rodar o script)

```powershell
.venv\Scripts\Activate.ps1
```

**4. Execute o script**

```powershell
python main.py
```

O script irá:
1. Conectar ao navegador aberto na porta `9222`
2. Localizar a aba do Medicalsys automaticamente
3. Exibir um menu para você escolher o status de destino
4. Mostrar uma **prévia** com contagem de pacientes e pedir confirmação (`sim`)
5. Processar e alterar os status, exibindo o resultado de cada paciente
6. Exibir um **relatório final** com alterados, ignorados, falhas e itens para revisão manual

---

## Configurações (`config.py`)

| Variável | Descrição | Padrão |
|---|---|---|
| `DEV_PREFIX` | Se definido (ex.: `"TESTE_"`), a automação **só opera em pacientes cujo nome comece com esse prefixo**. Para produção real, defina como `None`. | `"TESTE_"` |
| `MAX_CONSECUTIVE_FAILURES` | Número de falhas consecutivas que aciona parada de emergência. | `3` |
| `DEFAULT_TIMEOUT_MS` | Timeout padrão para ações do Playwright (ms). | `10000` |

> **Importante:** antes do primeiro uso em produção, certifique-se de definir `DEV_PREFIX = None` em `medicalsys_automation/config.py`.

---

## Segurança

- A execução pode ser interrompida a qualquer momento com **Ctrl+C** — o script aguarda o paciente atual ser concluído e exibe um relatório parcial.
- Pacientes com **nomes duplicados** (sem ID estável) e pacientes **não cadastrados** são marcados automaticamente para revisão manual e não são alterados.
- Com `DEV_PREFIX` ativo, se qualquer paciente real estiver na lista, a operação é **abortada antes de qualquer alteração**.
