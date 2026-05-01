from collections import deque
import os
import random

from q_learning import carregar_q_table, salvar_q_table, escolher_acao_q, atualizar_q_table


DIRECOES = [
    ("cima", 0, -1),
    ("baixo", 0, 1),
    ("esquerda", -1, 0),
    ("direita", 1, 0),
]

TILES_LIVRES = (0, 3, 4)
TILES_POWERUP = (3, 4)
TILE_DESTRUTIVEL = 1
TILE_PAREDE_FIXA = 2
ALPHA = 0.1
GAMMA = 0.9
EPSILON_TREINO = 0.05


class BombaVirtual:
    def __init__(self, x, y, nivel):
        self.x = x
        self.y = y
        self.nivel = nivel
        self.explodida = False


def dentro_mapa(x, y, mapa):
    return 0 <= y < len(mapa) and 0 <= x < len(mapa[0])


def posicao_livre(x, y, mapa, bombas):
    if not dentro_mapa(x, y, mapa):
        return False

    if mapa[y][x] not in TILES_LIVRES:
        return False

    for bomba in bombas:
        if not getattr(bomba, "explodida", False) and bomba.x == x and bomba.y == y:
            return False

    return True


def posicao_livre_para_fuga(x, y, mapa, bombas, origem_x, origem_y):
    """
    Usada somente na simulação de fuga após plantar bomba.

    A origem é liberada porque representa o jogador saindo de cima
    da bomba que acabou de plantar. Nas outras posições, bombas continuam
    bloqueando normalmente.
    """
    if not dentro_mapa(x, y, mapa):
        return False

    if mapa[y][x] not in TILES_LIVRES:
        return False

    if (x, y) == (origem_x, origem_y):
        return True

    for bomba in bombas:
        if not getattr(bomba, "explodida", False) and bomba.x == x and bomba.y == y:
            return False

    return True

def caminho_bloqueado(x1, y1, x2, y2, mapa):
    if x1 == x2:
        passo = 1 if y2 > y1 else -1
        for y in range(y1 + passo, y2, passo):
            if mapa[y][x1] in (TILE_DESTRUTIVEL, TILE_PAREDE_FIXA):
                return True

    if y1 == y2:
        passo = 1 if x2 > x1 else -1
        for x in range(x1 + passo, x2, passo):
            if mapa[y1][x] in (TILE_DESTRUTIVEL, TILE_PAREDE_FIXA):
                return True

    return False


def caminho_livre_entre(x1, y1, x2, y2, mapa):
    if x1 != x2 and y1 != y2:
        return False

    return not caminho_bloqueado(x1, y1, x2, y2, mapa)


def posicao_no_raio_bomba(x, y, bomba, mapa):
    alcance = 1 + (getattr(bomba, "nivel", 1) - 1) * 2

    if x == bomba.x and y == bomba.y:
        return True

    if y == bomba.y and abs(x - bomba.x) <= alcance:
        return not caminho_bloqueado(bomba.x, bomba.y, x, y, mapa)

    if x == bomba.x and abs(y - bomba.y) <= alcance:
        return not caminho_bloqueado(bomba.x, bomba.y, x, y, mapa)

    return False


def posicao_em_perigo(x, y, bombas, mapa):
    if not dentro_mapa(x, y, mapa):
        return True

    for bomba in bombas:
        if getattr(bomba, "explodida", False):
            if getattr(bomba, "tempo_fogo", 0) > 0 and (x, y) in getattr(bomba, "fogo", []):
                return True
            continue

        if posicao_no_raio_bomba(x, y, bomba, mapa):
            return True

    return False


def posicao_em_fogo(x, y, bombas):
    for bomba in bombas:
        if getattr(bomba, "explodida", False):
            if getattr(bomba, "tempo_fogo", 0) > 0 and (x, y) in getattr(bomba, "fogo", []):
                return True
    return False


def posicao_segura(x, y, bombas, mapa):
    return posicao_livre(x, y, mapa, bombas) and not posicao_em_perigo(x, y, bombas, mapa)


def bombas_com_virtual(player, bombas):
    bomba_virtual = BombaVirtual(
        player.grid_x,
        player.grid_y,
        getattr(player, "bomba_nivel", 1),
    )
    return list(bombas) + [bomba_virtual]


def bomba_na_posicao(x, y, bombas):
    return any(
        bomba.x == x and bomba.y == y and not getattr(bomba, "explodida", False)
        for bomba in bombas
    )


