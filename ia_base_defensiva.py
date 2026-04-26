import atexit
import json
import os
import random
from collections import deque
from types import SimpleNamespace


ACOES = ["cima", "baixo", "esquerda", "direita", "bomba", "parado"]
MOVIMENTOS = {
    "cima": (0, -1),
    "baixo": (0, 1),
    "esquerda": (-1, 0),
    "direita": (1, 0),
}
TILES_LIVRES = {0, 3, 4}
MARGEM_SEGURANCA = 0.05


def dentro_mapa(mapa, x, y):
    return 0 <= y < len(mapa) and 0 <= x < len(mapa[0])


def tile_livre(mapa, x, y):
    return dentro_mapa(mapa, x, y) and mapa[y][x] in TILES_LIVRES


def bomba_ativa_em(bombas, x, y):
    return any(not b.explodida and b.x == x and b.y == y for b in bombas)


def alcance_bomba(nivel):
    return 1 + max(0, nivel - 1) * 2


def celulas_explosao_bomba(bomba, mapa):
    if bomba.explodida and getattr(bomba, "tempo_fogo", 0) > 0:
        return set(getattr(bomba, "fogo", []))

    celulas = {(bomba.x, bomba.y)}
    for dx, dy in MOVIMENTOS.values():
        for passo in range(1, alcance_bomba(getattr(bomba, "nivel", 1)) + 1):
            nx = bomba.x + dx * passo
            ny = bomba.y + dy * passo
            if not dentro_mapa(mapa, nx, ny):
                break
            if mapa[ny][nx] == 2:
                break
            celulas.add((nx, ny))
            if mapa[ny][nx] == 1:
                break
    return celulas


def mapear_perigo(mapa, bombas):
    perigo = {}
    bombas_pendentes = [b for b in bombas if not b.explodida]
    blast_cache = {id(b): celulas_explosao_bomba(b, mapa) for b in bombas_pendentes}
    tempos = {
        id(b): max(0.0, float(getattr(b, "tempo_explosao", 0.0)))
        for b in bombas_pendentes
    }

    for _ in range(len(bombas_pendentes)):
        alterou = False
        for bomba in bombas_pendentes:
            tempo_bomba = tempos[id(bomba)]
            for outra in bombas_pendentes:
                if outra is bomba:
                    continue
                if (outra.x, outra.y) in blast_cache[id(bomba)] and tempo_bomba < tempos[id(outra)]:
                    tempos[id(outra)] = tempo_bomba
                    alterou = True
        if not alterou:
            break

    for bomba in bombas:
        if bomba.explodida and getattr(bomba, "tempo_fogo", 0) > 0:
            for celula in getattr(bomba, "fogo", []):
                perigo[celula] = 0.0

    for bomba in bombas_pendentes:
        tempo_bomba = tempos[id(bomba)]
        for celula in blast_cache[id(bomba)]:
            if celula not in perigo or tempo_bomba < perigo[celula]:
                perigo[celula] = tempo_bomba

    return perigo


def celula_segura(perigo, posicao, tempo_chegada):
    tempo_perigo = perigo.get(posicao)
    if tempo_perigo is None:
        return True
    return tempo_perigo > tempo_chegada + MARGEM_SEGURANCA


def posicao_transitavel(mapa, bombas, inicio, x, y):
    if (x, y) == inicio:
        return True
    if not tile_livre(mapa, x, y):
        return False
    return not bomba_ativa_em(bombas, x, y)


def explorar_rotas(inicio, mapa, bombas, perigo, tempo_movimento, max_passos):
    fila = deque([inicio])
    pais = {inicio: (None, None)}
    tempos = {inicio: 0.0}
    passos = {inicio: 0}

    while fila:
        atual = fila.popleft()
        if passos[atual] >= max_passos:
            continue

        for acao, (dx, dy) in MOVIMENTOS.items():
            nx = atual[0] + dx
            ny = atual[1] + dy
            if not posicao_transitavel(mapa, bombas, inicio, nx, ny):
                continue

            chegada = tempos[atual] + tempo_movimento
            destino = (nx, ny)
            if not celula_segura(perigo, destino, chegada):
                continue

            if destino in tempos and chegada >= tempos[destino]:
                continue

            pais[destino] = (atual, acao)
            tempos[destino] = chegada
            passos[destino] = passos[atual] + 1
            fila.append(destino)

    return pais, tempos


def reconstruir_rota(destino, pais):
    rota = []
    atual = destino
    while pais[atual][0] is not None:
        anterior, acao = pais[atual]
        rota.append(acao)
        atual = anterior
    rota.reverse()
    return rota


