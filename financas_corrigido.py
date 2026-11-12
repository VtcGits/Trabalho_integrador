#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Controle Financeiro Pessoal
--------------------------------------
Funcionalidades:
  1. Receitas
  2. Despesas
  3. Contas (com saldo individual)
  4. Categorias
  5. Saldo mensal
  6. Relatórios de receitas e despesas

Requisitos: Python 3.8+ (usa apenas a biblioteca padrão).
Execução:   python financas.py

Os valores são guardados em centavos (inteiros) para evitar erros de
arredondamento.
"""

import os
import re
import sqlite3
import sys
from datetime import date, datetime
import math

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "financas.db")
RECEITA, DESPESA = "receita", "despesa"
TIPOS_CONTA = ["Carteira", "Conta corrente", "Poupança", "Investimento", "Outro"]
CATEGORIAS_PADRAO = {
    RECEITA: ["Salário", "Freelance", "Investimentos", "Outras receitas"],
    DESPESA: ["Alimentação", "Moradia", "Transporte", "Saúde", "Educação",
              "Lazer", "Contas e serviços", "Outras despesas"],
}
def _suporta(simbolo):
    """True se o terminal atual consegue exibir o símbolo."""
    try:
        simbolo.encode(sys.stdout.encoding or "ascii")
        return True
    except (UnicodeEncodeError, LookupError):
        return False


OK_S = "\u2714" if _suporta("\u2714") else "[OK]"
AVISO_S = "\u26a0" if _suporta("\u26a0") else "(!)"
BLOCO_S = "\u2588" if _suporta("\u2588") else "#"

MESES = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
         "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


# ----------------------------------------------------------------------
# Banco de dados
# ----------------------------------------------------------------------
def conectar():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def iniciar_banco():
    with conectar() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS contas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                tipo TEXT NOT NULL,
                saldo_inicial INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS categorias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                tipo TEXT NOT NULL CHECK (tipo IN ('receita','despesa')),
                UNIQUE (nome, tipo)
            );
            CREATE TABLE IF NOT EXISTS lancamentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL CHECK (tipo IN ('receita','despesa')),
                conta_id INTEGER NOT NULL,
                categoria_id INTEGER NOT NULL,
                descricao TEXT NOT NULL,
                valor INTEGER NOT NULL CHECK (valor > 0),
                data TEXT NOT NULL,
                FOREIGN KEY (conta_id) REFERENCES contas(id),
                FOREIGN KEY (categoria_id) REFERENCES categorias(id)
            );
            """
        )
        if con.execute("SELECT COUNT(*) FROM categorias").fetchone()[0] == 0:
            for tipo, nomes in CATEGORIAS_PADRAO.items():
                con.executemany(
                    "INSERT INTO categorias (nome, tipo) VALUES (?,?)",
                    [(n, tipo) for n in nomes])
        if con.execute("SELECT COUNT(*) FROM contas").fetchone()[0] == 0:
            con.execute("INSERT INTO contas (nome, tipo, saldo_inicial) "
                        "VALUES ('Carteira','Carteira',0)")


# ----------------------------------------------------------------------
# Utilitários
# ----------------------------------------------------------------------
def brl(centavos):
    sinal = "-" if centavos < 0 else ""
    reais = abs(centavos) / 100
    texto = f"{reais:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{sinal}R$ {texto}"


def titulo(texto):
    print("\n" + "=" * 62)
    print(texto.center(62))
    print("=" * 62)


def pausar():
    input("\nPressione ENTER para continuar...")


def confirmar(msg):
    return input(f"{msg} (s/n): ").strip().lower() == "s"


def ler_texto(msg):
    while True:
        valor = input(f"{msg}: ").strip()
        if valor:
            return valor
        print("  ! Campo obrigatório.")