def bomba_pertence_ao_jogador(bomba, player, numero_jogador=None):
    for atributo in ("dono", "player", "jogador", "owner"):
        if getattr(bomba, atributo, None) is player:
            return True

    id_bomba = getattr(bomba, "id_jogador", None)
    if numero_jogador is not None and id_bomba == numero_jogador:
        return True

    return False


def bombas_ativas_do_jogador(player, bombas=None, numero_jogador=None):
    ativas = []

    for bomba in bombas or []:
        if getattr(bomba, "explodida", False):
            continue
        if bomba_pertence_ao_jogador(bomba, player, numero_jogador):
            ativas.append(bomba)

    for bomba in getattr(player, "bombas", []):
        if getattr(bomba, "explodida", False):
            continue
        if bomba not in ativas:
            ativas.append(bomba)

    return ativas


def limite_bombas_do_jogador(player):
    for atributo in ("max_bombas", "bombas_max", "limite_bombas", "bombas_disponiveis"):
        valor = getattr(player, atributo, None)
        if isinstance(valor, int):
            return max(1, valor)

    return 1


def pode_colocar_mais_bomba(player, bombas, numero_jogador=None):
    return len(bombas_ativas_do_jogador(player, bombas, numero_jogador)) < limite_bombas_do_jogador(player)


def fora_do_raio_das_bombas(x, y, bombas, mapa):
    for bomba in bombas:
        if posicao_no_raio_bomba(x, y, bomba, mapa):
            return False
    return True


def parede_destrutivel_perto(player, mapa):
    for _, dx, dy in DIRECOES:
        nx = player.grid_x + dx
        ny = player.grid_y + dy

        if dentro_mapa(nx, ny, mapa) and mapa[ny][nx] == TILE_DESTRUTIVEL:
            return True

    return False


def adjacente_a_parede_destrutivel(x, y, mapa):
    for _, dx, dy in DIRECOES:
        nx = x + dx
        ny = y + dy

        if dentro_mapa(nx, ny, mapa) and mapa[ny][nx] == TILE_DESTRUTIVEL:
            return True

    return False


def contar_saidas_seguras(x, y, mapa, bombas):
    saidas = 0
    for _, dx, dy in DIRECOES:
        if posicao_segura(x + dx, y + dy, bombas, mapa):
            saidas += 1
    return saidas


def existe_bomba_ameacando_posicao(x, y, bombas, mapa):
    for bomba in bombas:
        if getattr(bomba, "explodida", False):
            continue
        if posicao_no_raio_bomba(x, y, bomba, mapa):
            return True
    return False


def distancia_ate_bomba_mais_proxima(x, y, bombas):
    distancias = [
        abs(x - bomba.x) + abs(y - bomba.y)
        for bomba in bombas
        if not getattr(bomba, "explodida", False)
    ]
    return min(distancias) if distancias else 999


def pontuar_posicao_defensiva(x, y, bombas, mapa):
    return contar_saidas_seguras(x, y, mapa, bombas) * 10 + distancia_ate_bomba_mais_proxima(x, y, bombas)


def primeira_acao_bfs(player, mapa, bombas, objetivo):
    fila = deque()
    visitados = set()

    fila.append((player.grid_x, player.grid_y, []))
    visitados.add((player.grid_x, player.grid_y))

    while fila:
        x, y, caminho = fila.popleft()

        if caminho and objetivo(x, y):
            return caminho[0]

        for acao, dx, dy in DIRECOES:
            nx = x + dx
            ny = y + dy

            if (nx, ny) in visitados:
                continue

            if not posicao_segura(nx, ny, bombas, mapa):
                continue

            visitados.add((nx, ny))
            fila.append((nx, ny, caminho + [acao]))

    return None


def bfs_fuga_segura(player, mapa, bombas):
    candidatos = []
    fila = deque()
    visitados = set()

    fila.append((player.grid_x, player.grid_y, []))
    visitados.add((player.grid_x, player.grid_y))

    while fila:
        x, y, caminho = fila.popleft()

        if caminho and posicao_segura(x, y, bombas, mapa):
            score = pontuar_posicao_defensiva(x, y, bombas, mapa)
            candidatos.append((len(caminho), -score, caminho[0]))

        for acao, dx, dy in DIRECOES:
            nx = x + dx
            ny = y + dy

            if (nx, ny) in visitados:
                continue

            if not posicao_livre(nx, ny, mapa, bombas):
                continue

            # Durante a fuga pode ser necessario atravessar o raio da bomba
            # antes da explosao; o destino final ainda precisa ser seguro.
            if posicao_em_fogo(nx, ny, bombas):
                continue

            visitados.add((nx, ny))
            fila.append((nx, ny, caminho + [acao]))

    if candidatos:
        candidatos.sort()
        return candidatos[0][2]

    return escolher_movimento_defensivo(player, mapa, bombas)