def contar_saidas_seguras(posicao, mapa, bombas, perigo, tempo_base, tempo_movimento):
    saidas = 0
    for dx, dy in MOVIMENTOS.values():
        nx = posicao[0] + dx
        ny = posicao[1] + dy
        if not posicao_transitavel(mapa, bombas, posicao, nx, ny):
            continue
        if celula_segura(perigo, (nx, ny), tempo_base + tempo_movimento):
            saidas += 1
    return saidas


def distancia_minima_bombas(posicao, bombas):
    distancias = [
        abs(b.x - posicao[0]) + abs(b.y - posicao[1])
        for b in bombas
        if not b.explodida
    ]
    return min(distancias) if distancias else 8


def distancia_minima_inimigos(player, posicao, jogadores):
    distancias = [
        abs(p.grid_x - posicao[0]) + abs(p.grid_y - posicao[1])
        for p in jogadores
        if p.ativo and p != player
    ]
    return min(distancias) if distancias else 8


def parede_quebravel_adjacente(mapa, x, y):
    return sum(
        1
        for dx, dy in MOVIMENTOS.values()
        if dentro_mapa(mapa, x + dx, y + dy) and mapa[y + dy][x + dx] == 1
    )


def inimigo_na_linha(player, jogadores, mapa, x, y, alcance):
    for dx, dy in MOVIMENTOS.values():
        for passo in range(1, alcance + 1):
            nx = x + dx * passo
            ny = y + dy * passo
            if not dentro_mapa(mapa, nx, ny):
                break
            if mapa[ny][nx] == 2:
                break
            for outro in jogadores:
                if outro.ativo and outro != player and outro.grid_x == nx and outro.grid_y == ny:
                    return True
            if mapa[ny][nx] == 1:
                break
    return False


def distancia_manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def contar_paredes_no_blast(blast, mapa):
    return sum(1 for x, y in blast if mapa[y][x] == 1)


def contar_paredes_quebraveis(mapa):
    return sum(1 for linha in mapa for tile in linha if tile == 1)


