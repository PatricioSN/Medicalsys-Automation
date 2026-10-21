"""Configurações globais da automação do Medicalsys."""

# Porta e endereço do Chrome DevTools Protocol (CDP)
CDP_PORT = 9222
CDP_URL = f"http://localhost:{CDP_PORT}"

# Trecho da URL usado para identificar a aba do Medicalsys no navegador
URL_SUBSTRING = "medicalsys.com.br"

# Lista oficial dos 7 status disponíveis no Medicalsys (texto exato exibido no site)
STATUS_OPTIONS = [
    "Agendado",
    "Aguardando",
    "Confirmado",
    "Não compareceu",
    "Finalizado",
    "Remarcado",
    "Cancelado",
]

# Trava de segurança para desenvolvimento e homologação:
# - Se for string (ex.: "TESTE_"), a automação SÓ altera pacientes cujo nome comece com esse prefixo.
#   Se qualquer outro paciente for encontrado na lista, a execução é abortada ANTES de alterar qualquer um.
# - Para uso real em produção, defina: DEV_PREFIX = None
DEV_PREFIX = "TESTE_"

# Limite de falhas consecutivas antes de interromper a execução automaticamente por segurança
MAX_CONSECUTIVE_FAILURES = 3

# Timeout padrão em milissegundos para ações e esperas do Playwright
DEFAULT_TIMEOUT_MS = 10000