def fugir_da_bomba(player, mapa, bombas):
    return bfs_fuga_segura(player, mapa, bombas)


def powerup_perto_ou_acessivel(player, mapa, bombas):
    return primeira_acao_bfs(
        player,
        mapa,
        bombas,
        lambda x, y: mapa[y][x] in TILES_POWERUP,
    )


def buscar_parede_destrutivel(player, mapa, bombas):
    fila = deque()
    visitados = set()
    melhores = []

    fila.append((player.grid_x, player.grid_y, []))
    visitados.add((player.grid_x, player.grid_y))

    while fila:
        x, y, caminho = fila.popleft()

        if caminho and adjacente_a_parede_destrutivel(x, y, mapa):
            fantasma = type("PlayerFantasma", (), {})()
            fantasma.grid_x = x
            fantasma.grid_y = y
            fantasma.bomba_nivel = getattr(player, "bomba_nivel", 1)
            fantasma.max_bombas = getattr(player, "max_bombas", 1)
            fantasma.bombas = getattr(player, "bombas", [])

            rota_farm = existe_rota_fuga_apos_bomba_farm(fantasma, mapa, bombas)
            score = contar_saidas_seguras(x, y, mapa, bombas)
            if rota_farm:
                score += 20

            melhores.append((len(caminho), -score, caminho[0]))

        for acao, dx, dy in DIRECOES:
            nx = x + dx
            ny = y + dy

            if (nx, ny) in visitados:
                continue

            if not posicao_segura(nx, ny, bombas, mapa):
                continue

            visitados.add((nx, ny))
            fila.append((nx, ny, caminho + [acao]))

    if not melhores:
        return None

    melhores.sort()
    return melhores[0][2]


def buscar_posicao_melhor(player, mapa, bombas):
    """Busca posição adjacente com mais espaço quando parede perto mas não pode plantar bomba."""
    opcoes = []

    for acao, dx, dy in DIRECOES:
        nx = player.grid_x + dx
        ny = player.grid_y + dy

        if not posicao_segura(nx, ny, bombas, mapa):
            continue

        saidas = contar_saidas_seguras(nx, ny, mapa, bombas)
        score = 20 * saidas + distancia_ate_bomba_mais_proxima(nx, ny, bombas)

        if adjacente_a_parede_destrutivel(nx, ny, mapa):
            score += 10

        opcoes.append((score, acao))

    if opcoes:
        opcoes.sort(reverse=True)
        return opcoes[0][1]

    return None

    
def rota_fuga_farm(player, mapa, bombas):
    """
    Simula plantar uma bomba na posição atual e procura uma rota real
    para fora do raio da bomba nova.

    Retorna:
    {
        "existe": bool,
        "primeira_acao": str | None,
        "destino": tuple | None,
        "motivo": str
    }
    """
    bombas_futuras = bombas_com_virtual(player, bombas)
    bomba_nova = bombas_futuras[-1]

    origem_x = player.grid_x
    origem_y = player.grid_y

    fila = deque()
    visitados = set()

    fila.append((origem_x, origem_y, []))
    visitados.add((origem_x, origem_y))

    encontrou_posicao_livre = False
    encontrou_fora_raio = False

    while fila:
        x, y, caminho = fila.popleft()

        # Destino válido: saiu da origem, está livre, fora da bomba nova
        # e não está ameaçado por outras bombas já existentes.
        if caminho:
            if posicao_livre(x, y, mapa, bombas_futuras):
                encontrou_posicao_livre = True

                fora_bomba_nova = not posicao_no_raio_bomba(x, y, bomba_nova, mapa)
                fora_outras_bombas = not existe_bomba_ameacando_posicao(x, y, bombas, mapa)
                sem_fogo = not posicao_em_fogo(x, y, bombas)

                if fora_bomba_nova:
                    encontrou_fora_raio = True

                if fora_bomba_nova and fora_outras_bombas and sem_fogo:
                    return {
                        "existe": True,
                        "primeira_acao": caminho[0],
                        "destino": (x, y),
                        "motivo": "ok",
                    }

        for acao, dx, dy in DIRECOES:
            nx = x + dx
            ny = y + dy

            if (nx, ny) in visitados:
                continue

            # Aqui está o ponto importante:
            # permite sair da origem mesmo com a bomba virtual ali.
            if not posicao_livre_para_fuga(nx, ny, mapa, bombas_futuras, origem_x, origem_y):
                continue

            if posicao_em_fogo(nx, ny, bombas):
                continue

            visitados.add((nx, ny))
            fila.append((nx, ny, caminho + [acao]))

    if not encontrou_posicao_livre:
        motivo = "sem_posicao_livre"
    elif not encontrou_fora_raio:
        motivo = "sem_destino_fora_do_raio"
    else:
        motivo = "bloqueado_por_outra_bomba"

    return {
        "existe": False,
        "primeira_acao": None,
        "destino": None,
        "motivo": motivo,
    }

