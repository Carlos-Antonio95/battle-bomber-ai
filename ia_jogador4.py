import random
import json
from collections import deque

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
    "bomba_nivel": 1,
    "jogadores": [],
    "rota_fuga": [],

    # Anti-loop: evita ficar subindo/descendo sem decisão
    "ultima_posicao": None,
    "ultima_acao": None,
    "manter_acao": 0
}
TEMPO_PASSO_ESTIMADO = 0.13
MAX_PASSOS_FUGA = 8

def posicao_livre(x, y, mapa, bombas):
    if y < 0 or y >= len(mapa) or x < 0 or x >= len(mapa[0]):
        return False

    if mapa[y][x] not in [0, 3, 4]:
        return False

    for b in bombas:
        if not b.explodida and b.x == x and b.y == y:
            return False

    return True

def posicao_livre_sem_jogador(x, y, mapa, bombas, player):
    if not posicao_livre(x, y, mapa, bombas):
        return False

    for j in memoria.get("jogadores", []):
        if j is player:
            continue

        if not j.ativo:
            continue

        if j.grid_x == x and j.grid_y == y:
            return False

    return True

def proxima_posicao(player, acao):
    for nome, dx, dy in DIRECOES:
        if nome == acao:
            return player.grid_x + dx, player.grid_y + dy

    return player.grid_x, player.grid_y

def acao_oposta(acao):
    opostas = {
        "cima": "baixo",
        "baixo": "cima",
        "esquerda": "direita",
        "direita": "esquerda"
    }

    return opostas.get(acao)


def pode_manter_acao(player, acao, mapa, bombas):
    if acao is None or acao == "parado":
        return False

    nx, ny = proxima_posicao(player, acao)

    if not posicao_livre(nx, ny, mapa, bombas):
        return False

    if posicao_em_perigo(nx, ny, bombas, mapa):
        return False

    return True


def registrar_acao(player, acao):
    memoria["ultima_posicao"] = (player.grid_x, player.grid_y)
    memoria["ultima_acao"] = acao

    if acao != "parado":
        memoria["manter_acao"] = 2
    else:
        memoria["manter_acao"] = 0

    return acao

def contar_saidas_seguras(x, y, mapa, bombas):
    mapa_perigo = criar_mapa_perigo(mapa, bombas)
    saidas = 0

    for _, dx, dy in DIRECOES:
        nx = x + dx
        ny = y + dy

        if posicao_livre(nx, ny, mapa, bombas) and not posicao_perigosa_mapa(nx, ny, mapa_perigo):
            saidas += 1

    return saidas

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

def posicao_quase_cela(x, y, mapa, bombas):
    bloqueios = 0

    for _, dx, dy in DIRECOES:
        nx = x + dx
        ny = y + dy

        if not posicao_livre(nx, ny, mapa, bombas):
            bloqueios += 1

    return bloqueios

def pegar_powerup_perto(player, mapa, bombas):
    opcoes = []

    for acao, dx, dy in DIRECOES:
        nx = player.grid_x + dx
        ny = player.grid_y + dy

        if not posicao_livre_sem_jogador(nx, ny, mapa, bombas, player):
            continue

        if posicao_em_perigo(nx, ny, bombas, mapa):
            continue

        if mapa[ny][nx] in [3, 4]:
            opcoes.append(acao)

    # fallback: permite passar por jogador se necessário
    if not opcoes:
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

        # tenta evitar jogador primeiro
        if posicao_livre_sem_jogador(nx, ny, mapa, bombas, player) \
           and not posicao_em_perigo(nx, ny, bombas, mapa):
            opcoes.append(acao)

    # fallback: se travar, ignora jogador
    if not opcoes:
        for acao, dx, dy in DIRECOES:
            nx = player.grid_x + dx
            ny = player.grid_y + dy

            if posicao_livre(nx, ny, mapa, bombas) \
               and not posicao_em_perigo(nx, ny, bombas, mapa):
                opcoes.append(acao)

    if opcoes:
        ultima_acao = memoria.get("ultima_acao")
        oposta = acao_oposta(ultima_acao)

        opcoes_filtradas = [acao for acao in opcoes if acao != oposta]

        if opcoes_filtradas:
            return registrar_acao(player, random.choice(opcoes_filtradas))

        return registrar_acao(player, random.choice(opcoes))

    return registrar_acao(player, "parado")