class ControladorDefensivo:
    def __init__(self, jogador_id, q_table_file, log_file):
        self.jogador_id = jogador_id
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.q_table_path = os.path.join(self.base_dir, q_table_file)
        self.log_path = os.path.join(self.base_dir, log_file)
        self.alpha = 0.25
        self.gamma = 0.92
        self.epsilon = 0.14
        self.epsilon_min = 0.03
        self.epsilon_decay = 0.9995
        self.versao_estado = 3
        self.q = self._carregar_q()
        self.estado_anterior = None
        self.acao_anterior = None
        self.contexto_anterior = None
        self.motivo_heuristica = None
        self.posicao_anterior = None
        self.recompensa_acumulada = 0.0
        self.contador = 0
        self.partida_iniciada = False
        self.log_salvo = False
        self.pontos_anteriores = None
        self.jogo_atual = self._proximo_jogo()
        self.tempo_partida = None
        self.tempo_restante_anterior = None
        self.tempo_vivo_acumulado = 0.0
        atexit.register(self.salvar_q)
        atexit.register(self.salvar_log_saida)

    def _carregar_q(self):
        if os.path.exists(self.q_table_path):
            with open(self.q_table_path, "r") as arquivo:
                return json.load(arquivo)
        return {}

    def _proximo_jogo(self):
        if not os.path.exists(self.log_path):
            return 1

        with open(self.log_path, "r") as arquivo:
            for linha in reversed(arquivo.readlines()):
                if linha.startswith("Jogo "):
                    return int(linha.split()[1].rstrip(":")) + 1
        return 1

    def salvar_q(self):
        with open(self.q_table_path, "w") as arquivo:
            json.dump(self.q, arquivo)

    def salvar_log_saida(self):
        if self.log_salvo or not self.partida_iniciada or self.contador == 0:
            return

        with open(self.log_path, "a") as arquivo:
            arquivo.write(
                f"Jogo {self.jogo_atual}: Recompensa acumulada {self.recompensa_acumulada:.2f}, "
                f"Acoes {self.contador}\n"
            )
        self.log_salvo = True

    def bucket_tempo_perigo(self, tempo_perigo):
        if tempo_perigo == 0.0:
            return 3
        if tempo_perigo is not None and tempo_perigo <= 0.7:
            return 2
        if tempo_perigo is not None and tempo_perigo <= 1.5:
            return 1
        return 0

    def bucket_distancia(self, distancia, max_bucket):
        if distancia is None:
            return max_bucket
        return min(int(distancia), max_bucket)

    def get_estado(self, player, mapa, jogadores, bombas, self_state, perigo, tempo_movimento):
        x, y = player.grid_x, player.grid_y
        tempo_perigo = perigo.get((x, y))
        powerup_proximo = any(
            dentro_mapa(mapa, x + dx, y + dy) and mapa[y + dy][x + dx] in (3, 4)
            for dx, dy in MOVIMENTOS.values()
        )
        menor_dist_inimigo = distancia_minima_inimigos(player, (x, y), jogadores)
        menor_dist_bomba = distancia_minima_bombas((x, y), bombas)
        bomba_viavel = self.score_ofensivo_bomba(
            player,
            (x, y),
            mapa,
            jogadores,
            bombas,
            perigo,
            self.tempo_restante_anterior if self.tempo_restante_anterior is not None else self.tempo_partida or 0.0,
            {"tempo_movimento": tempo_movimento, "tempo_explosao": 4.0},
            self_state,
        )
        inimigo_alinhado = inimigo_na_linha(player, jogadores, mapa, x, y, alcance_bomba(self_state["bomba_nivel"]))

        return (
            self.versao_estado,
            self.bucket_tempo_perigo(tempo_perigo),
            min(contar_saidas_seguras((x, y), mapa, bombas, perigo, 0.0, tempo_movimento), 4),
            self.bucket_distancia(menor_dist_bomba, 4),
            self.bucket_distancia(menor_dist_inimigo, 5),
            int(inimigo_alinhado),
            min(parede_quebravel_adjacente(mapa, x, y), 4),
            int(powerup_proximo),
            min(max(0, int(bomba_viavel // 25.0)), 4) if bomba_viavel != float("-inf") else 0,
            min(self_state["bombas_ativas"], 2),
            min(self_state["bomba_nivel"], 4),
        )

    def registrar_tempo_partida(self, tempo_restante, hud_info):
        tempo_partida_hud = float(hud_info.get("tempo_partida", tempo_restante))
        if self.tempo_partida is None:
            self.tempo_partida = max(tempo_partida_hud, float(tempo_restante), 1.0)
            return

        if self.tempo_restante_anterior is not None and tempo_restante > self.tempo_restante_anterior + 1.0:
            self.tempo_partida = max(tempo_partida_hud, float(tempo_restante), 1.0)
            self.tempo_vivo_acumulado = 0.0
            self.tempo_restante_anterior = None

    def bonus_tempo_vivo(self, tempo_restante, tempo_perigo):
        if self.tempo_restante_anterior is None:
            return 0.0

        delta_tempo = max(0.0, min(self.tempo_restante_anterior - tempo_restante, 1.0))
        self.tempo_vivo_acumulado += delta_tempo

        if self.tempo_partida is None or self.tempo_partida <= 0:
            progresso = 0.0
        else:
            progresso = min(1.0, self.tempo_vivo_acumulado / self.tempo_partida)

        bonus = delta_tempo * (45.0 + 75.0 * progresso)
        if tempo_perigo == 0.0:
            return 0.0
        if tempo_perigo is not None and tempo_perigo <= 0.7:
            return bonus * 0.25
        return bonus

    def extrair_contexto(self, player, mapa, jogadores, bombas, perigo, hud_info, self_state, tempo_restante):
        posicao = (player.grid_x, player.grid_y)
        bomb_score = self.score_ofensivo_bomba(
            player,
            posicao,
            mapa,
            jogadores,
            bombas,
            perigo,
            tempo_restante,
            hud_info,
            self_state,
        )
        if bomb_score == float("-inf"):
            bomb_score = 0.0

        return {
            "tempo_perigo_bucket": self.bucket_tempo_perigo(perigo.get(posicao)),
            "dist_inimigo": distancia_minima_inimigos(player, posicao, jogadores),
            "dist_bomba": distancia_minima_bombas(posicao, bombas),
            "saidas_seguras": contar_saidas_seguras(posicao, mapa, bombas, perigo, 0.0, hud_info["tempo_movimento"]),
            "bomb_score": bomb_score,
            "powerup_na_casa": int(mapa[player.grid_y][player.grid_x] in (3, 4)),
        }

    def get_recompensa(self, player, mapa, jogadores, bombas, pontos, perigo, tempo_movimento, tempo_restante, contexto_atual):
        idx = jogadores.index(player)
        x, y = player.grid_x, player.grid_y
        tempo_perigo = perigo.get((x, y))
        pontos_atuais = pontos[idx]
        delta_pontos = 0 if self.pontos_anteriores is None else pontos_atuais - self.pontos_anteriores

        recompensa = 1.5
        recompensa += self.bonus_tempo_vivo(tempo_restante, tempo_perigo)
        recompensa += delta_pontos / 100.0

        if tempo_perigo == 0.0:
            recompensa -= 60
        elif tempo_perigo is not None and tempo_perigo <= 0.7:
            recompensa -= 18
        elif tempo_perigo is None:
            recompensa += 6

        if mapa[y][x] in (3, 4):
            recompensa += 10

        recompensa += contar_saidas_seguras((x, y), mapa, bombas, perigo, 0.0, tempo_movimento) * 0.8

        if self.contexto_anterior is not None:
            delta_inimigo = self.contexto_anterior["dist_inimigo"] - contexto_atual["dist_inimigo"]
            recompensa += delta_inimigo * 4.0  # Aumentado para incentivar aproximação de inimigos

            delta_bomb_score = contexto_atual["bomb_score"] - self.contexto_anterior["bomb_score"]
            recompensa += max(0.0, delta_bomb_score) * 0.15  # Aumentado

            if self.acao_anterior == "bomba":
                recompensa += min(40.0, self.contexto_anterior["bomb_score"] * 0.3)  # Aumentado para incentivar plantar bombas

            if self.acao_anterior == "parado":
                if self.contexto_anterior["bomb_score"] >= 18.0:
                    recompensa -= 7
                if self.contexto_anterior["dist_inimigo"] <= 4:
                    recompensa -= 2.5

            if self.acao_anterior in MOVIMENTOS and contexto_atual["saidas_seguras"] > self.contexto_anterior["saidas_seguras"]:
                recompensa += 1.5

        return recompensa

    def score_posicao(self, player, posicao, mapa, jogadores, bombas, perigo, tempo_chegada, tempo_movimento):
        score = 0.0
        tempo_perigo = perigo.get(posicao)

        if tempo_perigo is None:
            score += 28
        else:
            score += max(0.0, tempo_perigo - tempo_chegada) * 6

        score += contar_saidas_seguras(posicao, mapa, bombas, perigo, tempo_chegada, tempo_movimento) * 7
        score += min(distancia_minima_bombas(posicao, bombas), 8) * 1.7
        distancia_inimigo = min(distancia_minima_inimigos(player, posicao, jogadores), 8)
        if distancia_inimigo <= 1:
            score -= 1.5
        elif distancia_inimigo <= 4:
            score += (5 - distancia_inimigo) * 2.5
        else:
            score += max(0, 8 - distancia_inimigo) * 0.4

        x, y = posicao
        if mapa[y][x] in (3, 4):
            score += 25

        return score

    def contar_refugios_livres(self, posicao, mapa, bombas, perigo, tempo_movimento):
        pais, tempos = explorar_rotas(
            posicao,
            mapa,
            bombas,
            perigo,
            tempo_movimento,
            len(mapa) * len(mapa[0]),
        )

        refugios = 0
        melhor_tempo = None
        for destino, tempo_chegada in tempos.items():
            if perigo.get(destino) is None:
                refugios += 1
                if melhor_tempo is None or tempo_chegada < melhor_tempo:
                    melhor_tempo = tempo_chegada

        return refugios, melhor_tempo

    def jogadores_com_player_virtual(self, jogadores, player_real, player_virtual):
        return [player_virtual if outro == player_real else outro for outro in jogadores]

    def score_ofensivo_bomba(self, player, posicao, mapa, jogadores, bombas, perigo, tempo_restante, hud_info, self_state):
        x, y = posicao
        alcance = alcance_bomba(self_state["bomba_nivel"])

        if self_state["bombas_ativas"] >= self_state["max_bombas"]:
            return float("-inf")
        if bomba_ativa_em(bombas, x, y):
            return float("-inf")
        if perigo.get((x, y)) is not None:
            return float("-inf")
        if tempo_restante < 15:
            return float("-inf")

        bomba_virtual = SimpleNamespace(
            x=x,
            y=y,
            nivel=self_state["bomba_nivel"],
            explodida=False,
            tempo_explosao=hud_info["tempo_explosao"],
            tempo_fogo=0,
            fogo=[],
        )
        bombas_simuladas = list(bombas) + [bomba_virtual]
        perigo_simulado = mapear_perigo(mapa, bombas_simuladas)

        refugios_proprios, melhor_tempo_refugio = self.contar_refugios_livres(
            (x, y),
            mapa,
            bombas_simuladas,
            perigo_simulado,
            hud_info["tempo_movimento"],
        )
        if refugios_proprios <= 0:
            return float("-inf")

        blast = celulas_explosao_bomba(bomba_virtual, mapa)
        paredes_atingidas = contar_paredes_no_blast(blast, mapa)
        score = paredes_atingidas * 28.0
        if melhor_tempo_refugio is not None and melhor_tempo_refugio <= 1.0:
            score += 4.0
        elif melhor_tempo_refugio is not None and melhor_tempo_refugio <= 2.0:
            score += 2.0

        score_inimigos = 0.0
        objetivo_inimigo = False
        player_virtual = SimpleNamespace(grid_x=x, grid_y=y, ativo=True)
        jogadores_virtual = self.jogadores_com_player_virtual(jogadores, player, player_virtual)
        for inimigo in jogadores_virtual:
            if not inimigo.ativo or inimigo == player:
                continue

            pos_inimigo = (inimigo.grid_x, inimigo.grid_y)
            dist = distancia_manhattan((x, y), pos_inimigo)
            if dist > alcance + 4:
                continue

            refugios_antes, _ = self.contar_refugios_livres(
                pos_inimigo,
                mapa,
                bombas,
                perigo,
                hud_info["tempo_movimento"],
            )
            refugios_depois, melhor_tempo = self.contar_refugios_livres(
                pos_inimigo,
                mapa,
                bombas_simuladas,
                perigo_simulado,
                hud_info["tempo_movimento"],
            )
            delta_refugios = refugios_antes - refugios_depois
            armadilha_forte = refugios_depois <= 2 and delta_refugios >= 2
            morte_quase_certa = pos_inimigo in blast and refugios_depois == 0

            if pos_inimigo in blast:
                if morte_quase_certa:
                    objetivo_inimigo = True
                    score_inimigos += 150.0
                elif armadilha_forte:
                    objetivo_inimigo = True
                    score_inimigos += 95.0
                elif refugios_depois <= 1 and delta_refugios >= 1:
                    objetivo_inimigo = True
                    score_inimigos += 60.0

                if morte_quase_certa:
                    score_inimigos += 140.0
                if melhor_tempo is not None and melhor_tempo > 1.5:
                    score_inimigos += 16.0
            elif dist <= 2 and armadilha_forte:
                objetivo_inimigo = True
                score_inimigos += delta_refugios * 18.0
            elif dist <= 1 and refugios_depois == 1 and delta_refugios >= 1:
                objetivo_inimigo = True
                score_inimigos += 30.0

        score += score_inimigos
        if paredes_atingidas == 0 and not objetivo_inimigo:
            return float("-inf")

        return score

    def encontrar_rota_fuga(self, player, mapa, jogadores, bombas, perigo, tempo_movimento):
        inicio = (player.grid_x, player.grid_y)
        max_passos = len(mapa) * len(mapa[0])
        pais, tempos = explorar_rotas(inicio, mapa, bombas, perigo, tempo_movimento, max_passos)

        melhor_destino = None
        melhor_score = float("-inf")
        for destino, tempo_chegada in tempos.items():
            if destino == inicio:
                continue

            score = self.score_posicao(
                player,
                destino,
                mapa,
                jogadores,
                bombas,
                perigo,
                tempo_chegada,
                tempo_movimento,
            )
            if perigo.get(destino) is None:
                score += 20

            if score > melhor_score:
                melhor_score = score
                melhor_destino = destino

        if melhor_destino is None:
            return []
        return reconstruir_rota(melhor_destino, pais)

    def encontrar_rota_powerup(self, player, mapa, bombas, perigo, tempo_movimento):
        inicio = (player.grid_x, player.grid_y)
        max_passos = len(mapa) * len(mapa[0])
        pais, tempos = explorar_rotas(inicio, mapa, bombas, perigo, tempo_movimento, max_passos)

        melhor_destino = None
        melhor_score = float("-inf")
        for destino, tempo_chegada in tempos.items():
            if destino == inicio:
                continue

            x, y = destino
            if mapa[y][x] not in (3, 4):
                continue

            score = 100 - tempo_chegada * 20
            score += contar_saidas_seguras(destino, mapa, bombas, perigo, tempo_chegada, tempo_movimento) * 4
            if destino == self.posicao_anterior:
                score -= 6.0
            if score > melhor_score:
                melhor_score = score
                melhor_destino = destino

        if melhor_destino is None:
            return []
        return reconstruir_rota(melhor_destino, pais)

    def encontrar_rota_bomba(self, player, mapa, jogadores, bombas, perigo, tempo_restante, hud_info, self_state):
        inicio = (player.grid_x, player.grid_y)
        max_passos = len(mapa) * len(mapa[0])
        pais, tempos = explorar_rotas(inicio, mapa, bombas, perigo, hud_info["tempo_movimento"], max_passos)

        melhor_destino = None
        melhor_score = float("-inf")
        for destino, tempo_chegada in tempos.items():
            if destino == inicio:
                continue

            player_virtual = SimpleNamespace(
                grid_x=destino[0],
                grid_y=destino[1],
                ativo=True,
            )
            jogadores_virtual = self.jogadores_com_player_virtual(jogadores, player, player_virtual)
            self_state_virtual = dict(self_state)
            self_state_virtual["grid_x"] = destino[0]
            self_state_virtual["grid_y"] = destino[1]
            score_bomba = self.score_ofensivo_bomba(
                player_virtual,
                destino,
                mapa,
                jogadores_virtual,
                bombas,
                perigo,
                tempo_restante,
                hud_info,
                self_state_virtual,
            )
            if score_bomba < 14.0:
                continue

            score = score_bomba - tempo_chegada * 18
            score += contar_saidas_seguras(
                destino,
                mapa,
                bombas,
                perigo,
                tempo_chegada,
                hud_info["tempo_movimento"],
            ) * 4
            if destino == self.posicao_anterior:
                score -= 10.0

            if score > melhor_score:
                melhor_score = score
                melhor_destino = destino

        if melhor_destino is None:
            return []
        return reconstruir_rota(melhor_destino, pais)

    def encontrar_rota_pressao(self, player, mapa, jogadores, bombas, perigo, tempo_restante, hud_info, self_state):
        inicio = (player.grid_x, player.grid_y)
        max_passos = len(mapa) * len(mapa[0])
        pais, tempos = explorar_rotas(inicio, mapa, bombas, perigo, hud_info["tempo_movimento"], max_passos)
        dist_atual = distancia_minima_inimigos(player, inicio, jogadores)

        melhor_destino = None
        melhor_score = float("-inf")
        for destino, tempo_chegada in tempos.items():
            if destino == inicio:
                continue

            dist_inimigo = distancia_minima_inimigos(player, destino, jogadores)
            if dist_inimigo is None:
                continue

            player_virtual = SimpleNamespace(
                grid_x=destino[0],
                grid_y=destino[1],
                ativo=True,
            )
            jogadores_virtual = self.jogadores_com_player_virtual(jogadores, player, player_virtual)
            self_state_virtual = dict(self_state)
            self_state_virtual["grid_x"] = destino[0]
            self_state_virtual["grid_y"] = destino[1]
            score_bomba = self.score_ofensivo_bomba(
                player_virtual,
                destino,
                mapa,
                jogadores_virtual,
                bombas,
                perigo,
                tempo_restante,
                hud_info,
                self_state_virtual,
            )

            score = 120.0 - dist_inimigo * 18.0 - tempo_chegada * 14.0
            score += contar_saidas_seguras(
                destino,
                mapa,
                bombas,
                perigo,
                tempo_chegada,
                hud_info["tempo_movimento"],
            ) * 3.0

            if dist_inimigo <= 2:
                score += 18.0
            elif dist_inimigo <= 4:
                score += 8.0
            if score_bomba != float("-inf"):
                score += min(42.0, score_bomba * 0.40)
            if inimigo_na_linha(
                player_virtual,
                jogadores_virtual,
                mapa,
                destino[0],
                destino[1],
                alcance_bomba(self_state["bomba_nivel"]),
            ):
                score += 16.0
            if dist_inimigo >= dist_atual and score_bomba == float("-inf") and mapa[destino[1]][destino[0]] not in (3, 4):
                score -= 18.0
            if destino == self.posicao_anterior:
                score -= 22.0

            if score > melhor_score:
                melhor_score = score
                melhor_destino = destino

        if melhor_destino is None:
            return []
        return reconstruir_rota(melhor_destino, pais)

    def deve_colocar_bomba(self, player, mapa, jogadores, bombas, perigo, tempo_restante, hud_info, self_state):
        posicao = (player.grid_x, player.grid_y)
        score_bomba = self.score_ofensivo_bomba(
            player,
            posicao,
            mapa,
            jogadores,
            bombas,
            perigo,
            tempo_restante,
            hud_info,
            self_state,
        )
        return score_bomba >= 18.0

    def listar_acoes_validas(self, player, mapa, jogadores, bombas, perigo, tempo_restante, hud_info, self_state):
        tempo_movimento = hud_info["tempo_movimento"]
        origem = (player.grid_x, player.grid_y)
        em_perigo = perigo.get(origem) is not None
        ataque_continuo = contar_paredes_quebraveis(mapa) == 0 and distancia_minima_inimigos(player, origem, jogadores) is not None
        acoes_legais = []
        acoes_seguras = []

        for acao, (dx, dy) in MOVIMENTOS.items():
            nx = player.grid_x + dx
            ny = player.grid_y + dy
            if not posicao_transitavel(mapa, bombas, origem, nx, ny):
                continue

            acoes_legais.append(acao)
            if celula_segura(perigo, (nx, ny), tempo_movimento):
                acoes_seguras.append(acao)

        if not em_perigo and not ataque_continuo and celula_segura(perigo, origem, tempo_movimento):
            acoes_legais.append("parado")
            acoes_seguras.append("parado")
        elif not acoes_legais:
            acoes_legais.append("parado")

        if not em_perigo and self.deve_colocar_bomba(
            player,
            mapa,
            jogadores,
            bombas,
            perigo,
            tempo_restante,
            hud_info,
            self_state,
        ):
            acoes_legais.append("bomba")
            acoes_seguras.append("bomba")

        if acoes_seguras:
            return list(dict.fromkeys(acoes_seguras))
        if acoes_legais:
            return list(dict.fromkeys(acoes_legais))
        return ["parado"]

    def escolher_acao_heuristica(self, player, mapa, jogadores, bombas, tempo_restante, hud_info, self_state, perigo):
        tempo_movimento = hud_info["tempo_movimento"]
        posicao_atual = (player.grid_x, player.grid_y)
        self.motivo_heuristica = "fallback"

        if perigo.get(posicao_atual) is not None:
            rota_fuga = self.encontrar_rota_fuga(
                player,
                mapa,
                jogadores,
                bombas,
                perigo,
                tempo_movimento,
            )
            if rota_fuga:
                self.motivo_heuristica = "fuga"
                return rota_fuga[0]

        if self.deve_colocar_bomba(player, mapa, jogadores, bombas, perigo, tempo_restante, hud_info, self_state):
            self.motivo_heuristica = "bomba"
            return "bomba"

        rota_bomba = self.encontrar_rota_bomba(
            player,
            mapa,
            jogadores,
            bombas,
            perigo,
            tempo_restante,
            hud_info,
            self_state,
        )
        rota_pressao = self.encontrar_rota_pressao(
            player,
            mapa,
            jogadores,
            bombas,
            perigo,
            tempo_restante,
            hud_info,
            self_state,
        )
        rota_powerup = self.encontrar_rota_powerup(player, mapa, bombas, perigo, tempo_movimento)
        paredes_restantes = contar_paredes_quebraveis(mapa)

        if rota_powerup and len(rota_powerup) <= 2 and not (rota_bomba and len(rota_bomba) <= 1):
            self.motivo_heuristica = "powerup"
            return rota_powerup[0]
        if rota_bomba and not rota_powerup and not rota_pressao:
            self.motivo_heuristica = "rota_bomba"
            return rota_bomba[0]
        if rota_pressao and not rota_bomba and not rota_powerup:
            self.motivo_heuristica = "pressao"
            return rota_pressao[0]
        if rota_powerup and not rota_bomba and not rota_pressao:
            self.motivo_heuristica = "powerup"
            return rota_powerup[0]
        if paredes_restantes == 0:
            if rota_bomba:
                self.motivo_heuristica = "rota_bomba"
                return rota_bomba[0]
            if rota_powerup and len(rota_powerup) <= 3:
                self.motivo_heuristica = "powerup"
                return rota_powerup[0]
            if rota_pressao:
                self.motivo_heuristica = "pressao"
                return rota_pressao[0]
        if rota_bomba and rota_pressao:
            if len(rota_bomba) <= len(rota_pressao) + 1:
                self.motivo_heuristica = "rota_bomba"
                return rota_bomba[0]
            self.motivo_heuristica = "pressao"
            return rota_pressao[0]
        if rota_bomba and rota_powerup:
            if len(rota_bomba) <= 2:
                self.motivo_heuristica = "rota_bomba"
                return rota_bomba[0]
            if len(rota_powerup) <= 3:
                self.motivo_heuristica = "powerup"
                return rota_powerup[0]
            self.motivo_heuristica = "rota_bomba"
            return rota_bomba[0]
        if rota_pressao and rota_powerup:
            if len(rota_powerup) <= 2:
                self.motivo_heuristica = "powerup"
                return rota_powerup[0]
            self.motivo_heuristica = "pressao"
            return rota_pressao[0]

        if rota_bomba:
            self.motivo_heuristica = "rota_bomba"
            return rota_bomba[0]
        if rota_powerup:
            self.motivo_heuristica = "powerup"
            return rota_powerup[0]
        if rota_pressao:
            self.motivo_heuristica = "pressao"
            return rota_pressao[0]

        acoes_candidatas = []
        for acao, (dx, dy) in MOVIMENTOS.items():
            nx = player.grid_x + dx
            ny = player.grid_y + dy
            if not posicao_transitavel(mapa, bombas, posicao_atual, nx, ny):
                continue

            chegada = tempo_movimento
            destino = (nx, ny)
            if not celula_segura(perigo, destino, chegada):
                continue

            score = self.score_posicao(
                player,
                destino,
                mapa,
                jogadores,
                bombas,
                perigo,
                chegada,
                tempo_movimento,
            )
            if destino == self.posicao_anterior:
                score -= 12.0
            acoes_candidatas.append((score, acao))

        score_atual = self.score_posicao(
            player,
            posicao_atual,
            mapa,
            jogadores,
            bombas,
            perigo,
            0.0,
            tempo_movimento,
        )
        if celula_segura(perigo, posicao_atual, tempo_movimento) and paredes_restantes > 0:
            acoes_candidatas.append((score_atual - 1.0, "parado"))

        if not acoes_candidatas:
            return "parado"

        acoes_candidatas.sort(reverse=True)
        melhor_score, melhor_acao = acoes_candidatas[0]
        if melhor_acao != "parado" and score_atual >= melhor_score + 0.5:
            return "parado"
        return melhor_acao

    def escolher_acao(self, estado_atual, acoes_validas, acao_heuristica):
        chave_estado = str(estado_atual)
        q_estado = self.q.setdefault(chave_estado, {})
        for acao in acoes_validas:
            q_estado.setdefault(acao, 0.0)

        epsilon_atual = max(self.epsilon_min, self.epsilon * (self.epsilon_decay ** self.contador))
        if random.random() < epsilon_atual:
            exploracao = [acao for acao in acoes_validas if acao != acao_heuristica]
            return random.choice(exploracao or acoes_validas)

        melhor_valor = None
        melhores = []
        for acao in acoes_validas:
            valor = q_estado.get(acao, 0.0)
            if acao == acao_heuristica:
                valor += 0.15

            if melhor_valor is None or valor > melhor_valor:
                melhor_valor = valor
                melhores = [acao]
            elif valor == melhor_valor:
                melhores.append(acao)

        valores_sem_bias = [q_estado.get(acao, 0.0) for acao in acoes_validas]
        if max(valores_sem_bias, default=0.0) == 0.0 and acao_heuristica in acoes_validas:
            return acao_heuristica
        if acao_heuristica in melhores:
            return acao_heuristica
        return random.choice(melhores)

    def decidir_acao(self, player, mapa, jogadores, bombas, tempo_restante, pontos, hud_info, self_state):
        self.partida_iniciada = True
        self.log_salvo = False

        self.registrar_tempo_partida(tempo_restante, hud_info)
        perigo = mapear_perigo(mapa, bombas)
        tempo_movimento = hud_info["tempo_movimento"]
        estado_atual = self.get_estado(player, mapa, jogadores, bombas, self_state, perigo, tempo_movimento)
        contexto_atual = self.extrair_contexto(
            player,
            mapa,
            jogadores,
            bombas,
            perigo,
            hud_info,
            self_state,
            tempo_restante,
        )

        if self.estado_anterior is not None and self.acao_anterior is not None:
            recompensa = self.get_recompensa(
                player,
                mapa,
                jogadores,
                bombas,
                pontos,
                perigo,
                tempo_movimento,
                tempo_restante,
                contexto_atual,
            )
            self.recompensa_acumulada += recompensa

            q_atual = self.q.get(str(self.estado_anterior), {}).get(self.acao_anterior, 0.0)
            max_q_futuro = max(self.q.get(str(estado_atual), {}).values()) if self.q.get(str(estado_atual)) else 0.0
            self.q[str(self.estado_anterior)] = self.q.get(str(self.estado_anterior), {})
            self.q[str(self.estado_anterior)][self.acao_anterior] = q_atual + self.alpha * (
                recompensa + self.gamma * max_q_futuro - q_atual
            )

        acao_heuristica = self.escolher_acao_heuristica(
            player,
            mapa,
            jogadores,
            bombas,
            tempo_restante,
            hud_info,
            self_state,
            perigo,
        )
        posicao_atual = (player.grid_x, player.grid_y)
        if perigo.get(posicao_atual) is not None and acao_heuristica in MOVIMENTOS:
            acao = acao_heuristica
        else:
            acoes_validas = self.listar_acoes_validas(
                player,
                mapa,
                jogadores,
                bombas,
                perigo,
                tempo_restante,
                hud_info,
                self_state,
            )
            if self.motivo_heuristica in {"bomba", "rota_bomba", "powerup"} and acao_heuristica in acoes_validas:
                acao = acao_heuristica
            elif (
                self.motivo_heuristica == "pressao"
                and contar_paredes_quebraveis(mapa) == 0
                and acao_heuristica in acoes_validas
            ):
                acao = acao_heuristica
            else:
                acao = self.escolher_acao(estado_atual, acoes_validas, acao_heuristica)

        if acao == "bomba":
            if not self.deve_colocar_bomba(player, mapa, jogadores, bombas, perigo, tempo_restante, hud_info, self_state):
                acao = acao_heuristica if acao_heuristica != "bomba" else "parado"
        elif acao in MOVIMENTOS:
            dx, dy = MOVIMENTOS[acao]
            destino = (player.grid_x + dx, player.grid_y + dy)
            if not posicao_transitavel(mapa, bombas, (player.grid_x, player.grid_y), destino[0], destino[1]):
                acao = acao_heuristica
            elif not celula_segura(perigo, destino, tempo_movimento):
                acao = acao_heuristica

        self.estado_anterior = estado_atual
        self.acao_anterior = acao
        self.contexto_anterior = contexto_atual
        self.posicao_anterior = posicao_atual
        self.contador += 1
        self.pontos_anteriores = pontos[jogadores.index(player)]
        self.tempo_restante_anterior = tempo_restante

        if self.contador % 200 == 0:
            self.salvar_q()

        return acao


def criar_decisor(jogador_id, q_table_file, log_file):
    controlador = ControladorDefensivo(jogador_id, q_table_file, log_file)
    return controlador.decidir_acao