def obter_primeiro_passo_rota_fuga_farm(player, mapa, bombas):
    return rota_fuga_farm(player, mapa, bombas)["primeira_acao"]

def existe_rota_fuga_apos_bomba_farm(player, mapa, bombas):
    bombas_futuras = bombas_com_virtual(player, bombas)
    bomba_nova = bombas_futuras[-1]
    origem_x, origem_y = player.grid_x, player.grid_y

    fila = deque()
    visitados = set()

    fila.append((player.grid_x, player.grid_y, 0))
    visitados.add((player.grid_x, player.grid_y))

    while fila:
        x, y, passos = fila.popleft()

        if passos > 0 and posicao_livre(x, y, mapa, bombas_futuras):
            fora_bomba_nova = not posicao_no_raio_bomba(x, y, bomba_nova, mapa)
            fora_outras_bombas = not existe_bomba_ameacando_posicao(x, y, bombas, mapa)

            if fora_bomba_nova and fora_outras_bombas and not posicao_em_fogo(x, y, bombas):
                saidas = contar_saidas_seguras(x, y, mapa, bombas_futuras)

                if saidas >= 1:
                    return True

        for _, dx, dy in DIRECOES:
            nx = x + dx
            ny = y + dy

            if (nx, ny) in visitados:
                continue

            if not posicao_livre_para_fuga(nx, ny, mapa, bombas_futuras, origem_x, origem_y):
                continue

            if posicao_em_fogo(nx, ny, bombas):
                continue

            visitados.add((nx, ny))
            fila.append((nx, ny, passos + 1))

    return False


def pode_plantar_bomba_farm_seguro(player, mapa, bombas, numero_jogador=None):
    if bomba_na_posicao(player.grid_x, player.grid_y, bombas):
        return False

    if not pode_colocar_mais_bomba(player, bombas, numero_jogador):
        return False

    if not parede_destrutivel_perto(player, mapa):
        return False

    rota = rota_fuga_farm(player, mapa, bombas)
    return rota["existe"]

def existe_rota_fuga_apos_bomba(player, mapa, bombas):
    """
    Rota de fuga mais conservadora, usada para ATAQUE.
    Para farm usamos rota_fuga_farm(), que é mais permissiva.
    """
    bombas_futuras = bombas_com_virtual(player, bombas)
    bomba_nova = bombas_futuras[-1]

    origem_x = player.grid_x
    origem_y = player.grid_y

    fila = deque()
    visitados = set()

    fila.append((origem_x, origem_y, []))
    visitados.add((origem_x, origem_y))

    fallback_uma_saida = False

    while fila:
        x, y, caminho = fila.popleft()

        if caminho:
            if posicao_livre(x, y, mapa, bombas_futuras):
                fora_bomba_nova = not posicao_no_raio_bomba(x, y, bomba_nova, mapa)
                fora_outras_bombas = not existe_bomba_ameacando_posicao(x, y, bombas, mapa)
                sem_fogo = not posicao_em_fogo(x, y, bombas)

                if fora_bomba_nova and fora_outras_bombas and sem_fogo:
                    saidas = contar_saidas_seguras(x, y, mapa, bombas_futuras)

                    if saidas >= 2:
                        return True

                    if saidas == 1:
                        fallback_uma_saida = True

        for acao, dx, dy in DIRECOES:
            nx = x + dx
            ny = y + dy

            if (nx, ny) in visitados:
                continue

            if not posicao_livre_para_fuga(nx, ny, mapa, bombas_futuras, origem_x, origem_y):
                continue

            if posicao_em_fogo(nx, ny, bombas):
                continue

            visitados.add((nx, ny))
            fila.append((nx, ny, caminho + [acao]))

    return fallback_uma_saida    