def pontuar_posicao_segura(x, y, mapa, bombas):
    pontos = 0

    mapa_perigo = criar_mapa_perigo(mapa, bombas)

    if posicao_perigosa_mapa(x, y, mapa_perigo):
        return -9999

    # quanto mais saídas livres ao redor, melhor
    saidas = 0
    for _, dx, dy in DIRECOES:
        nx = x + dx
        ny = y + dy

        if posicao_livre(nx, ny, mapa, bombas):
            saidas += 1

            if not posicao_perigosa_mapa(nx, ny, mapa_perigo):
                pontos += 3

    pontos += saidas * 2

    # evita ficar em beco sem saída
    if saidas <= 1:
        pontos -= 8

    bloqueios = posicao_quase_cela(x, y, mapa, bombas)

    if bloqueios == 3:
        pontos -= 15  # quase beco

    if bloqueios == 4:
        pontos -= 100  # morto certo

    # distancia das bombas
    for b in bombas:
        if not b.explodida:
            pontos += abs(x - b.x) + abs(y - b.y)

    if memoria["bomba_x"] is not None and memoria["bomba_y"] is not None:
        pontos += abs(x - memoria["bomba_x"]) + abs(y - memoria["bomba_y"])

    # power-up é bom, mas segurança vem primeiro
    if mapa[y][x] in [3, 4]:
        pontos += 5

    return pontos
def esconderijo_bom(player, mapa, bombas):
    x = player.grid_x
    y = player.grid_y

    if posicao_em_perigo(x, y, bombas, mapa):
        return False

    if not distancia_segura_da_bomba(x, y, bombas):
        return False

    saidas = contar_saidas_seguras(x, y, mapa, bombas)

    if memoria["bomba_x"] is not None and memoria["bomba_y"] is not None:
        if saidas < 2:
            return False
    else:
        if saidas < 1:
            return False

    return True




def posicao_no_raio_bomba(x, y, bx, by, alcance, mapa):
    if x == bx and y == by:
        return True

    if y == by and abs(x - bx) <= alcance:
        return not caminho_bloqueado(bx, by, x, y, mapa)

    if x == bx and abs(y - by) <= alcance:
        return not caminho_bloqueado(bx, by, x, y, mapa)

    return False

def calcular_tempos_cadeia_bombas(bombas, mapa):
    tempos = {}

    for b in bombas:
        if not b.explodida:
            tempos[b] = getattr(b, "tempo_explosao", 4)

    mudou = True

    while mudou:
        mudou = False

        for b in bombas:
            if b.explodida or b not in tempos:
                continue

            alcance = 1 + (getattr(b, "nivel", 1) - 1) * 2

            for outra in bombas:
                if outra is b or outra.explodida or outra not in tempos:
                    continue

                if posicao_no_raio_bomba(outra.x, outra.y, b.x, b.y, alcance, mapa):
                    if tempos[outra] > tempos[b]:
                        tempos[outra] = tempos[b]
                        mudou = True

    return tempos

def tempo_perigo_posicao(x, y, bombas, mapa):
    menor_tempo = None
    tempos_cadeia = calcular_tempos_cadeia_bombas(bombas, mapa)

    for b in bombas:
        if b.explodida and getattr(b, "tempo_fogo", 0) > 0:
            if (x, y) in b.fogo:
                return 0

        if not b.explodida:
            alcance = 1 + (getattr(b, "nivel", 1) - 1) * 2

            if posicao_no_raio_bomba(x, y, b.x, b.y, alcance, mapa):
                tempo = tempos_cadeia.get(b, getattr(b, "tempo_explosao", 4))

                if menor_tempo is None or tempo < menor_tempo:
                    menor_tempo = tempo

    if memoria["bomba_x"] is not None and memoria["bomba_y"] is not None:
        alcance_mem = 1 + (memoria["bomba_nivel"] - 1) * 2

        if posicao_no_raio_bomba(
            x,
            y,
            memoria["bomba_x"],
            memoria["bomba_y"],
            alcance_mem,
            mapa
        ):
            if menor_tempo is None or 4 < menor_tempo:
                menor_tempo = 4

    return menor_tempo

def posicao_segura_no_tempo(x, y, passos, bombas, mapa):
    tempo_chegada = passos * TEMPO_PASSO_ESTIMADO
    cautela = GENES.get("cautela_bomba", 1.0)

    tempo_perigo = tempo_perigo_posicao(x, y, bombas, mapa)

    if tempo_perigo is None:
        return True

    margem_tempo = 0.40 * cautela

    return tempo_perigo > tempo_chegada + margem_tempo


