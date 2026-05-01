import json
import os
import random


ACOES_Q = [
    "fugir",
    "pegar_powerup",
    "farmar",
    "atacar",
    "reposicionar",
    "esperar",
]


def carregar_q_table(caminho):
    if not os.path.exists(caminho):
        return {}

    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        return {}

    return dados if isinstance(dados, dict) else {}


def salvar_q_table(q_table, caminho):
    pasta = os.path.dirname(caminho)
    if pasta:
        os.makedirs(pasta, exist_ok=True)

    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(q_table, arquivo, indent=4, sort_keys=True)


def estado_para_chave(estado):
    return "|".join("1" if valor else "0" for valor in estado)


def inicializar_estado(q_table, estado):
    chave = estado_para_chave(estado) if not isinstance(estado, str) else estado

    if chave not in q_table or not isinstance(q_table[chave], dict):
        q_table[chave] = {acao: 0.0 for acao in ACOES_Q}
    else:
        for acao in ACOES_Q:
            q_table[chave].setdefault(acao, 0.0)

    return chave


def escolher_acao_q(q_table, estado, epsilon, acoes_validas=None):
    chave = inicializar_estado(q_table, estado)
    validas = list(acoes_validas or ACOES_Q)

    if not validas:
        validas = ["reposicionar"]

    if random.random() < epsilon:
        return random.choice(validas)

    valores = q_table[chave]
    maior_valor = max(valores.get(acao, 0.0) for acao in validas)
    melhores = [acao for acao in validas if valores.get(acao, 0.0) == maior_valor]
    return random.choice(melhores)


def atualizar_q_table(q_table, estado, acao, recompensa, novo_estado, alpha, gamma):
    if estado is None or acao is None:
        return q_table

    chave = inicializar_estado(q_table, estado)
    nova_chave = inicializar_estado(q_table, novo_estado)

    valor_atual = q_table[chave].get(acao, 0.0)
    melhor_futuro = max(q_table[nova_chave].values())
    novo_valor = valor_atual + alpha * (recompensa + gamma * melhor_futuro - valor_atual)
    q_table[chave][acao] = round(novo_valor, 4)
    return q_table