def pode_plantar_bomba_ataque_seguro(player, mapa, bombas, inimigos, numero_jogador=None):
    if posicao_em_perigo(player.grid_x, player.grid_y, bombas, mapa):
        return False

    if bomba_na_posicao(player.grid_x, player.grid_y, bombas):
        return False

    if contar_saidas_seguras(player.grid_x, player.grid_y, mapa, bombas) < 2:
        return False

    if not (inimigo_perto(player, inimigos) or inimigo_alinhado(player, inimigos, mapa)):
        return False

    if not pode_colocar_mais_bomba(player, bombas, numero_jogador):
        return False

    return existe_rota_fuga_apos_bomba(player, mapa, bombas)


def pode_plantar_bomba_seguro(player, mapa, bombas, numero_jogador=None):
    return pode_plantar_bomba_farm_seguro(player, mapa, bombas, numero_jogador)


def inimigos_ativos(player, inimigos):
    return [
        inimigo for inimigo in inimigos or []
        if inimigo is not player and getattr(inimigo, "ativo", True)
    ]


def distancia_manhattan(a, b):
    return abs(a.grid_x - b.grid_x) + abs(a.grid_y - b.grid_y)


def inimigo_perto(player, inimigos, distancia_maxima=3):
    for inimigo in inimigos_ativos(player, inimigos):
        if distancia_manhattan(player, inimigo) <= distancia_maxima:
            return True

    return False


def inimigo_alinhado(player, inimigos, mapa, distancia_maxima=6):
    for inimigo in inimigos_ativos(player, inimigos):
        mesma_linha = player.grid_y == inimigo.grid_y
        mesma_coluna = player.grid_x == inimigo.grid_x

        if not (mesma_linha or mesma_coluna):
            continue

        if distancia_manhattan(player, inimigo) > distancia_maxima:
            continue

        if caminho_livre_entre(player.grid_x, player.grid_y, inimigo.grid_x, inimigo.grid_y, mapa):
            return True

    return False


def pode_atacar(player, mapa, bombas, inimigos, numero_jogador=None):
    return pode_plantar_bomba_ataque_seguro(player, mapa, bombas, inimigos, numero_jogador)


def escolher_movimento_defensivo(player, mapa, bombas):
    opcoes = []

    for acao, dx, dy in DIRECOES:
        nx = player.grid_x + dx
        ny = player.grid_y + dy

        if not posicao_livre(nx, ny, mapa, bombas):
            continue

        score = pontuar_posicao_defensiva(nx, ny, bombas, mapa)
        if posicao_em_perigo(nx, ny, bombas, mapa):
            score -= 1000

        opcoes.append((score, acao))

    if not opcoes:
        return "parado"

    opcoes.sort(reverse=True)
    melhor_score = opcoes[0][0]
    melhores = [acao for score, acao in opcoes if score == melhor_score]
    return random.choice(melhores)


def escolher_movimento_seguro(player, mapa, bombas, memoria=None):
    opcoes = []
    ultima_acao = memoria.get("ultima_acao") if memoria else None

    for acao, dx, dy in DIRECOES:
        nx = player.grid_x + dx
        ny = player.grid_y + dy

        if not posicao_segura(nx, ny, bombas, mapa):
            continue

        score = pontuar_posicao_defensiva(nx, ny, bombas, mapa)
        if acao == acao_oposta(ultima_acao):
            score -= 4
        if contar_saidas_seguras(nx, ny, mapa, bombas) <= 1:
            score -= 8

        opcoes.append((score, acao))

    if not opcoes:
        return "parado"

    opcoes.sort(reverse=True)
    melhor_score = opcoes[0][0]
    melhores = [acao for score, acao in opcoes if score == melhor_score]
    return random.choice(melhores)


def tem_movimento_seguro(player, mapa, bombas):
    for _, dx, dy in DIRECOES:
        if posicao_segura(player.grid_x + dx, player.grid_y + dy, bombas, mapa):
            return True
    return False


def acao_oposta(acao):
    opostas = {
        "cima": "baixo",
        "baixo": "cima",
        "esquerda": "direita",
        "direita": "esquerda",
    }
    return opostas.get(acao)


def parece_lista_de_bombas(objetos):
    if not objetos:
        return False

    return all(
        hasattr(item, "x")
        and hasattr(item, "y")
        and (
            hasattr(item, "explodida")
            or hasattr(item, "fogo")
            or hasattr(item, "tempo_fogo")
            or hasattr(item, "dono")
        )
        for item in objetos
    )