def bfs_fuga_segura(player, mapa, bombas):
    fila = deque()
    visitados = set()
    melhores = []

    fila.append((player.grid_x, player.grid_y, [], 0))
    visitados.add((player.grid_x, player.grid_y))

    while fila:
        x, y, caminho, passos = fila.popleft()

        if passos > MAX_PASSOS_FUGA:
            continue

        if passos > 0:
            if posicao_segura_no_tempo(x, y, passos, bombas, mapa):
                if not posicao_em_perigo(x, y, bombas, mapa):
                    if distancia_segura_da_bomba(x, y, bombas):
                        if memoria["bomba_x"] is not None and memoria["bomba_y"] is not None:
                            if not casa_vira_cela_com_bomba(
                                x,
                                y,
                                mapa,
                                bombas,
                                memoria["bomba_x"],
                                memoria["bomba_y"]
                            ):
                                score = pontuar_posicao_segura(x, y, mapa, bombas)
                                score += contar_saidas_seguras(x, y, mapa, bombas) * 5
                                score -= passos
                                melhores.append((score, caminho[0]))
                        else:
                            score = pontuar_posicao_segura(x, y, mapa, bombas)
                            score += contar_saidas_seguras(x, y, mapa, bombas) * 5
                            score -= passos
                            melhores.append((score, caminho[0]))

        for acao, dx, dy in DIRECOES:
            nx = x + dx
            ny = y + dy

            if (nx, ny) in visitados:
                continue

            if not posicao_livre(nx, ny, mapa, bombas):
                continue

            novo_caminho = caminho + [acao]
            novo_passos = passos + 1

            if not posicao_segura_no_tempo(nx, ny, novo_passos, bombas, mapa):
                continue

            visitados.add((nx, ny))
            fila.append((nx, ny, novo_caminho, novo_passos))

    if melhores:
        melhores.sort(reverse=True)
        return melhores[0][1]

    return None

def fugir_da_bomba(player, mapa, bombas):
     # segue rota antiga somente se ainda for segura
    if memoria.get("rota_fuga"):
        acao = memoria["rota_fuga"][0]
        nx, ny = proxima_posicao(player, acao)

        if posicao_livre(nx, ny, mapa, bombas) \
           and posicao_segura_no_tempo(nx, ny, 1, bombas, mapa) \
           and not posicao_em_perigo(nx, ny, bombas, mapa):

            memoria["rota_fuga"].pop(0)
            return acao

        # rota ficou perigosa, recalcula
        memoria["rota_fuga"] = []

    acao_bfs = bfs_fuga_segura(player, mapa, bombas)

    if acao_bfs:
        memoria["acabou_de_colocar_bomba"] = False
        return acao_bfs

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

        # qualquer casa livre para emergência
        opcoes_livres.append((dist, acao))

        # casa realmente segura/inteligente
        score = pontuar_posicao_segura(nx, ny, mapa, bombas)

        if score > -9999:
            opcoes_seguras.append((score, acao))

    # primeiro passo: sair de cima da bomba de qualquer jeito
    if memoria["acabou_de_colocar_bomba"]:
        memoria["acabou_de_colocar_bomba"] = False

        if opcoes_seguras:
            opcoes_seguras.sort(reverse=True)
            return opcoes_seguras[0][1]

        if opcoes_livres:
            opcoes_livres.sort(reverse=True)
            return opcoes_livres[0][1]

        return "parado"

    # se já está em esconderijo realmente bom, fica parado
    if esconderijo_bom(player, mapa, bombas):
        return "parado"

    # se ainda não está em esconderijo bom, tenta ir para melhor posição segura
    if opcoes_seguras:
        opcoes_seguras.sort(reverse=True)
        return opcoes_seguras[0][1]

    # último recurso: se afastar da bomba
    if opcoes_livres:
        opcoes_livres.sort(reverse=True)
        return opcoes_livres[0][1]

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

def posicao_livre_com_bomba_virtual(x, y, mapa, bombas, bomba_x, bomba_y):
    if y < 0 or y >= len(mapa) or x < 0 or x >= len(mapa[0]):
        return False

    if mapa[y][x] not in [0, 3, 4]:
        return False

    if x == bomba_x and y == bomba_y:
        return False

    for b in bombas:
        if not b.explodida and b.x == x and b.y == y:
            return False

    return True


def contar_saidas_com_bomba_virtual(x, y, mapa, bombas, bomba_x, bomba_y):
    saidas = 0

    for _, dx, dy in DIRECOES:
        nx = x + dx
        ny = y + dy

        if posicao_livre_com_bomba_virtual(nx, ny, mapa, bombas, bomba_x, bomba_y):
            saidas += 1

    return saidas


