"""Configurações globais da automação do Medicalsys."""

# Porta e endereço do Chrome DevTools Protocol (CDP)
CDP_PORT = 9222
CDP_URL = f"http://localhost:{CDP_PORT}"

# Trecho da URL ou título usado para identificar a aba correta do Medicalsys no navegador
# Exemplos observados na aplicação:
# - 'softon.tec.br'
# - 'pagina=paciente'
# - 'pagina=ficha'
URL_SUBSTRING = "softon.tec.br"

# Lista de status disponíveis no sistema Medicalsys (texto exato exibido no site).
# Ajuste conforme o texto exato apresentado na tela do seu ambiente.
STATUS_OPTIONS = [
    "AGUARDANDO ATENDIMENTO",
    "EM ATENDIMENTO",
    "ATENDIDO",
    "FINALIZADO",
    "CANCELADO",
    "FALTOU",
    "EM TRIAGEM",
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
