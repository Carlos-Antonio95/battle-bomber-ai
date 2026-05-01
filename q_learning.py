import json
import os
import random


ACOES_MACRO = [
    "fugir",
    "atacar",
    "plantar_bomba",
    "quebrar_parede",
    "buscar_powerup",
    "esperar",
]


def carregar_q_table(jogador):
    arquivo = f"q_table_jogador{jogador}.json"
    if not os.path.exists(arquivo):
        return {}

    try:
        with open(arquivo, "r") as f:
            dados = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

    return dados if isinstance(dados, dict) else {}


def salvar_q_table(q_table, jogador):
    arquivo = f"q_table_jogador{jogador}.json"
    with open(arquivo, "w") as f:
        json.dump(q_table, f, indent=4, sort_keys=True)


def _bool_int(valor):
    return 1 if valor else 0


def obter_estado(
    jogador_em_perigo=False,
    inimigo_perto=False,
    bomba_disponivel=False,
    parede_destrutivel_perto=False,
    powerup_perto=False,
    preso_ou_sem_rota=False,
):
    partes = (
        _bool_int(jogador_em_perigo),
        _bool_int(inimigo_perto),
        _bool_int(bomba_disponivel),
        _bool_int(parede_destrutivel_perto),
        _bool_int(powerup_perto),
        _bool_int(preso_ou_sem_rota),
    )
    return "|".join(str(p) for p in partes)


def _garantir_estado(q_table, estado):
    if estado not in q_table or not isinstance(q_table[estado], dict):
        q_table[estado] = {acao: 0.0 for acao in ACOES_MACRO}
    else:
        for acao in ACOES_MACRO:
            q_table[estado].setdefault(acao, 0.0)


def escolher_acao_q(q_table, estado, epsilon=0.10):
    _garantir_estado(q_table, estado)

    if random.random() < epsilon:
        return random.choice(ACOES_MACRO)

    valores = q_table[estado]
    maior = max(valores.values())
    melhores = [acao for acao, valor in valores.items() if valor == maior]
    return random.choice(melhores)


def atualizar_q_table(q_table, estado, acao, recompensa, proximo_estado, alpha=0.20, gamma=0.90):
    if estado is None or acao is None:
        return q_table

    _garantir_estado(q_table, estado)
    _garantir_estado(q_table, proximo_estado)

    valor_atual = q_table[estado].get(acao, 0.0)
    melhor_futuro = max(q_table[proximo_estado].values())
    novo_valor = valor_atual + alpha * (recompensa + gamma * melhor_futuro - valor_atual)
    q_table[estado][acao] = round(novo_valor, 4)
    return q_table