def casa_vira_cela_com_bomba(x, y, mapa, bombas, bomba_x, bomba_y):
    saidas = contar_saidas_com_bomba_virtual(x, y, mapa, bombas, bomba_x, bomba_y)

    return saidas == 0

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

                    if casa_vira_cela_com_bomba(x, y, mapa, bombas, bomba_x, bomba_y):
                        continue

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
def criar_mapa_perigo(mapa, bombas):
    linhas = len(mapa)
    colunas = len(mapa[0])

    perigo = [[0 for _ in range(colunas)] for _ in range(linhas)]

    # fogo ativo
    for b in bombas:
        if b.explodida and getattr(b, "tempo_fogo", 0) > 0:
            for fx, fy in b.fogo:
                if 0 <= fy < linhas and 0 <= fx < colunas:
                    perigo[fy][fx] = 2

    # bombas ativas
    for b in bombas:
        if b.explodida:
            continue

        alcance = 1 + (getattr(b, "nivel", 1) - 1) * 2

        perigo[b.y][b.x] = 1

        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            for i in range(1, alcance + 1):
                nx = b.x + dx * i
                ny = b.y + dy * i

                if not (0 <= nx < colunas and 0 <= ny < linhas):
                    break

                if mapa[ny][nx] == 2:
                    break

                perigo[ny][nx] = 1

                if mapa[ny][nx] == 1:
                    break

    # bomba recém colocada pela IA
    if memoria["bomba_x"] is not None and memoria["bomba_y"] is not None:
        bx = memoria["bomba_x"]
        by = memoria["bomba_y"]
        alcance = 1 + (memoria["bomba_nivel"] - 1) * 2

        if 0 <= by < linhas and 0 <= bx < colunas:
            perigo[by][bx] = 1

        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            for i in range(1, alcance + 1):
                nx = bx + dx * i
                ny = by + dy * i

                if not (0 <= nx < colunas and 0 <= ny < linhas):
                    break

                if mapa[ny][nx] == 2:
                    break

                perigo[ny][nx] = 1

                if mapa[ny][nx] == 1:
                    break

    return perigo


def posicao_perigosa_mapa(x, y, mapa_perigo):
    if y < 0 or y >= len(mapa_perigo) or x < 0 or x >= len(mapa_perigo[0]):
        return True

    return mapa_perigo[y][x] > 0

def posicao_em_perigo(x, y, bombas, mapa):
    mapa_perigo = criar_mapa_perigo(mapa, bombas)
    return posicao_perigosa_mapa(x, y, mapa_perigo)

def perigo_iminente(player, mapa, bombas):
    tempo = tempo_perigo_posicao(player.grid_x, player.grid_y, bombas, mapa)

    if tempo is None:
        return False

    limite = GENES.get("tempo_perigo_iminente", 0.45)

    return tempo <= limite

def caminho_livre_ate_inimigo(player, inimigo, mapa):
    x1, y1 = player.grid_x, player.grid_y
    x2, y2 = inimigo.grid_x, inimigo.grid_y

    if x1 == x2:
        passo = 1 if y2 > y1 else -1
        for y in range(y1 + passo, y2, passo):
            if mapa[y][x1] not in [0, 3, 4]:
                return False
        return True

    if y1 == y2:
        passo = 1 if x2 > x1 else -1
        for x in range(x1 + passo, x2, passo):
            if mapa[y1][x] not in [0, 3, 4]:
                return False
        return True

    return False

def inimigo_no_raio(player, jogadores, mapa):
    alcance = 1 + (player.bomba_nivel - 1) * 2

    for inimigo in jogadores:
        if inimigo is player or not inimigo.ativo:
            continue

        dist = abs(player.grid_x - inimigo.grid_x) + abs(player.grid_y - inimigo.grid_y)

        if dist <= alcance:
            if caminho_livre_ate_inimigo(player, inimigo, mapa):
                return True

    return False

def distancia_inimigo_mais_proximo(player, jogadores):
    menor = None

    for inimigo in jogadores:
        if inimigo is player or not inimigo.ativo:
            continue

        dist = abs(player.grid_x - inimigo.grid_x) + abs(player.grid_y - inimigo.grid_y)

        if menor is None or dist < menor:
            menor = dist

    return menor

