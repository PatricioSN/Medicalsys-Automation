"""Ponto de entrada e orquestração da automação do Medicalsys."""

import sys
from playwright.sync_api import sync_playwright
from medicalsys_automation.browser import connect_browser
from medicalsys_automation.config import STATUS_OPTIONS
from medicalsys_automation.runner import run_status_update


def display_status_menu() -> str:
    """Exibe o menu numerado com os status configurados e retorna a opção escolhida."""
    print("\n" + "=" * 50)
    print("      ESCOLHA O STATUS DE DESTINO DESEJADO")
    print("=" * 50)
    for idx, status in enumerate(STATUS_OPTIONS, start=1):
        print(f"  [{idx}] {status}")
    print("  [0] Sair")
    print("=" * 50)

    while True:
        choice = input(f"\nDigite o número da opção desejada (1 a {len(STATUS_OPTIONS)}): ").strip()
        if choice == "0":
            print("\nExecução encerrada.")
            sys.exit(0)

        if choice.isdigit():
            num = int(choice)
            if 1 <= num <= len(STATUS_OPTIONS):
                selected = STATUS_OPTIONS[num - 1]
                print(f"\nStatus selecionado: '{selected}'")
                return selected

        print(f"Opção inválida! Digite um número de 1 a {len(STATUS_OPTIONS)} ou 0 para sair.")


def main() -> None:
    """Função principal que coordena conexão, seleção de status e execução."""
    print("\n" + "#" * 60)
    print("        AUTOMAÇÃO DE STATUS - SISTEMA MEDICALSYS")
    print("#" * 60)

    with sync_playwright() as playwright:
        print("\nConectando ao navegador via CDP (porta 9222)...")
        browser, page = connect_browser(playwright)

        if not browser or not page:
            # browser.py já exibiu as orientações detalhadas de inicialização
            return

        print("Conectado com sucesso à aba do Medicalsys!")

        # Menu de seleção de status
        target_status = display_status_menu()

        # Inicia a prévia, confirmação e execução da automação
        run_status_update(page, target_status)


if __name__ == "__main__":
    main()
