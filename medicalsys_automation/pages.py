"""Seletores e ações do sistema Medicalsys na interface web.

Centraliza todas as interações com o DOM utilizando get_by_role, get_by_label,
get_by_text e esperas explícitas do Playwright.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from playwright.sync_api import Locator, Page
from medicalsys_automation.config import DEFAULT_TIMEOUT_MS


@dataclass
class PatientItem:
    """Representação em memória de um paciente identificado na página."""
    anon_id: str                      # Ex: P01, P02 (usado exclusivamente em logs e relatórios)
    name: str                         # Usado para localização e checagem de DEV_PREFIX (nunca exibido em log)
    current_status: str               # Texto exato do status atual obtido na página
    stable_id: Optional[str] = None   # ID estável do registro (atributo HTML data-id, ID de banco, ou CPF)
    manual_review: bool = False       # Flag se precisa de revisão manual
    review_reason: str = ""           # Motivo de marcar para revisão manual


def get_table_locator(page: Page) -> Locator:
    """Retorna o locator da tabela principal de registros na página."""
    return page.get_by_role("table").first


def detect_columns_mapping(page: Page) -> Dict[str, int]:
    """Mapeia os nomes das colunas aos seus respectivos índices na tabela.

    Inspeciona o cabeçalho (thead th) para identificar colunas dinamicamente
    (Nome/Paciente, Status/Situação, CPF, Ações, etc.).
    """
    mapping: Dict[str, int] = {}
    table = get_table_locator(page)
    headers = table.locator("thead th")

    count = headers.count()
    for i in range(count):
        text = headers.nth(i).inner_text().strip().upper()
        if "PACIENTE" in text or "NOME" in text:
            mapping["name"] = i
        elif "STATUS" in text or "SITUA" in text:
            mapping["status"] = i
        elif "CPF" in text:
            mapping["cpf"] = i
        elif "AÇÕ" in text or "ACO" in text or "AÇÃO" in text:
            mapping["actions"] = i

    return mapping


def get_patient_rows(page: Page) -> Locator:
    """Retorna as linhas com dados de pacientes na tabela atual."""
    table = get_table_locator(page)
    # Seleciona linhas do tbody
    return table.locator("tbody tr")


def extract_patient_from_row(row: Locator, col_map: Dict[str, int], anon_id: str) -> Optional[PatientItem]:
    """Extrai os dados de um paciente a partir de uma linha da tabela."""
    cells = row.locator("td")
    total_cells = cells.count()
    if total_cells == 0:
        return None

    # Tenta identificar ID estável a partir de atributos HTML da tag <tr>
    stable_id = (
        row.get_attribute("data-id")
        or row.get_attribute("data-paciente-id")
        or row.get_attribute("data-ficha-id")
        or row.get_attribute("id")
    )

    # Identificação do Nome do Paciente
    name_idx = col_map.get("name", 0 if total_cells > 0 else 0)
    name = cells.nth(name_idx).inner_text().strip()
    if not name:
        return None

    # Se não houver data-id no tr, verifica se há coluna CPF como chave secundária
    if not stable_id and "cpf" in col_map and col_map["cpf"] < total_cells:
        cpf_text = cells.nth(col_map["cpf"]).inner_text().strip()
        if cpf_text:
            stable_id = f"CPF_{cpf_text}"

    # Identificação do Status atual
    current_status = "DESCONHECIDO"
    if "status" in col_map and col_map["status"] < total_cells:
        # Lê o TEXTO exato exibido na coluna de status, nunca apenas cor
        status_cell = cells.nth(col_map["status"])
        current_status = status_cell.inner_text().strip()

    return PatientItem(
        anon_id=anon_id,
        name=name,
        current_status=current_status,
        stable_id=stable_id,
    )


def read_current_page_patients(page: Page, start_index: int = 1) -> List[PatientItem]:
    """Lê todos os pacientes presentes na visualização atual da tabela."""
    get_table_locator(page).wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
    col_map = detect_columns_mapping(page)
    rows = get_patient_rows(page)
    row_count = rows.count()

    patients: List[PatientItem] = []
    current_idx = start_index

    for i in range(row_count):
        row = rows.nth(i)
        item = extract_patient_from_row(row, col_map, anon_id=f"P{current_idx:02d}")
        if item:
            patients.append(item)
            current_idx += 1

    return patients


def has_next_page(page: Page) -> Optional[Locator]:
    """Verifica se existe um botão de próxima página habilitado."""
    # O Medicalsys / DataTables comumente utiliza link ou botão "Próximo"
    next_btn = page.get_by_role("link", name="Próximo")
    if next_btn.count() == 0:
        next_btn = page.get_by_text("Próximo", exact=True)

    if next_btn.count() > 0 and next_btn.first.is_visible():
        btn = next_btn.first
        class_attr = (btn.get_attribute("class") or "").lower()
        aria_disabled = (btn.get_attribute("aria-disabled") or "").lower()
        parent_class = ""
        try:
            parent_class = (btn.locator("xpath=..").get_attribute("class") or "").lower()
        except Exception:
            pass

        if "disabled" in class_attr or aria_disabled == "true" or "disabled" in parent_class:
            return None
        return btn

    return None


def read_all_patients(page: Page) -> List[PatientItem]:
    """Lê todos os pacientes da lista, percorrendo todas as páginas de paginação."""
    all_patients: List[PatientItem] = []

    while True:
        current_batch = read_current_page_patients(page, start_index=len(all_patients) + 1)
        all_patients.extend(current_batch)

        next_btn = has_next_page(page)
        if not next_btn:
            break

        # Clica para ir para a próxima página com espera explícita
        next_btn.click()
        # Aguarda a atualização da tabela via espera explícita
        page.wait_for_load_state("domcontentloaded")
        page.locator("table tbody tr").first.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)

    return all_patients


def find_patient_row(page: Page, patient: PatientItem) -> Optional[Locator]:
    """Localiza a linha específica do paciente na tabela atual."""
    rows = get_patient_rows(page)
    count = rows.count()

    for i in range(count):
        row = rows.nth(i)
        # Se temos stable_id, confere por atributo HTML
        if patient.stable_id:
            attr_id = (
                row.get_attribute("data-id")
                or row.get_attribute("data-paciente-id")
                or row.get_attribute("data-ficha-id")
                or row.get_attribute("id")
            )
            if attr_id and attr_id == patient.stable_id:
                return row
            if patient.stable_id.startswith("CPF_"):
                cpf_raw = patient.stable_id.replace("CPF_", "")
                if cpf_raw in row.inner_text():
                    return row

        # Se busca pelo nome exato do paciente
        if patient.name in row.inner_text():
            return row

    return None


def open_patient_modal(page: Page, row: Locator) -> Locator:
    """Clica no botão/ícone de edição da linha e aguarda o modal abrir."""
    # Procura botões ou links de edição na coluna de ações
    edit_btn = row.locator("a[title*='Editar'], button[title*='Editar'], a[href*='edit'], .fa-edit, .fa-pencil, .fa-pen")
    if edit_btn.count() == 0:
        # Fallback para o primeiro botão ou link da coluna de ações
        cells = row.locator("td")
        last_cell = cells.last
        edit_btn = last_cell.locator("a, button").first

    edit_btn.first.click()

    # Aguarda o modal ficar visível de forma explícita
    modal = page.locator(".modal.show, .modal[style*='display: block'], [role='dialog']").first
    modal.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
    return modal


def change_status_in_modal(modal: Locator, target_status: str) -> None:
    """Altera o campo de status no modal para o valor selecionado."""
    # Tenta localizar o campo de status por label, name ou id
    status_select = modal.get_by_label("Status", exact=False)
    if status_select.count() == 0:
        status_select = modal.get_by_role("combobox", name="Status")
    if status_select.count() == 0:
        status_select = modal.locator("select[name*='status' i], select[id*='status' i]")

    if status_select.count() > 0 and status_select.first.is_visible():
        select_el = status_select.first
        try:
            # Seleciona pelo texto visível do status
            select_el.select_option(label=target_status, timeout=DEFAULT_TIMEOUT_MS)
            return
        except Exception:
            # Caso o valor no option seja correspondente
            select_el.select_option(value=target_status, timeout=DEFAULT_TIMEOUT_MS)
            return

    # Caso seja um dropdown customizado baseado em texto/divs/buttons
    dropdown_trigger = modal.get_by_text("Status", exact=False)
    dropdown_trigger.first.click()
    option_el = modal.get_by_text(target_status, exact=True)
    option_el.first.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
    option_el.first.click()


def save_modal(modal: Locator) -> None:
    """Clica no botão SALVAR e aguarda o fechamento do modal com espera explícita."""
    save_button = modal.get_by_role("button", name="SALVAR")
    if save_button.count() == 0:
        save_button = modal.get_by_text("SALVAR", exact=True)

    save_button.first.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
    save_button.first.click()

    # Aguarda o modal sumir completamente
    modal.wait_for(state="hidden", timeout=DEFAULT_TIMEOUT_MS)


def refresh_table(page: Page) -> None:
    """Aciona a atualização da tabela se o botão ATUALIZAR estiver disponível."""
    refresh_btn = page.get_by_role("button", name="ATUALIZAR")
    if refresh_btn.count() > 0 and refresh_btn.first.is_visible():
        refresh_btn.first.click()
        page.wait_for_load_state("domcontentloaded")
        page.locator("table tbody tr").first.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)


def check_status_persisted(page: Page, patient: PatientItem, target_status: str) -> bool:
    """Confere na interface se o novo status foi persistido com sucesso."""
    refresh_table(page)
    row = find_patient_row(page, patient)
    if not row:
        return False

    col_map = detect_columns_mapping(page)
    cells = row.locator("td")

    if "status" in col_map and col_map["status"] < cells.count():
        actual_text = cells.nth(col_map["status"]).inner_text().strip()
        return actual_text.upper() == target_status.upper()

    # Se não houver coluna status direta, busca o texto de destino na linha
    return target_status.upper() in row.inner_text().upper()


def change_patient_status(page: Page, patient: PatientItem, target_status: str) -> bool:
    """Executa a alteração completa de status de um paciente e verifica persistência.

    Returns:
        bool: True se o status foi alterado e verificado; False caso contrário.
    """
    row = find_patient_row(page, patient)
    if not row:
        return False

    try:
        modal = open_patient_modal(page, row)
        change_status_in_modal(modal, target_status)
        save_modal(modal)
        return check_status_persisted(page, patient, target_status)
    except Exception:
        return False