def ler_valor(msg, permitir_zero=False):
    """Lê um valor em reais e devolve em centavos.

    Aceita 1234,56 | 1.234,56 | 1234.56 | 1.500 (= mil e quinhentos).
    """
    while True:
        bruto = input(f"{msg}: ").strip().replace("R$", "").replace(" ", "")
        if "," in bruto:
            bruto = bruto.replace(".", "").replace(",", ".")
        elif re.fullmatch(r"\d{1,3}(\.\d{3})+", bruto):
            bruto = bruto.replace(".", "")  # ponto como separador de milhar
        try:
            numero = float(bruto)
            if not math.isfinite(numero):
                raise ValueError
            valor = round(numero * 100)
            if valor < 0 or (valor == 0 and not permitir_zero):
                raise ValueError
            return valor
        except (ValueError, OverflowError):
            print("  ! Informe um valor numérico válido"
                  + ("." if permitir_zero else " e maior que zero."))


def ler_data(msg="Data (dd/mm/aaaa, ENTER = hoje)"):
    while True:
        bruto = input(f"{msg}: ").strip()
        if not bruto:
            return date.today().isoformat()
        try:
            return datetime.strptime(bruto, "%d/%m/%Y").date().isoformat()
        except ValueError:
            print("  ! Data inválida. Use o formato dd/mm/aaaa.")


def ler_mes():
    """Devolve (ano, mes). ENTER = mês atual."""
    hoje = date.today()
    while True:
        bruto = input("Mês (mm/aaaa, ENTER = mês atual): ").strip()
        if not bruto:
            return hoje.year, hoje.month
        try:
            d = datetime.strptime(bruto, "%m/%Y")
            return d.year, d.month
        except ValueError:
            print("  ! Mês inválido. Use o formato mm/aaaa.")


def ler_ano():
    while True:
        bruto = input(f"Ano (aaaa, ENTER = {date.today().year}): ").strip()
        if not bruto:
            return date.today().year
        if bruto.isdigit() and 1900 <= int(bruto) <= 2100:
            return int(bruto)
        print("  ! Ano inválido.")


def prefixo(ano, mes):
    return f"{ano:04d}-{mes:02d}"


def fmt_data(iso):
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")


def escolher_item(linhas, rotulo, msg):
    """Mostra uma lista numerada pelo id e devolve a linha escolhida."""
    if not linhas:
        print("  ! Nada cadastrado ainda.")
        return None
    ids = {l["id"]: l for l in linhas}
    for l in linhas:
        print(f"  [{l['id']}] {rotulo(l)}")
    while True:
        bruto = input(f"{msg} (0 para cancelar): ").strip()
        if bruto == "0":
            return None
        if bruto.isdigit() and int(bruto) in ids:
            return ids[int(bruto)]
        print("  ! Opção inválida.")


def saldo_conta(con, conta_id):
    r = con.execute(
        "SELECT c.saldo_inicial + COALESCE(SUM(CASE l.tipo WHEN 'receita' "
        "THEN l.valor ELSE -l.valor END), 0) "
        "FROM contas c LEFT JOIN lancamentos l ON l.conta_id = c.id "
        "WHERE c.id = ?", (conta_id,)).fetchone()
    return r[0]


# ----------------------------------------------------------------------
# Contas
# ----------------------------------------------------------------------
def cadastrar_conta():
    titulo("NOVA CONTA")
    nome = ler_texto("Nome da conta (ex.: Nubank, Itaú, Carteira)")
    print("Tipo da conta:")
    for i, t in enumerate(TIPOS_CONTA, 1):
        print(f"  {i}) {t}")
    while True:
        op = input("Tipo: ").strip()
        if op.isdigit() and 1 <= int(op) <= len(TIPOS_CONTA):
            tipo = TIPOS_CONTA[int(op) - 1]
            break
        print("  ! Opção inválida.")
    saldo = ler_valor("Saldo inicial (R$)", permitir_zero=True)
    try:
        with conectar() as con:
            con.execute("INSERT INTO contas (nome, tipo, saldo_inicial) "
                        "VALUES (?,?,?)", (nome, tipo, saldo))
        print(f"\n{OK_S} Conta cadastrada.")
    except sqlite3.IntegrityError:
        print("\n  ! Já existe uma conta com esse nome.")