def perseguir_inimigo(player, mapa, bombas, jogadores):
    alvo = None
    menor_dist = None

    for inimigo in jogadores:
        if inimigo is player or not inimigo.ativo:
            continue

        dist = abs(player.grid_x - inimigo.grid_x) + abs(player.grid_y - inimigo.grid_y)

        if menor_dist is None or dist < menor_dist:
            menor_dist = dist
            alvo = inimigo

    if alvo is None:
        return None

    opcoes = []

    for acao, dx, dy in DIRECOES:
        nx = player.grid_x + dx
        ny = player.grid_y + dy

        if not posicao_livre(nx, ny, mapa, bombas):
            continue

        if posicao_em_perigo(nx, ny, bombas, mapa):
            continue

        nova_dist = abs(nx - alvo.grid_x) + abs(ny - alvo.grid_y)

        penalidade = 0

        if memoria.get("ultima_posicao") == (nx, ny):
            penalidade += 2

        if acao == acao_oposta(memoria.get("ultima_acao")):
            penalidade += 1

        opcoes.append((nova_dist + penalidade, acao))

    if opcoes:
        opcoes.sort()
        return registrar_acao(player, opcoes[0][1])

    return None

def ataque_basico(player, mapa, jogadores, bombas):

    # 💣 ATAQUE DIRETO
    if inimigo_no_raio(player, jogadores, mapa):
        if tem_rota_fuga_apos_bomba(player, mapa, bombas):
            if random.random() < GENES.get("chance_ataque", 0.20):

                memoria["fugindo"] = GENES.get("tempo_fuga", 35)
                memoria["acabou_de_colocar_bomba"] = True
                memoria["bomba_x"] = player.grid_x
                memoria["bomba_y"] = player.grid_y
                memoria["bomba_nivel"] = player.bomba_nivel
                memoria["rota_fuga"] = []

                return "bomba"

    # 🎯 PERSEGUIÇÃO
    dist = distancia_inimigo_mais_proximo(player, jogadores)

    if dist is not None and dist <= GENES.get("distancia_perseguir", 5):
        acao = perseguir_inimigo(player, mapa, bombas, jogadores)

        if acao:
            return acao

    return None
def decidir_acao(player, mapa, jogadores, bombas, tempo_restante, pontos, hud_info, self_state):
    memoria["jogadores"] = jogadores

    # Primeiro limpa a memória da bomba se ela já explodiu/sumiu
    if memoria["bomba_x"] is not None and memoria["bomba_y"] is not None:
        bomba_ainda_existe = False

        for b in bombas:
            if b.x == memoria["bomba_x"] and b.y == memoria["bomba_y"]:
                bomba_ainda_existe = True
                break

        if not bomba_ainda_existe:
            limpar_memoria_bomba()

    # Mantém a última ação por pouco tempo apenas se não houver perigo.
    # Isso reduz o loop de ficar subindo e descendo sem atrapalhar a fuga.
    if not posicao_em_perigo(player.grid_x, player.grid_y, bombas, mapa) \
       and not perigo_iminente(player, mapa, bombas):

        if memoria.get("manter_acao", 0) > 0:
            ultima = memoria.get("ultima_acao")

            if pode_manter_acao(player, ultima, mapa, bombas):
                memoria["manter_acao"] -= 1
                return ultima
            else:
                memoria["manter_acao"] = 0

    # EMERGÊNCIA REAL: só foge se a explosão estiver quase acontecendo
    if perigo_iminente(player, mapa, bombas):
        memoria["fugindo"] = GENES.get("tempo_fuga", 35)
        memoria["rota_fuga"] = []
        return fugir_da_bomba(player, mapa, bombas)

    # MODO FUGA
    if memoria["fugindo"] > 0:
        memoria["fugindo"] -= 1

        if posicao_em_perigo(player.grid_x, player.grid_y, bombas, mapa) \
           or not distancia_segura_da_bomba(player.grid_x, player.grid_y, bombas):

            return fugir_da_bomba(player, mapa, bombas)

        if esconderijo_bom(player, mapa, bombas):
            limpar_memoria_bomba()
        else:
            return fugir_da_bomba(player, mapa, bombas)

    # BUSCAR POWER-UP
    acao_bfs = bfs_powerup(player, mapa, bombas)
    if acao_bfs:
        return acao_bfs

    acao_powerup = pegar_powerup_perto(player, mapa, bombas)
    if acao_powerup:
        return acao_powerup
    
    # 🔥 ATAQUE BÁSICO
    acao_ataque = ataque_basico(player, mapa, jogadores, bombas)
    if acao_ataque:
        return acao_ataque

    # COLOCAR BOMBA
    if parede_destrutivel_perto(player, mapa) and tem_rota_fuga_apos_bomba(player, mapa, bombas):
        if random.random() < GENES.get("chance_bomba", 0.09):
            memoria["fugindo"] = GENES.get("tempo_fuga", 35)
            memoria["acabou_de_colocar_bomba"] = True
            memoria["bomba_x"] = player.grid_x
            memoria["bomba_y"] = player.grid_y
            memoria["bomba_nivel"] = player.bomba_nivel
            return "bomba"

    return movimento_aleatorio(player, mapa, bombas)