def extrair_bombas(args, kwargs):
    jogadores = args[0] if len(args) > 0 else kwargs.get("jogadores")
    bombas = args[1] if len(args) > 1 else kwargs.get("bombas", [])

    # Compatibilidade com chamadas do tipo decidir_acao(player, mapa, bombas).
    if parece_lista_de_bombas(jogadores):
        bombas = jogadores

    return bombas


def extrair_contexto(args, kwargs):
    inimigos = args[0] if len(args) > 0 else kwargs.get("inimigos")
    bombas = args[1] if len(args) > 1 else kwargs.get("bombas", [])

    # Compatibilidade com chamadas do tipo decidir_acao(player, mapa, bombas).
    if parece_lista_de_bombas(inimigos):
        bombas = inimigos
        inimigos = []

    return inimigos or [], bombas


def extrair_pontos(args, kwargs):
    if len(args) > 3 and isinstance(args[3], list):
        return args[3]
    return kwargs.get("pontos", [])


def registrar_memoria(memoria, acao):
    if acao == memoria.get("ultima_acao"):
        memoria["repeticoes"] = memoria.get("repeticoes", 0) + 1
    else:
        memoria["repeticoes"] = 0

    memoria["ultima_acao"] = acao
    return acao


def registrar_posicao(memoria, player):
    posicoes = memoria.setdefault("posicoes_recentes", [])
    posicoes.append((player.grid_x, player.grid_y))

    if len(posicoes) > 6:
        del posicoes[:-6]


def esta_em_loop(memoria, player):
    posicoes = memoria.get("posicoes_recentes", [])

    if len(posicoes) < 4:
        return False

    # Detectar loop de 2 posições: a-b-a-b
    if len(posicoes) >= 4 and posicoes[-1] == posicoes[-3] and posicoes[-2] == posicoes[-4]:
        return True

    # Detectar loop de 6 posições: a-b-a-b-a-b
    if len(posicoes) >= 6:
        a = posicoes[-1]
        b = posicoes[-2]

        if a == b:
            return False

        return posicoes[-3] == a and posicoes[-4] == b and posicoes[-5] == a and posicoes[-6] == b

    return False


def quebrar_loop(player, mapa, bombas, memoria):
    opcoes = []
    oposta = acao_oposta(memoria.get("ultima_acao"))
    posicoes_recentes = memoria.get("posicoes_recentes", [])

    for acao, dx, dy in DIRECOES:
        if acao == oposta:
            continue

        nx = player.grid_x + dx
        ny = player.grid_y + dy

        if not posicao_segura(nx, ny, bombas, mapa):
            continue

        saidas = contar_saidas_seguras(nx, ny, mapa, bombas)
        score = 20 * saidas + distancia_ate_bomba_mais_proxima(nx, ny, bombas)

        if adjacente_a_parede_destrutivel(nx, ny, mapa):
            score += 15

        if saidas <= 1:
            score -= 20  # Penalizar corredores

        if (nx, ny) in posicoes_recentes:
            score -= 50  # Evitar posições recentes

        opcoes.append((score, acao))

    if opcoes:
        opcoes.sort(reverse=True)
        return opcoes[0][1]

    return escolher_movimento_seguro(player, mapa, bombas, memoria)


def motivo_bloqueio_farm(player, mapa, bombas, numero_jogador=None):
    if bomba_na_posicao(player.grid_x, player.grid_y, bombas):
        return "bomba_na_posicao"

    if not pode_colocar_mais_bomba(player, bombas, numero_jogador):
        return "limite_bombas"

    if not parede_destrutivel_perto(player, mapa):
        return "sem_parede_perto"

    rota = rota_fuga_farm(player, mapa, bombas)
    if not rota["existe"]:
        return rota["motivo"]

    return "ok"

def obter_estado_q(player, mapa, bombas, inimigos, numero_jogador=None):
    perigo_atual = posicao_em_perigo(player.grid_x, player.grid_y, bombas, mapa)
    powerup_acessivel = powerup_perto_ou_acessivel(player, mapa, bombas) is not None
    parede_perto = parede_destrutivel_perto(player, mapa)
    perto = inimigo_perto(player, inimigos)
    alinhado = inimigo_alinhado(player, inimigos, mapa)
    pode_bomba_segura = pode_plantar_bomba_farm_seguro(player, mapa, bombas, numero_jogador)
    pode_atacar_seguro = pode_atacar(player, mapa, bombas, inimigos, numero_jogador)
    preso_ou_sem_rota = not tem_movimento_seguro(player, mapa, bombas)

    return (
        perigo_atual,
        powerup_acessivel,
        parede_perto,
        perto,
        alinhado,
        pode_bomba_segura,
        pode_atacar_seguro,
        preso_ou_sem_rota,
    )