def listar_contas():
    with conectar() as con:
        contas = con.execute("SELECT * FROM contas ORDER BY nome").fetchall()
        if not contas:
            print("\nNenhuma conta cadastrada.")
            return
        print(f"\n{'ID':<5}{'Conta':<24}{'Tipo':<18}{'Saldo atual':>14}")
        print("-" * 61)
        total = 0
        for c in contas:
            s = saldo_conta(con, c["id"])
            total += s
            print(f"{c['id']:<5}{c['nome'][:23]:<24}{c['tipo']:<18}{brl(s):>14}")
        print("-" * 61)
        print(f"{'Patrimônio total':<47}{brl(total):>14}")


def excluir_conta():
    titulo("EXCLUIR CONTA")
    with conectar() as con:
        contas = con.execute("SELECT * FROM contas ORDER BY nome").fetchall()
        conta = escolher_item(contas, lambda c: c["nome"], "ID da conta")
        if not conta:
            return
        usos = con.execute("SELECT COUNT(*) FROM lancamentos WHERE conta_id=?",
                           (conta["id"],)).fetchone()[0]
        if usos:
            print(f"  ! Não é possível excluir: há {usos} lançamento(s) nesta conta.")
            return
        if confirmar(f"Excluir a conta '{conta['nome']}'?"):
            con.execute("DELETE FROM contas WHERE id=?", (conta["id"],))
            print(f"\n{OK_S} Conta excluída.")


def menu_contas():
    while True:
        titulo("CONTAS")
        print("1) Cadastrar conta\n2) Listar contas e saldos\n3) Excluir conta\n0) Voltar")
        op = input("Opção: ").strip()
        if op == "1":
            cadastrar_conta()
        elif op == "2":
            listar_contas()
        elif op == "3":
            excluir_conta()
        elif op == "0":
            return
        else:
            print("Opção inválida.")
        pausar()


# ----------------------------------------------------------------------
# Categorias
# ----------------------------------------------------------------------
def cadastrar_categoria():
    titulo("NOVA CATEGORIA")
    print("1) Receita\n2) Despesa")
    op = input("Tipo: ").strip()
    if op not in ("1", "2"):
        print("Opção inválida.")
        return
    tipo = RECEITA if op == "1" else DESPESA
    nome = ler_texto("Nome da categoria")
    try:
        with conectar() as con:
            con.execute("INSERT INTO categorias (nome, tipo) VALUES (?,?)",
                        (nome, tipo))
        print(f"\n{OK_S} Categoria cadastrada.")
    except sqlite3.IntegrityError:
        print("\n  ! Essa categoria já existe.")


def listar_categorias():
    with conectar() as con:
        for tipo, rotulo in ((RECEITA, "RECEITAS"), (DESPESA, "DESPESAS")):
            linhas = con.execute("SELECT * FROM categorias WHERE tipo=? "
                                 "ORDER BY nome", (tipo,)).fetchall()
            print(f"\n{rotulo}")
            for c in linhas:
                print(f"  [{c['id']}] {c['nome']}")


def excluir_categoria():
    titulo("EXCLUIR CATEGORIA")
    with conectar() as con:
        cats = con.execute("SELECT * FROM categorias ORDER BY tipo, nome").fetchall()
        cat = escolher_item(cats, lambda c: f"{c['nome']} ({c['tipo']})",
                            "ID da categoria")
        if not cat:
            return
        usos = con.execute("SELECT COUNT(*) FROM lancamentos WHERE categoria_id=?",
                           (cat["id"],)).fetchone()[0]
        if usos:
            print(f"  ! Não é possível excluir: há {usos} lançamento(s) nela.")
            return
        if confirmar(f"Excluir a categoria '{cat['nome']}'?"):
            con.execute("DELETE FROM categorias WHERE id=?", (cat["id"],))
            print(f"\n{OK_S} Categoria excluída.")


def menu_categorias():
    while True:
        titulo("CATEGORIAS")
        print("1) Cadastrar categoria\n2) Listar categorias\n3) Excluir categoria\n0) Voltar")
        op = input("Opção: ").strip()
        if op == "1":
            cadastrar_categoria()
        elif op == "2":
            listar_categorias()
        elif op == "3":
            excluir_categoria()
        elif op == "0":
            return
        else:
            print("Opção inválida.")
        pausar()


