"""Seletores e ações do sistema Medicalsys na interface web.

Centraliza todas as interações com o DOM utilizando get_by_role, get_by_label,
get_by_text e seletores semânticos com esperas explícitas do Playwright.
Suporta tanto a visualização em Agenda/Calendário (FullCalendar) quanto em Tabela.
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
    stable_id: Optional[str] = None   # ID estável do registro (ID do agendamento ou paciente)
    manual_review: bool = False       # Flag se precisa de revisão manual
    review_reason: str = ""           # Motivo de marcar para revisão manual


def is_calendar_view(page: Page) -> bool:
    """Verifica se a página aberta é a visualização da Agenda / Calendário."""
    return page.locator("#calendar").count() > 0


# ==============================================================================
# FLUXO 1: AGENDA / CALENDÁRIO (FULLCALENDAR DO MEDICALSYS)
# ==============================================================================

def read_calendar_patients(page: Page) -> List[PatientItem]:
    """Extrai todos os pacientes e status presentes na Agenda do Medicalsys."""
    page.locator("#calendar").wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)

    # Inspeciona os eventos carregados no FullCalendar
    events_data = page.evaluate("""() => {
        if (!window.jQuery || !$('#calendar').fullCalendar) return [];
        const events = $('#calendar').fullCalendar('clientEvents');
        return events.map(e => ({
            id: String(e.id || e._id || ''),
            paciente: String(e.paciente || (e.title || '').split('\\n')[0] || '').trim(),
            situacao: String(e.situacao || 'Desconhecido').trim()
        }));
    }""")

    patients: List[PatientItem] = []
    for idx, ev in enumerate(events_data, start=1):
        if not ev["paciente"]:
            continue
        patients.append(PatientItem(
            anon_id=f"P{idx:02d}",
            name=ev["paciente"],
            current_status=ev["situacao"],
            stable_id=ev["id"] or None,
        ))

    return patients


def change_calendar_patient_status(page: Page, patient: PatientItem, target_status: str) -> bool:
    """Altera o status de um agendamento na tela de Agenda/Calendário com espera de rede."""
    # Garante que popovers anteriores estejam fechados
    page.evaluate("() => { if (window.closePopover) window.closePopover(); if (window.fecharPopovers) window.fecharPopovers(); }")

    # 1. Localiza o card do evento no calendário
    event_loc = page.locator(".fc-event").filter(has_text=patient.name)
    if event_loc.count() == 0 and patient.stable_id:
        event_loc = page.locator(f".fc-event:has-text('{patient.name[:15]}')")

    if event_loc.count() == 0:
        return False

    # Rola até o card se necessário e clica para abrir o popover
    target_event = event_loc.first
    target_event.scroll_into_view_if_needed()
    target_event.click()

    # 2. Aguarda o popover abrir
    popover = page.locator(".popover.in, .popover").first
    try:
        popover.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
    except Exception:
        return False

    # 3. Localiza o componente de seleção de status no popover
    select2_container = popover.locator(".select2-container")
    native_select = popover.locator("select#opcoesAgendamento, select#status-agendamento")

    if select2_container.count() > 0 and select2_container.first.is_visible():
        # Clica no container do Select2 para abrir a lista suspensa
        select2_container.first.click()

        # Aguarda as opções do Select2 ficarem visíveis
        results_option = page.locator(".select2-results__option")
        try:
            results_option.first.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
        except Exception:
            page.evaluate("() => { if (window.closePopover) window.closePopover(); if (window.fecharPopovers) window.fecharPopovers(); }")
            return False

        # Localiza a opção pelo texto exato
        target_option = results_option.filter(has_text=target_status).first
        if target_option.count() == 0:
            # Opção não permitida para o estado atual deste agendamento
            page.evaluate("() => { if (window.closePopover) window.closePopover(); if (window.fecharPopovers) window.fecharPopovers(); }")
            return False

        # Clica na opção aguardando a resposta da requisição AJAX de alteração
        try:
            with page.expect_response(lambda r: "alterar_situacao" in r.url or "agenda" in r.url, timeout=DEFAULT_TIMEOUT_MS):
                target_option.click()
        except Exception:
            # Fallback se a requisição não casar a URL exata
            pass

    elif native_select.count() > 0:
        try:
            with page.expect_response(lambda r: "alterar_situacao" in r.url or "agenda" in r.url, timeout=DEFAULT_TIMEOUT_MS):
                native_select.first.select_option(label=target_status, timeout=DEFAULT_TIMEOUT_MS)
        except Exception:
            return False
    else:
        # Popover sem campo de status disponível (ex: consulta bloqueada/finalizada)
        page.evaluate("() => { if (window.closePopover) window.closePopover(); if (window.fecharPopovers) window.fecharPopovers(); }")
        return False

    # 4. Aguarda a confirmação de persistência no FullCalendar
    persisted = False
    try:
        page.wait_for_function(
            """({ id, targetStatus }) => {
                if (!window.jQuery || !$('#calendar').fullCalendar) return false;
                const events = $('#calendar').fullCalendar('clientEvents');
                const ev = events.find(e => String(e.id) === String(id) || String(e._id) === String(id));
                return ev && ev.situacao && ev.situacao.trim().toLowerCase() === targetStatus.trim().toLowerCase();
            }""",
            arg={"id": patient.stable_id, "targetStatus": target_status},
            timeout=DEFAULT_TIMEOUT_MS
        )
        persisted = True
    except Exception:
        # Confere fallback no estado do evento
        current_status = page.evaluate("""(id) => {
            if (!window.jQuery || !$('#calendar').fullCalendar) return null;
            const ev = $('#calendar').fullCalendar('clientEvents').find(e => String(e.id) === String(id));
            return ev ? ev.situacao : null;
        }""", patient.stable_id)
        if current_status and current_status.strip().lower() == target_status.strip().lower():
            persisted = True

    # 5. Fecha qualquer popover remanescente
    page.evaluate("() => { if (window.closePopover) window.closePopover(); if (window.fecharPopovers) window.fecharPopovers(); }")

    return persisted


# ==============================================================================
# FLUXO 2: TABELAS COM PAGINAÇÃO (SALA DE ESPERA / PACIENTES)
# ==============================================================================

def get_table_locator(page: Page) -> Locator:
    """Retorna o locator da tabela principal de registros na página."""
    return page.get_by_role("table").first


def detect_columns_mapping(page: Page) -> Dict[str, int]:
    """Mapeia os nomes das colunas aos seus respectivos índices na tabela."""
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


def read_table_patients(page: Page) -> List[PatientItem]:
    """Lê pacientes de páginas de tabela do Medicalsys com paginação."""
    all_patients: List[PatientItem] = []
    col_map = detect_columns_mapping(page)

    while True:
        rows = page.locator("table tbody tr")
        row_count = rows.count()

        for i in range(row_count):
            row = rows.nth(i)
            cells = row.locator("td")
            if cells.count() == 0:
                continue

            name_idx = col_map.get("name", 0)
            name = cells.nth(name_idx).inner_text().strip()
            if not name:
                continue

            status_text = "Desconhecido"
            if "status" in col_map and col_map["status"] < cells.count():
                status_text = cells.nth(col_map["status"]).inner_text().strip()

            stable_id = row.get_attribute("data-id") or row.get_attribute("id")
            if not stable_id and "cpf" in col_map and col_map["cpf"] < cells.count():
                cpf_val = cells.nth(col_map["cpf"]).inner_text().strip()
                if cpf_val:
                    stable_id = f"CPF_{cpf_val}"

            all_patients.append(PatientItem(
                anon_id=f"P{len(all_patients) + 1:02d}",
                name=name,
                current_status=status_text,
                stable_id=stable_id
            ))

        # Paginação
        next_btn = page.get_by_role("link", name="Próximo")
        if next_btn.count() == 0:
            next_btn = page.get_by_text("Próximo", exact=True)

        if next_btn.count() > 0 and next_btn.first.is_visible():
            btn = next_btn.first
            classes = (btn.get_attribute("class") or "").lower()
            if "disabled" in classes:
                break
            btn.click()
            page.wait_for_load_state("domcontentloaded")
            page.locator("table tbody tr").first.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
        else:
            break

    return all_patients


# ==============================================================================
# FUNÇÕES PRINCIPAIS DE ENTRADA (CHAMADAS PELO RUNNER)
# ==============================================================================

def read_all_patients(page: Page) -> List[PatientItem]:
    """Ponto de entrada unificado para leitura de todos os pacientes da tela aberta."""
    if is_calendar_view(page):
        return read_calendar_patients(page)
    else:
        return read_table_patients(page)


def change_patient_status(page: Page, patient: PatientItem, target_status: str) -> bool:
    """Ponto de entrada unificado para alteração do status de um paciente."""
    if is_calendar_view(page):
        return change_calendar_patient_status(page, patient, target_status)
    else:
        row = page.locator("table tbody tr").filter(has_text=patient.name).first
        if row.count() == 0:
            return False
        edit_btn = row.locator("a[title*='Editar'], button[title*='Editar'], .fa-pencil, .fa-edit").first
        edit_btn.click()
        modal = page.locator(".modal.show, .modal.in, [role='dialog']").first
        modal.wait_for(state="visible", timeout=DEFAULT_TIMEOUT_MS)
        modal.get_by_label("Status", exact=False).select_option(label=target_status)
        modal.get_by_role("button", name="SALVAR").click()
        modal.wait_for(state="hidden", timeout=DEFAULT_TIMEOUT_MS)
        return True
