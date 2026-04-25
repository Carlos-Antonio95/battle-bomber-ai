import random
import json

with open("genes_jogador4.json", "r") as f:
    GENES = json.load(f)


DIRECOES = [
    ("cima", 0, -1),
    ("baixo", 0, 1),
    ("esquerda", -1, 0),
    ("direita", 1, 0),
]

memoria = {
    "fugindo": 0
}

def posicao_livre(x, y, mapa, bombas):
    if y < 0 or y >= len(mapa) or x < 0 or x >= len(mapa[0]):
        return False

    if mapa[y][x] not in [0, 3, 4]:
        return False

    for b in bombas:
        if not b.explodida and b.x == x and b.y == y:
            return False

    return True


def parede_destrutivel_perto(player, mapa):
    for _, dx, dy in DIRECOES:
        nx = player.grid_x + dx
        ny = player.grid_y + dy

        if 0 <= ny < len(mapa) and 0 <= nx < len(mapa[0]):
            if mapa[ny][nx] == 1:
                return True

    return False


def movimento_aleatorio(player, mapa, bombas):
    opcoes = []

    for acao, dx, dy in DIRECOES:
        nx = player.grid_x + dx
        ny = player.grid_y + dy

        if posicao_livre(nx, ny, mapa, bombas):
            opcoes.append(acao)

    if opcoes:
        return random.choice(opcoes)

    return "parado"


def fugir_da_bomba(player, mapa, bombas):
    opcoes = []

    for acao, dx, dy in DIRECOES:
        nx = player.grid_x + dx
        ny = player.grid_y + dy

        if not posicao_livre(nx, ny, mapa, bombas):
            continue

        # escolhe movimentos que afastam da bomba mais próxima
        distancia = 0
        for b in bombas:
            if not b.explodida:
                distancia += abs(nx - b.x) + abs(ny - b.y)

        opcoes.append((distancia, acao))

    if opcoes:
        opcoes.sort(reverse=True)
        return opcoes[0][1]

    return "parado"


def tem_saida(player, mapa, bombas):
    for _, dx, dy in DIRECOES:
        nx = player.grid_x + dx
        ny = player.grid_y + dy

        if posicao_livre(nx, ny, mapa, bombas):
            return True

    return False


def decidir_acao(player, mapa, jogadores, bombas, tempo_restante, pontos, hud_info, self_state):

    # Se acabou de colocar bomba, foge por alguns turnos
    if memoria["fugindo"] > 0:
        memoria["fugindo"] -= 1
        return fugir_da_bomba(player, mapa, bombas)

    # Se tem parede destrutível perto e tem saída, coloca bomba
     # Só coloca bomba se tiver parede destrutível perto E tiver saída
    if parede_destrutivel_perto(player, mapa) and tem_saida(player, mapa, bombas):
        if random.random() < GENES["chance_bomba"]:
            memoria["fugindo"] = GENES["tempo_fuga"]
            return "bomba"

    # Caso contrário, anda pelo mapa
    return movimento_aleatorio(player, mapa, bombas)