# ----------------------------------------------------------------------
# Lançamentos (receitas e despesas)
# ----------------------------------------------------------------------
def registrar(tipo):
    nome = "RECEITA" if tipo == RECEITA else "DESPESA"
    titulo(f"NOVA {nome}")
    with conectar() as con:
        print("Conta:")
        contas = con.execute("SELECT * FROM contas ORDER BY nome").fetchall()
        conta = escolher_item(contas, lambda c: c["nome"], "ID da conta")
        if not conta:
            return
        print(f"\nCategoria de {tipo}:")
        cats = con.execute("SELECT * FROM categorias WHERE tipo=? ORDER BY nome",
                           (tipo,)).fetchall()
        cat = escolher_item(cats, lambda c: c["nome"], "ID da categoria")
        if not cat:
            return
        desc = ler_texto("Descrição")
        valor = ler_valor("Valor (R$)")
        data = ler_data()
        con.execute(
            "INSERT INTO lancamentos (tipo, conta_id, categoria_id, descricao, "
            "valor, data) VALUES (?,?,?,?,?,?)",
            (tipo, conta["id"], cat["id"], desc, valor, data))
        print(f"\n{OK_S} {tipo.capitalize()} de {brl(valor)} registrada em "
              f"'{conta['nome']}'.")
        if tipo == DESPESA and saldo_conta(con, conta["id"]) < 0:
            print(f"  {AVISO_S} Atenção: a conta '{conta['nome']}' ficou com saldo "
                  f"negativo ({brl(saldo_conta(con, conta['id']))}).")


def listar_lancamentos(tipo):
    ano, mes = ler_mes()
    with conectar() as con:
        linhas = con.execute(
            "SELECT l.*, c.nome conta, g.nome categoria FROM lancamentos l "
            "JOIN contas c ON c.id = l.conta_id "
            "JOIN categorias g ON g.id = l.categoria_id "
            "WHERE l.tipo=? AND substr(l.data,1,7)=? ORDER BY l.data, l.id",
            (tipo, prefixo(ano, mes))).fetchall()
    print(f"\n{tipo.upper()}S de {MESES[mes]}/{ano}")
    if not linhas:
        print("Nenhum lançamento no período.")
        return
    print(f"\n{'ID':<5}{'Data':<12}{'Descrição':<20}{'Categoria':<16}"
          f"{'Conta':<12}{'Valor':>13}")
    print("-" * 78)
    for l in linhas:
        print(f"{l['id']:<5}{fmt_data(l['data']):<12}{l['descricao'][:19]:<20}"
              f"{l['categoria'][:15]:<16}{l['conta'][:11]:<12}{brl(l['valor']):>13}")
    print("-" * 78)
    print(f"{'Total':<65}{brl(sum(l['valor'] for l in linhas)):>13}")


def excluir_lancamento(tipo):
    titulo(f"EXCLUIR {tipo.upper()}")
    listar_lancamentos(tipo)
    bruto = input("\nID do lançamento a excluir (ENTER para cancelar): ").strip()
    if not bruto.isdigit():
        return
    with conectar() as con:
        l = con.execute("SELECT * FROM lancamentos WHERE id=? AND tipo=?",
                        (int(bruto), tipo)).fetchone()
        if not l:
            print("  ! Lançamento não encontrado.")
            return
        if confirmar(f"Excluir '{l['descricao']}' ({brl(l['valor'])})?"):
            con.execute("DELETE FROM lancamentos WHERE id=?", (l["id"],))
            print(f"\n{OK_S} Lançamento excluído.")


def menu_lancamentos(tipo):
    nome = "RECEITAS" if tipo == RECEITA else "DESPESAS"
    while True:
        titulo(nome)
        print(f"1) Registrar\n2) Listar por mês\n3) Excluir\n0) Voltar")
        op = input("Opção: ").strip()
        if op == "1":
            registrar(tipo)
        elif op == "2":
            listar_lancamentos(tipo)
        elif op == "3":
            excluir_lancamento(tipo)
        elif op == "0":
            return
        else:
            print("Opção inválida.")
        pausar()


