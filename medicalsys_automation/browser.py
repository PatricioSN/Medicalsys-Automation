"""Gerenciamento de conexão com o navegador via CDP (Chrome DevTools Protocol)."""

import os
from typing import Optional, Tuple
from playwright.sync_api import Browser, Page, Playwright
from medicalsys_automation.config import CDP_URL, URL_SUBSTRING


def print_cdp_instructions() -> None:
    """Exibe instruções amigáveis no terminal sobre como iniciar o navegador com CDP."""
    home_dir = os.path.expanduser("~")
    suggested_profile_dir = os.path.join(home_dir, "medicalsys_debug_profile")

    print("\n" + "=" * 78)
    print(" [AVISO] NÃO FOI POSSÍVEL CONECTAR AO NAVEGADOR NA PORTA 9222")
    print("=" * 78)
    print("O navegador precisa ser iniciado com depuração remota e um perfil separado.")
    print("Navegadores baseados em Chromium não permitem depuração no perfil padrão em uso.\n")
    print("Como iniciar (feche as janelas normais do navegador ou execute em um novo terminal):")
    print("\n* Opção 1: Google Chrome")
    print(f'  chrome.exe --remote-debugging-port=9222 --user-data-dir="{suggested_profile_dir}"')
    print("\n* Opção 2: Brave Browser")
    print(f'  & "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe" --remote-debugging-port=9222 --user-data-dir="{suggested_profile_dir}"')
    print("\n* Opção 3: Microsoft Edge")
    print(f'  & "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe" --remote-debugging-port=9222 --user-data-dir="{suggested_profile_dir}"')
    print("\nDepois que a janela abrir:")
    print("1. Acesse o Medicalsys e faça o seu login manualmente.")
    print("2. Abra a página onde os pacientes estão listados.")
    print("3. Execute este script novamente: python main.py")
    print("=" * 78 + "\n")


def connect_browser(playwright: Playwright) -> Tuple[Optional[Browser], Optional[Page]]:
    """Conecta ao navegador aberto via CDP e localiza a aba do Medicalsys.

    Returns:
        Tuple[Optional[Browser], Optional[Page]]: Instâncias de Browser e Page,
        ou (None, None) se não conseguir conectar ou encontrar a aba.
    """
    try:
        browser = playwright.chromium.connect_over_cdp(CDP_URL)
    except Exception:
        print_cdp_instructions()
        return None, None

    # Procura a aba do Medicalsys em todos os contextos abertos
    matched_page: Optional[Page] = None
    all_pages = []

    for context in browser.contexts:
        for page in context.pages:
            all_pages.append(page)
            # Verifica se o trecho configurado da URL está presente
            if URL_SUBSTRING.lower() in page.url.lower():
                matched_page = page
                break
        if matched_page:
            break

    if not matched_page:
        print("\n" + "=" * 78)
        print(" [AVISO] NAVEGADOR CONECTADO, MAS ABA DO MEDICALSYS NÃO FOI LOCALIZADA")
        print("=" * 78)
        print(f"Não encontramos nenhuma aba aberta cuja URL contenha: '{URL_SUBSTRING}'")
        print(f"Total de abas abertas detectadas: {len(all_pages)}")
        print("\nAbra ou navegue até a tela do Medicalsys no navegador aberto e tente novamente.")
        print("=" * 78 + "\n")
        return browser, None

    try:
        matched_page.bring_to_front()
    except Exception:
        pass

    return browser, matched_page
