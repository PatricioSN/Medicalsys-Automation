"""Orquestração, prévia, confirmação, loop seguro de alteração e relatório final."""

import signal
import sys
from collections import Counter
from typing import Dict, List, Tuple
from playwright.sync_api import Page
from medicalsys_automation.config import DEV_PREFIX, MAX_CONSECUTIVE_FAILURES
from medicalsys_automation.pages import PatientItem, change_patient_status, read_all_patients


def check_dev_safety(patients: List[PatientItem]) -> bool:
    """Verifica se todos os pacientes atendem ao DEV_PREFIX configurado.

    Se DEV_PREFIX estiver ativo e qualquer paciente não iniciar com ele,
    a execução é abortada imediatamente antes de qualquer modificação.
    """
    if not DEV_PREFIX:
        return True

    prefix = DEV_PREFIX.strip().upper()
    non_matching = [p for p in patients if not p.name.strip().upper().startswith(prefix)]

    if non_matching:
        print("\n" + "=" * 78)
        print(" [ABORTADO] MODO DE DESENVOLVIMENTO ATIVO (DEV_PREFIX)")
        print("=" * 78)
        print(f"O sistema está configurado com DEV_PREFIX = '{DEV_PREFIX}'.")
        print(f"Foram identificados {len(non_matching)} paciente(s) na lista sem esse prefixo.")
        print("Para segurança absoluta dos dados reais, a operação foi cancelada.")
        print("Nenhuma alteração foi realizada e nenhum dado foi capturado.")
        print("\nPara utilizar em ambiente de produção com pacientes reais:")
        print("Altere em medicalsys_automation/config.py: DEV_PREFIX = None")
        print("=" * 78 + "\n")
        return False

    return True


def mark_duplicate_names(patients: List[PatientItem]) -> None:
    """Identifica pacientes com nomes repetidos quando não houver ID estável.

    Nomes repetidos sem ID estável são marcados preventivamente para revisão manual.
    """
    # Conta repetições de nomes normalizados
    counts = Counter(p.name.strip().upper() for p in patients)

    for p in patients:
        norm_name = p.name.strip().upper()
        if not p.stable_id and counts[norm_name] > 1:
            p.manual_review = True
            p.review_reason = "Nome duplicado na lista sem identificador estável único"


def show_preview_and_confirm(patients: List[PatientItem], target_status: str) -> bool:
    """Exibe prévia detalhada com contagens e solicita confirmação estrita ('sim')."""
    total = len(patients)
    status_counts = Counter(p.current_status for p in patients)

    print("\n" + "=" * 78)
    print("                              PRÉVIA DA OPERAÇÃO")
    print("=" * 78)
    print(f"Total de pacientes identificados na lista : {total}")
    print(f"Status de destino selecionado             : {target_status}")
    print("\nContagem por Status Atual:")
    for status, count in status_counts.items():
        print(f"  - {status}: {count} paciente(s)")

    already_target = status_counts.get(target_status, 0)
    print(f"\nPacientes que já estão no status de destino (serão ignorados): {already_target}")
    print(f"Pacientes candidatos a alteração                             : {total - already_target}")
    print("=" * 78)

    resposta = input("\nDigite 'sim' para confirmar e iniciar a alteração (qualquer outra resposta cancela): ")
    if resposta.strip().lower() != "sim":
        print("\n[CANCELADO] Operação cancelada pelo usuário. Nenhuma alteração foi efetuada.\n")
        return False

    return True


def print_final_report(
    total: int,
    target_status: str,
    altered: List[str],
    already_correct: List[str],
    failed: List[str],
    manual_review: List[Tuple[str, str]],
    interrupted: bool = False,
) -> None:
    """Exibe o relatório final ou parcial utilizando estritamente anon_ids (P01, P02...)."""
    header_title = "RELATÓRIO PARCIAL (INTERROMPIDO)" if interrupted else "RELATÓRIO FINAL DA OPERAÇÃO"

    print("\n" + "=" * 78)
    print(f"                        {header_title}")
    print("=" * 78)
    print(f"Status de Destino                : {target_status}")
    print(f"Total de registros processados   : {total}")
    print(f"Alterados com sucesso            : {len(altered)}")
    print(f"Já estavam corretos (ignorados)  : {len(already_correct)}")
    print(f"Falhas na alteração              : {len(failed)}")
    print(f"Revisar manualmente              : {len(manual_review)}")
    print("-" * 78)

    if altered:
        print(f"Identificadores Alterados        : {', '.join(altered)}")
    if already_correct:
        print(f"Identificadores Já Corretos      : {', '.join(already_correct)}")
    if failed:
        print(f"Identificadores com Falha        : {', '.join(failed)}")
    if manual_review:
        print("Identificadores para Revisão Manual:")
        for anon_id, reason in manual_review:
            print(f"  - [{anon_id}]: {reason}")

    print("=" * 78 + "\n")