# ----------------------------------------------------------------------
# Saldo mensal e relatórios
# ----------------------------------------------------------------------
def totais_mes(con, ano, mes):
    r = con.execute(
        "SELECT COALESCE(SUM(CASE WHEN tipo='receita' THEN valor END),0) rec, "
        "COALESCE(SUM(CASE WHEN tipo='despesa' THEN valor END),0) des "
        "FROM lancamentos WHERE substr(data,1,7)=?",
        (prefixo(ano, mes),)).fetchone()
    return r["rec"], r["des"]


def saldo_mensal():
    titulo("SALDO MENSAL")
    ano, mes = ler_mes()
    with conectar() as con:
        rec, des = totais_mes(con, ano, mes)
    saldo = rec - des
    print(f"\n{MESES[mes]}/{ano}")
    print(f"  Receitas .... {brl(rec):>16}")
    print(f"  Despesas .... {brl(des):>16}")
    print(f"  Saldo ....... {brl(saldo):>16}")
    if rec == 0 and des == 0:
        print("\nSem movimentação neste mês.")
    elif saldo > 0:
        print(f"\nSituação: positiva. Sobrou {saldo / rec * 100:.1f}% da receita." if rec
              else "\nSituação: positiva.")
    elif saldo < 0:
        print("\nSituação: negativa. As despesas superaram as receitas.")
    else:
        print("\nSituação: equilibrada.")


def relatorio_categorias(tipo):
    ano, mes = ler_mes()
    with conectar() as con:
        linhas = con.execute(
            "SELECT g.nome, SUM(l.valor) total, COUNT(*) qtd FROM lancamentos l "
            "JOIN categorias g ON g.id = l.categoria_id "
            "WHERE l.tipo=? AND substr(l.data,1,7)=? GROUP BY g.id "
            "ORDER BY total DESC", (tipo, prefixo(ano, mes))).fetchall()
    total = sum(l["total"] for l in linhas)
    print(f"\n{tipo.upper()}S POR CATEGORIA - {MESES[mes]}/{ano}")
    if not linhas:
        print("Nenhum lançamento no período.")
        return
    print(f"\n{'Categoria':<22}{'Qtd':>4}{'Total':>16}{'%':>8}  Gráfico")
    print("-" * 62)
    for l in linhas:
        pct = l["total"] / total * 100
        print(f"{l['nome'][:21]:<22}{l['qtd']:>4}{brl(l['total']):>16}"
              f"{pct:>7.1f}%  {BLOCO_S * max(1, round(pct / 5))}")
    print("-" * 62)
    print(f"{'Total':<26}{brl(total):>16}")


def extrato_conta():
    titulo("EXTRATO DA CONTA")
    with conectar() as con:
        contas = con.execute("SELECT * FROM contas ORDER BY nome").fetchall()
        conta = escolher_item(contas, lambda c: c["nome"], "ID da conta")
        if not conta:
            return
        linhas = con.execute(
            "SELECT l.*, g.nome categoria FROM lancamentos l "
            "JOIN categorias g ON g.id = l.categoria_id "
            "WHERE l.conta_id=? ORDER BY l.data, l.id", (conta["id"],)).fetchall()
        print(f"\nConta: {conta['nome']}  |  Saldo inicial: "
              f"{brl(conta['saldo_inicial'])}")
        saldo = conta["saldo_inicial"]
        if not linhas:
            print("Sem movimentação.")
        else:
            print(f"\n{'Data':<12}{'Descrição':<22}{'Categoria':<16}"
                  f"{'Valor':>13}{'Saldo':>14}")
            print("-" * 77)
            for l in linhas:
                v = l["valor"] if l["tipo"] == RECEITA else -l["valor"]
                saldo += v
                print(f"{fmt_data(l['data']):<12}{l['descricao'][:21]:<22}"
                      f"{l['categoria'][:15]:<16}{brl(v):>13}{brl(saldo):>14}")
        print(f"\nSaldo atual: {brl(saldo)}")


def evolucao_anual():
    ano = ler_ano()
    print(f"\nEVOLUÇÃO MENSAL - {ano}")
    print(f"\n{'Mês':<12}{'Receitas':>15}{'Despesas':>15}{'Saldo':>15}")
    print("-" * 57)
    tot_r = tot_d = 0
    with conectar() as con:
        for m in range(1, 13):
            rec, des = totais_mes(con, ano, m)
            tot_r += rec
            tot_d += des
            print(f"{MESES[m]:<12}{brl(rec):>15}{brl(des):>15}{brl(rec - des):>15}")
    print("-" * 57)
    print(f"{'Total':<12}{brl(tot_r):>15}{brl(tot_d):>15}{brl(tot_r - tot_d):>15}")


