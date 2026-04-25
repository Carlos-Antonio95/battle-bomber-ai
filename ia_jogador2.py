import random
import json
from collections import deque

with open("genes_jogador2.json", "r") as f:
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
    for b in bombas:
        if b.explodida and getattr(b, "tempo_fogo", 0) > 0:
            if (x, y) in b.fogo:
                return True

    posicoes_bombas = []

    for b in bombas:
        if not b.explodida:
            alcance = 1 + (getattr(b, "nivel", 1) - 1) * 2
            posicoes_bombas.append((b.x, b.y, alcance))

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


def distancia_segura_da_bomba(x, y, bombas):
    margem = GENES.get("margem_seguranca", 1)

    for b in bombas:
        if b.explodida:
            continue

        alcance = 1 + (getattr(b, "nivel", 1) - 1) * 2
        distancia = abs(x - b.x) + abs(y - b.y)

        if distancia <= alcance + margem:
            return False

    if memoria["bomba_x"] is not None and memoria["bomba_y"] is not None:
        alcance_mem = 1 + (memoria["bomba_nivel"] - 1) * 2
        distancia_mem = abs(x - memoria["bomba_x"]) + abs(y - memoria["bomba_y"])

        if distancia_mem <= alcance_mem + margem:
            return False

    return True


def existe_perigo_ativo(bombas):
    for b in bombas:
        if not b.explodida:
            return True

        if b.explodida and getattr(b, "tempo_fogo", 0) > 0:
            return True

    return False


def pegar_powerup_perto(player, mapa, bombas):
    opcoes = []

    for acao, dx, dy in DIRECOES:
        nx = player.grid_x + dx
        ny = player.grid_y + dy

        if not posicao_livre(nx, ny, mapa, bombas):
            continue

        if posicao_em_perigo(nx, ny, bombas, mapa):
            continue

        if mapa[ny][nx] in [3, 4]:
            opcoes.append(acao)

    if opcoes:
        return random.choice(opcoes)

    return None


def movimento_aleatorio(player, mapa, bombas):
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
    opcoes_aceitaveis = []
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

        opcoes_livres.append((dist, acao))

        if not posicao_em_perigo(nx, ny, bombas, mapa):
            opcoes_aceitaveis.append((dist, acao))

            if distancia_segura_da_bomba(nx, ny, bombas):
                opcoes_seguras.append((dist, acao))

    # primeiro passo: sair de cima da bomba de qualquer jeito
    if memoria["acabou_de_colocar_bomba"]:
        memoria["acabou_de_colocar_bomba"] = False

        if opcoes_seguras:
            opcoes_seguras.sort(reverse=True)
            return opcoes_seguras[0][1]

        if opcoes_aceitaveis:
            opcoes_aceitaveis.sort(reverse=True)
            return opcoes_aceitaveis[0][1]

        if opcoes_livres:
            opcoes_livres.sort(reverse=True)
            return opcoes_livres[0][1]

        return "parado"

    # depois que saiu da bomba, se estiver seguro, fica parado escondido
    if not posicao_em_perigo(player.grid_x, player.grid_y, bombas, mapa):
        return "parado"

    if opcoes_seguras:
        opcoes_seguras.sort(reverse=True)
        return opcoes_seguras[0][1]

    if opcoes_aceitaveis:
        opcoes_aceitaveis.sort(reverse=True)
        return opcoes_aceitaveis[0][1]

    return "parado"

def bfs_powerup(player, mapa, bombas):
    fila = deque()
    visitados = set()

    fila.append((player.grid_x, player.grid_y, []))
    visitados.add((player.grid_x, player.grid_y))

    while fila:
        x, y, caminho = fila.popleft()

        if mapa[y][x] in [3, 4] and caminho:
            return caminho[0]

        for acao, dx, dy in DIRECOES:
            nx = x + dx
            ny = y + dy

            if (nx, ny) in visitados:
                continue

            if not posicao_livre(nx, ny, mapa, bombas):
                continue

            if posicao_em_perigo(nx, ny, bombas, mapa):
                continue

            visitados.add((nx, ny))
            fila.append((nx, ny, caminho + [acao]))

    return None


def limpar_memoria_bomba():
    memoria["fugindo"] = 0
    memoria["acabou_de_colocar_bomba"] = False
    memoria["bomba_x"] = None
    memoria["bomba_y"] = None
    memoria["bomba_nivel"] = 1


def tem_rota_fuga_apos_bomba(player, mapa, bombas):
    bomba_x = player.grid_x
    bomba_y = player.grid_y
    bomba_nivel = player.bomba_nivel
    alcance = 1 + (bomba_nivel - 1) * 2
    margem = GENES.get("margem_seguranca", 1)

    fila = deque()
    visitados = set()

    fila.append((player.grid_x, player.grid_y, 0))
    visitados.add((player.grid_x, player.grid_y))

    while fila:
        x, y, passos = fila.popleft()

        # não conta a posição inicial como fuga
        if passos > 0:
            distancia = abs(x - bomba_x) + abs(y - bomba_y)

            fora_linha = x != bomba_x and y != bomba_y
            longe_o_suficiente = distancia > alcance + margem

            if passos >= 2 and (fora_linha or longe_o_suficiente):
                if not posicao_em_perigo(x, y, bombas, mapa):
                    return True

        for _, dx, dy in DIRECOES:
            nx = x + dx
            ny = y + dy

            if (nx, ny) in visitados:
                continue

            if not posicao_livre(nx, ny, mapa, bombas):
                continue

            visitados.add((nx, ny))
            fila.append((nx, ny, passos + 1))

    return False


def decidir_acao(player, mapa, jogadores, bombas, tempo_restante, pontos, hud_info, self_state):

    if memoria["bomba_x"] is not None and memoria["bomba_y"] is not None:
        bomba_ainda_existe = False

        for b in bombas:
            if b.x == memoria["bomba_x"] and b.y == memoria["bomba_y"]:
                bomba_ainda_existe = True
                break

        if not bomba_ainda_existe:
            limpar_memoria_bomba()

    if memoria["fugindo"] > 0:
        memoria["fugindo"] -= 1

        if not existe_perigo_ativo(bombas):
            limpar_memoria_bomba()
        else:
            return fugir_da_bomba(player, mapa, bombas)

    acao_bfs = bfs_powerup(player, mapa, bombas)
    if acao_bfs:
        return acao_bfs

    acao_powerup = pegar_powerup_perto(player, mapa, bombas)
    if acao_powerup:
        return acao_powerup

    if parede_destrutivel_perto(player, mapa) and tem_rota_fuga_apos_bomba(player, mapa, bombas):
        if random.random() < GENES.get("chance_bomba", 0.09):
            memoria["fugindo"] = GENES.get("tempo_fuga", 35)
            memoria["acabou_de_colocar_bomba"] = True
            memoria["bomba_x"] = player.grid_x
            memoria["bomba_y"] = player.grid_y
            memoria["bomba_nivel"] = player.bomba_nivel
            return "bomba"

    return movimento_aleatorio(player, mapa, bombas)