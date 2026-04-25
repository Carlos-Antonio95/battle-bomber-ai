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
    "fugindo": 0,
    "acabou_de_colocar_bomba": False,
    "bomba_x": None,
    "bomba_y": None,
    "bomba_nivel": 1
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


def caminho_bloqueado(x1, y1, x2, y2, mapa):
    if x1 == x2:
        passo = 1 if y2 > y1 else -1

        for y in range(y1 + passo, y2, passo):
            if mapa[y][x1] not in [0, 3, 4]:
                return True

    elif y1 == y2:
        passo = 1 if x2 > x1 else -1

        for x in range(x1 + passo, x2, passo):
            if mapa[y1][x] not in [0, 3, 4]:
                return True

    return False


def posicao_em_perigo(x, y, bombas, mapa):
    # 1. Se a bomba já explodiu, o fogo ainda mata.
    for b in bombas:
        if b.explodida and getattr(b, "tempo_fogo", 0) > 0:
            if (x, y) in b.fogo:
                return True

    # 2. Bombas ainda não explodidas.
    posicoes_bombas = []

    for b in bombas:
        if not b.explodida:
            alcance = 1 + (getattr(b, "nivel", 1) - 1) * 2
            posicoes_bombas.append((b.x, b.y, alcance))

    # 3. Bomba recém colocada pela IA.
    if memoria["bomba_x"] is not None and memoria["bomba_y"] is not None:
        alcance_mem = 1 + (memoria["bomba_nivel"] - 1) * 2
        posicoes_bombas.append((memoria["bomba_x"], memoria["bomba_y"], alcance_mem))

    for bx, by, alcance in posicoes_bombas:
        if x == bx and y == by:
            return True

        if y == by and abs(x - bx) <= alcance:
            if not caminho_bloqueado(bx, by, x, y, mapa):
                return True

        if x == bx and abs(y - by) <= alcance:
            if not caminho_bloqueado(bx, by, x, y, mapa):
                return True

    return False


def existe_perigo_ativo(bombas):
    for b in bombas:
        if not b.explodida:
            return True

        if b.explodida and getattr(b, "tempo_fogo", 0) > 0:
            return True

    return False


def movimento_aleatorio(player, mapa, bombas):
    # Se existe bomba/fogo e ele está seguro, fica parado.
    if existe_perigo_ativo(bombas):
        if not posicao_em_perigo(player.grid_x, player.grid_y, bombas, mapa):
            return "parado"

    opcoes = []

    for acao, dx, dy in DIRECOES:
        nx = player.grid_x + dx
        ny = player.grid_y + dy

        if posicao_livre(nx, ny, mapa, bombas) and not posicao_em_perigo(nx, ny, bombas, mapa):
            opcoes.append(acao)

    if opcoes:
        return random.choice(opcoes)

    return "parado"


def fugir_da_bomba(player, mapa, bombas):
    opcoes_seguras = []
    opcoes_livres = []

    for acao, dx, dy in DIRECOES:
        nx = player.grid_x + dx
        ny = player.grid_y + dy

        if not posicao_livre(nx, ny, mapa, bombas):
            continue

        dist = 0

        if memoria["bomba_x"] is not None and memoria["bomba_y"] is not None:
            dist += abs(nx - memoria["bomba_x"]) + abs(ny - memoria["bomba_y"])

        for b in bombas:
            if not b.explodida:
                dist += abs(nx - b.x) + abs(ny - b.y)

        # guarda qualquer posição livre
        opcoes_livres.append((dist, acao))

        # guarda posições realmente seguras
        if not posicao_em_perigo(nx, ny, bombas, mapa):
            opcoes_seguras.append((dist, acao))

    # primeiro movimento depois da bomba: sair de cima dela de qualquer jeito
    if memoria["acabou_de_colocar_bomba"]:
        memoria["acabou_de_colocar_bomba"] = False

        if opcoes_seguras:
            opcoes_seguras.sort(reverse=True)
            return opcoes_seguras[0][1]

        if opcoes_livres:
            opcoes_livres.sort(reverse=True)
            return opcoes_livres[0][1]

        return "parado"

    # se já está seguro, fica escondido
    if not posicao_em_perigo(player.grid_x, player.grid_y, bombas, mapa):
        return "parado"

    # se ainda está em perigo, tenta ir para posição segura
    if opcoes_seguras:
        opcoes_seguras.sort(reverse=True)
        return opcoes_seguras[0][1]

    return "parado"

def tem_saida_segura(player, mapa, bombas):
    for _, dx, dy in DIRECOES:
        nx = player.grid_x + dx
        ny = player.grid_y + dy

        if posicao_livre(nx, ny, mapa, bombas) and not posicao_em_perigo(nx, ny, bombas, mapa):
            return True

    return False


def decidir_acao(player, mapa, jogadores, bombas, tempo_restante, pontos, hud_info, self_state):

    # limpa memória da bomba se ela já explodiu e sumiu do mapa
    if memoria["bomba_x"] is not None and memoria["bomba_y"] is not None:
        bomba_ainda_existe = False

        for b in bombas:
            if b.x == memoria["bomba_x"] and b.y == memoria["bomba_y"]:
                bomba_ainda_existe = True
                break

        if not bomba_ainda_existe:
            memoria["fugindo"] = 0
            memoria["acabou_de_colocar_bomba"] = False
            memoria["bomba_x"] = None
            memoria["bomba_y"] = None
            memoria["bomba_nivel"] = 1

    # modo fuga
    if memoria["fugindo"] > 0:
        memoria["fugindo"] -= 1

        # se não existe mais perigo, libera o fluxo normal
        if not existe_perigo_ativo(bombas):
            memoria["fugindo"] = 0
            memoria["acabou_de_colocar_bomba"] = False
            memoria["bomba_x"] = None
            memoria["bomba_y"] = None
            memoria["bomba_nivel"] = 1
        else:
            return fugir_da_bomba(player, mapa, bombas)

    # colocar bomba
    if parede_destrutivel_perto(player, mapa) and tem_saida_segura(player, mapa, bombas):
        if random.random() < GENES["chance_bomba"]:
            memoria["fugindo"] = GENES["tempo_fuga"]
            memoria["acabou_de_colocar_bomba"] = True
            memoria["bomba_x"] = player.grid_x
            memoria["bomba_y"] = player.grid_y
            memoria["bomba_nivel"] = player.bomba_nivel
            return "bomba"

    return movimento_aleatorio(player, mapa, bombas)