def menu_relatorios():
    while True:
        titulo("RELATÓRIOS")
        print("1) Despesas por categoria (mês)")
        print("2) Receitas por categoria (mês)")
        print("3) Extrato de uma conta")
        print("4) Evolução mensal do ano")
        print("0) Voltar")
        op = input("Opção: ").strip()
        if op == "1":
            relatorio_categorias(DESPESA)
        elif op == "2":
            relatorio_categorias(RECEITA)
        elif op == "3":
            extrato_conta()
        elif op == "4":
            evolucao_anual()
        elif op == "0":
            return
        else:
            print("Opção inválida.")
        pausar()


# ----------------------------------------------------------------------
# Dados de exemplo
# ----------------------------------------------------------------------
def popular_exemplo():
    with conectar() as con:
        if con.execute("SELECT COUNT(*) FROM lancamentos").fetchone()[0] > 0:
            print("Já existem lançamentos. Carga de exemplo cancelada.")
            return
        try:
            con.execute("INSERT INTO contas (nome, tipo, saldo_inicial) "
                        "VALUES ('Conta corrente','Conta corrente',150000)")
        except sqlite3.IntegrityError:
            pass
        conta = {r["nome"]: r["id"] for r in con.execute("SELECT * FROM contas")}
        cat = {(r["nome"], r["tipo"]): r["id"]
               for r in con.execute("SELECT * FROM categorias")}
        hoje = date.today()
        base = prefixo(hoje.year, hoje.month)
        dados = [
            (RECEITA, "Conta corrente", "Salário", "Salário do mês", 450000, "05"),
            (RECEITA, "Conta corrente", "Freelance", "Projeto de site", 80000, "12"),
            (DESPESA, "Conta corrente", "Moradia", "Aluguel", 130000, "06"),
            (DESPESA, "Conta corrente", "Alimentação", "Supermercado", 42000, "08"),
            (DESPESA, "Conta corrente", "Alimentação", "Almoço e lanches", 18500, "10"),
            (DESPESA, "Conta corrente", "Transporte", "Combustível", 25000, "11"),
            (DESPESA, "Conta corrente", "Lazer", "Cinema e jantar", 14000, "14"),
            (DESPESA, "Conta corrente", "Saúde", "Farmácia", 9800, "15"),
        ]
        for tipo, c, g, desc, valor, dia in dados:
            con.execute(
                "INSERT INTO lancamentos (tipo, conta_id, categoria_id, descricao, "
                "valor, data) VALUES (?,?,?,?,?,?)",
                (tipo, conta[c], cat[(g, tipo)], desc, valor, f"{base}-{dia}"))
    print(f"\n{OK_S} Dados de exemplo carregados no mês atual.")


# ----------------------------------------------------------------------
# Menu principal
# ----------------------------------------------------------------------
def menu_principal():
    iniciar_banco()
    while True:
        titulo("CONTROLE FINANCEIRO PESSOAL")
        print("1) Receitas")
        print("2) Despesas")
        print("3) Contas")
        print("4) Categorias")
        print("5) Saldo mensal")
        print("6) Relatórios")
        print("7) Carregar dados de exemplo")
        print("0) Sair")
        op = input("Opção: ").strip()
        if op == "1":
            menu_lancamentos(RECEITA)
        elif op == "2":
            menu_lancamentos(DESPESA)
        elif op == "3":
            menu_contas()
        elif op == "4":
            menu_categorias()
        elif op == "5":
            saldo_mensal()
            pausar()
        elif op == "6":
            menu_relatorios()
        elif op == "7":
            popular_exemplo()
            pausar()
        elif op == "0":
            print("\nAté logo!")
            break
        else:
            print("Opção inválida.")


if __name__ == "__main__":
    try:
        menu_principal()
    except (KeyboardInterrupt, EOFError):
        print("\n\nEncerrado pelo usuário.")