def bomba_perigosa_propria(player, mapa, bombas, numero_jogador):
    minhas_bombas = bombas_ativas_do_jogador(player, bombas, numero_jogador)
    return not fora_do_raio_das_bombas(player.grid_x, player.grid_y, minhas_bombas, mapa)


def acoes_validas_q(player, mapa, bombas, inimigos, numero_jogador):
    validas = []
    powerup = powerup_perto_ou_acessivel(player, mapa, bombas)
    pode_farmar = pode_plantar_bomba_farm_seguro(player, mapa, bombas, numero_jogador)
    caminho_parede = buscar_parede_destrutivel(player, mapa, bombas)
    pode_atacar_seguro = pode_atacar(player, mapa, bombas, inimigos, numero_jogador)
    pode_reposicionar = tem_movimento_seguro(player, mapa, bombas)
    perigo = posicao_em_perigo(player.grid_x, player.grid_y, bombas, mapa)

    if perigo or bomba_perigosa_propria(player, mapa, bombas, numero_jogador):
        validas.append("fugir")

    if powerup:
        validas.append("pegar_powerup")

    if pode_atacar_seguro:
        validas.append("atacar")

    if pode_farmar or caminho_parede:
        validas.append("farmar")

    tem_acao_util = powerup or pode_atacar_seguro or pode_farmar or caminho_parede

    if pode_reposicionar and "farmar" not in validas:
        validas.append("reposicionar")

    if (
        posicao_segura(player.grid_x, player.grid_y, bombas, mapa)
        and not powerup
        and not pode_atacar_seguro
        and not pode_farmar
        and not caminho_parede
        and not tem_acao_util
    ):
        validas.append("esperar")

    return validas or ["reposicionar"]


def calcular_recompensa(memoria, player, mapa, bombas, pontos, numero_jogador):
    indice = numero_jogador - 1
    pontos_atuais = pontos[indice] if indice < len(pontos) else memoria.get("pontos_anteriores", 0)
    pontos_anteriores = memoria.get("pontos_anteriores", pontos_atuais)
    delta_pontos = pontos_atuais - pontos_anteriores

    recompensa = 1

    if delta_pontos >= 10000:
        recompensa += 100
    elif delta_pontos >= 1000:
        recompensa += 60
    elif delta_pontos >= 200:
        recompensa += 10
    elif delta_pontos >= 100:
        recompensa += 5

    if memoria.get("perigo_anterior") and not posicao_em_perigo(player.grid_x, player.grid_y, bombas, mapa):
        recompensa += 20

    if not memoria.get("perigo_anterior") and posicao_em_perigo(player.grid_x, player.grid_y, bombas, mapa):
        recompensa -= 10

    if memoria.get("ultima_acao") == "parado":
        memoria["repeticoes_parado"] = memoria.get("repeticoes_parado", 0) + 1
    else:
        memoria["repeticoes_parado"] = 0

    if memoria.get("repeticoes_parado", 0) >= 3:
        recompensa -= 5

    if not getattr(player, "ativo", True):
        recompensa -= 50

    return recompensa


def executar_acao_macro(acao_macro, player, mapa, bombas, inimigos, memoria, numero_jogador):
    if acao_macro == "fugir":
        return fugir_da_bomba(player, mapa, bombas)

    if acao_macro == "pegar_powerup":
        return powerup_perto_ou_acessivel(player, mapa, bombas) or executar_acao_macro(
            "farmar", player, mapa, bombas, inimigos, memoria, numero_jogador
        )

    if acao_macro == "atacar":
        if pode_atacar(player, mapa, bombas, inimigos, numero_jogador):
            memoria["fugindo"] = True
            return "bomba"
        return executar_acao_macro("farmar", player, mapa, bombas, inimigos, memoria, numero_jogador)

    if acao_macro == "farmar":
        if pode_plantar_bomba_farm_seguro(player, mapa, bombas, numero_jogador):
            memoria["fugindo"] = True
            return "bomba"
        return buscar_parede_destrutivel(player, mapa, bombas) or escolher_movimento_seguro(player, mapa, bombas, memoria)

    if acao_macro == "reposicionar":
        return escolher_movimento_seguro(player, mapa, bombas, memoria)

    if acao_macro == "esperar":
        if (
            posicao_segura(player.grid_x, player.grid_y, bombas, mapa)
            and not powerup_perto_ou_acessivel(player, mapa, bombas)
            and not pode_atacar(player, mapa, bombas, inimigos, numero_jogador)
            and not pode_plantar_bomba_farm_seguro(player, mapa, bombas, numero_jogador)
            and not buscar_parede_destrutivel(player, mapa, bombas)
        ):
            return "parado"
        return fugir_da_bomba(player, mapa, bombas)

    return escolher_movimento_seguro(player, mapa, bombas, memoria)