def run_status_update(page: Page, target_status: str) -> None:
    """Loop principal de alteração de status com tratamento de interrupção e verificação."""
    print("\nLendo registros de pacientes na interface do Medicalsys...")
    try:
        patients = read_all_patients(page)
    except Exception as e:
        print(f"\n[ERRO] Falha ao ler registros da tabela: {e}")
        return

    if not patients:
        print("\nNenhum paciente foi encontrado na visualização atual da tabela.")
        return

    # Verificação de segurança de DEV_PREFIX
    if not check_dev_safety(patients):
        return

    # Marcação de duplicidades sem ID único
    mark_duplicate_names(patients)

    # Prévia e confirmação
    if not show_preview_and_confirm(patients, target_status):
        return

    # Controle de interrupção graciosa (Ctrl+C)
    stop_requested = False

    def handle_sigint(signum, frame):
        nonlocal stop_requested
        if not stop_requested:
            stop_requested = True
            print("\n\n[Ctrl+C detectado] Interrupção solicitada!")
            print("Aguardando a conclusão do salvamento do paciente em andamento antes de parar...\n")
        else:
            print("\n[Ctrl+C forçado] Encerrando imediatamente.")
            sys.exit(1)

    original_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, handle_sigint)

    altered: List[str] = []
    already_correct: List[str] = []
    failed: List[str] = []
    manual_review: List[Tuple[str, str]] = []

    consecutive_failures = 0
    total_processed = 0

    print("\nIniciando processamento seguro dos pacientes...\n")

    try:
        for p in patients:
            if stop_requested:
                print("[INFO] Parando o loop com segurança conforme solicitado via Ctrl+C.")
                break

            total_processed += 1

            # Caso o paciente tenha sido previamente marcado para revisão manual
            if p.manual_review:
                print(f"[{p.anon_id}] Marcado para REVISÃO MANUAL ({p.review_reason}). Pulando...")
                manual_review.append((p.anon_id, p.review_reason))
                continue

            # Se já estiver com o status desejado
            if p.current_status.strip().upper() == target_status.strip().upper():
                print(f"[{p.anon_id}] Status já é '{target_status}'. Pulando...")
                already_correct.append(p.anon_id)
                consecutive_failures = 0
                continue

            # Executa a alteração do status
            print(f"[{p.anon_id}] Alterando status de '{p.current_status}' para '{target_status}'...")
            success = False
            try:
                success = change_patient_status(page, p, target_status)
            except Exception as err:
                success = False

            if success:
                print(f"[{p.anon_id}] Sucesso: alterado e persistência confirmada.")
                altered.append(p.anon_id)
                consecutive_failures = 0
            else:
                print(f"[{p.anon_id}] AVISO: Não foi possível confirmar a alteração. Marcado para revisão manual.")
                manual_review.append((p.anon_id, "Falha ao alterar ou persistir status na interface"))
                failed.append(p.anon_id)
                consecutive_failures += 1

                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    print("\n" + "!" * 78)
                    print(f" [PARADA DE EMERGÊNCIA] {consecutive_failures} FALHAS CONSECUTIVAS DETECTADAS")
                    print(" A execução foi interrompida para evitar alterações indevidas.")
                    print("!" * 78 + "\n")
                    break

    finally:
        # Restaura o handler original de SIGINT
        signal.signal(signal.SIGINT, original_sigint)
        # Exibe o relatório com anon_ids
        print_final_report(
            total=total_processed,
            target_status=target_status,
            altered=altered,
            already_correct=already_correct,
            failed=failed,
            manual_review=manual_review,
            interrupted=stop_requested,
        )