def registrar_decisao_q(memoria, estado_atual, acao_macro):
    memoria["estado_anterior"] = estado_atual
    memoria["acao_anterior"] = acao_macro


def debug_decisao(debug, numero_jogador, estado_atual, validas, acao_macro, acao):
    if debug:
        print(f"J{numero_jogador} estado={estado_atual} validas={validas} q={acao_macro} final={acao}")


def debug_farm(debug, numero_jogador, player, mapa, bombas, pode_farmar, motivo, rota_fuga, loop, acao):
    if debug:
        saidas = contar_saidas_seguras(player.grid_x, player.grid_y, mapa, bombas)
        print(
            f"J{numero_jogador} farm={pode_farmar} motivo={motivo} "
            f"saidas={saidas} rota_fuga_farm={rota_fuga} loop={loop} final={acao}"
        )


def criar_decisor_bfs(numero_jogador):
    caminho_q_table = os.path.join("data", f"q_table_jogador{numero_jogador}.json")
    q_table = carregar_q_table(caminho_q_table)

    memoria = {
        "ultima_acao": None,
        "repeticoes": 0,
        "fugindo": False,
        "estado_anterior": None,
        "acao_anterior": None,
        "pontos_anteriores": 0,
        "kills_anteriores": 0,
        "tempo_vivo_anterior": 0,
        "repeticoes_parado": 0,
        "perigo_anterior": False,
        "posicoes_recentes": [],
    }

    def decidir_acao(player, mapa, *args, **kwargs):
        inimigos, bombas = extrair_contexto(args, kwargs)
        pontos = extrair_pontos(args, kwargs)

        minhas_bombas = bombas_ativas_do_jogador(player, bombas, numero_jogador)
        estado_atual = obter_estado_q(player, mapa, bombas, inimigos, numero_jogador)
        debug = os.getenv("DEBUG_IA") == "1"

        registrar_posicao(memoria, player)
        loop_detectado = esta_em_loop(memoria, player)

        # Atualiza Q-table
        if memoria["estado_anterior"] is not None and memoria["acao_anterior"] is not None:
            recompensa = calcular_recompensa(
                memoria, player, mapa, bombas, pontos, numero_jogador
            )

            atualizar_q_table(
                q_table,
                memoria["estado_anterior"],
                memoria["acao_anterior"],
                recompensa,
                estado_atual,
                ALPHA,
                GAMMA,
            )

            salvar_q_table(q_table, caminho_q_table)

        # PRIORIDADE 1: PERIGO
        if posicao_em_perigo(player.grid_x, player.grid_y, bombas, mapa):
            memoria["fugindo"] = True
            return fugir_da_bomba(player, mapa, bombas)

        # PRIORIDADE 2: POWERUP
        acao_powerup = powerup_perto_ou_acessivel(player, mapa, bombas)
        if acao_powerup:
            return acao_powerup

        # PRIORIDADE 3: FARM
        if pode_plantar_bomba_farm_seguro(player, mapa, bombas, numero_jogador):
            memoria["fugindo"] = True
            return "bomba"

        acao_parede = buscar_parede_destrutivel(player, mapa, bombas)
        if acao_parede:
            return acao_parede

        # Q-LEARNING
        epsilon = float(os.getenv("Q_EPSILON", str(EPSILON_TREINO)))

        validas = acoes_validas_q(
            player, mapa, bombas, inimigos, numero_jogador
        )

        acao_macro = escolher_acao_q(
            q_table,
            estado_atual,
            epsilon,
            validas
        )

        acao = executar_acao_macro(
            acao_macro,
            player,
            mapa,
            bombas,
            inimigos,
            memoria,
            numero_jogador
        )

        if acao is None:
            acao = escolher_movimento_seguro(player, mapa, bombas, memoria)

        return registrar_memoria(memoria, acao)

    return decidir_acao