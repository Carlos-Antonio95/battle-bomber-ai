import atexit
import json
import os
import random
from collections import deque
from types import SimpleNamespace


# Todas as ações possíveis que o agente pode executar
ACOES = ["cima", "baixo", "esquerda", "direita", "bomba", "parado"]

# Mapeamento de cada ação para seu vetor de deslocamento (dx, dy)
MOVIMENTOS = {
    "cima": (0, -1),
    "baixo": (0, 1),
    "esquerda": (-1, 0),
    "direita": (1, 0),
}

# Tiles que o agente pode pisar: 0=vazio, 3=powerup velocidade, 4=powerup bomba
TILES_LIVRES = {0, 3, 4}

# Margem de segurança em segundos para considerar uma célula segura
MARGEM_SEGURANCA = 0.05

# Limite máximo de passos no BFS para evitar buscas muito longas
MAX_PASSOS_ROTAS = 36


def dentro_mapa(mapa, x, y):
    """Verifica se a posição (x, y) está dentro dos limites do mapa."""
    return 0 <= y < len(mapa) and 0 <= x < len(mapa[0])


def tile_livre(mapa, x, y):
    """Verifica se o tile em (x, y) é pisável pelo agente."""
    return dentro_mapa(mapa, x, y) and mapa[y][x] in TILES_LIVRES


def bomba_ativa_em(bombas, x, y):
    """Verifica se há uma bomba ainda não explodida na posição (x, y)."""
    return any(not b.explodida and b.x == x and b.y == y for b in bombas)


def alcance_bomba(nivel):
    """
    Calcula o alcance da explosão baseado no nível da bomba.
    Nível 1 = alcance 1, nível 2 = alcance 3, nível 3 = alcance 5, etc.
    """
    return 1 + max(0, nivel - 1) * 2


def celulas_explosao_bomba(bomba, mapa):
    """
    Retorna o conjunto de células que a bomba vai atingir quando explodir.
    Se a bomba já explodiu e ainda tem fogo ativo, retorna as células do fogo.
    Caso contrário, propaga o blast nas 4 direções até parede inquebrável ou borda.
    Paredes quebráveis (tile 1) são incluídas mas bloqueiam a propagação.
    """
    # Se a bomba já explodiu e tem fogo ativo, retorna as células do fogo
    if bomba.explodida and getattr(bomba, "tempo_fogo", 0) > 0:
        return set(getattr(bomba, "fogo", []))

    # Começa com a própria célula da bomba
    celulas = {(bomba.x, bomba.y)}
    for dx, dy in MOVIMENTOS.values():
        for passo in range(1, alcance_bomba(getattr(bomba, "nivel", 1)) + 1):
            nx = bomba.x + dx * passo
            ny = bomba.y + dy * passo
            if not dentro_mapa(mapa, nx, ny):
                break
            if mapa[ny][nx] == 2:  # Parede inquebrável bloqueia o blast
                break
            celulas.add((nx, ny))
            if mapa[ny][nx] == 1:  # Parede quebrável é incluída mas para o blast
                break
    return celulas


def mapear_perigo(mapa, bombas):
    """
    Cria um dicionário mapeando cada célula perigosa ao tempo até ser atingida.
    Trata reações em cadeia: se uma bomba explode dentro do raio de outra,
    a segunda explode no mesmo instante da primeira.
    Células com fogo ativo recebem tempo 0 (perigo imediato).
    """
    perigo = {}
    bombas_pendentes = [b for b in bombas if not b.explodida]

    # Pré-calcula as células de explosão de cada bomba
    blast_cache = {id(b): celulas_explosao_bomba(b, mapa) for b in bombas_pendentes}

    # Tempo de explosão inicial de cada bomba
    tempos = {
        id(b): max(0.0, float(getattr(b, "tempo_explosao", 0.0)))
        for b in bombas_pendentes
    }

    # Propaga reações em cadeia: bomba A no raio de bomba B → B explode junto com A
    for _ in range(len(bombas_pendentes)):
        alterou = False
        for bomba in bombas_pendentes:
            tempo_bomba = tempos[id(bomba)]
            for outra in bombas_pendentes:
                if outra is bomba:
                    continue
                # Se a outra bomba está no raio desta e esta explode antes
                if (outra.x, outra.y) in blast_cache[id(bomba)] and tempo_bomba < tempos[id(outra)]:
                    tempos[id(outra)] = tempo_bomba
                    alterou = True
        if not alterou:
            break  # Sem mais mudanças, encerra a propagação

    # Marca células com fogo ativo como perigo imediato (tempo 0)
    for bomba in bombas:
        if bomba.explodida and getattr(bomba, "tempo_fogo", 0) > 0:
            for celula in getattr(bomba, "fogo", []):
                perigo[celula] = 0.0

    # Registra o perigo de cada célula com o menor tempo de explosão possível
    for bomba in bombas_pendentes:
        tempo_bomba = tempos[id(bomba)]
        for celula in blast_cache[id(bomba)]:
            if celula not in perigo or tempo_bomba < perigo[celula]:
                perigo[celula] = tempo_bomba

    return perigo


def celula_segura(perigo, posicao, tempo_chegada):
    """
    Verifica se o agente estará seguro ao chegar numa célula num dado tempo.
    Seguro significa: sem perigo, ou o perigo ocorre depois da chegada + margem.
    """
    tempo_perigo = perigo.get(posicao)
    if tempo_perigo is None:
        return True  # Sem perigo registrado, célula é segura
    return tempo_perigo > tempo_chegada + MARGEM_SEGURANCA


def posicao_transitavel(mapa, bombas, inicio, x, y):
    """
    Verifica se o agente pode se mover para (x, y).
    A posição de origem sempre é transitável (o agente já está lá).
    Caso contrário, o tile deve ser livre e não ter bomba ativa.
    """
    if (x, y) == inicio:
        return True
    if not tile_livre(mapa, x, y):
        return False
    return not bomba_ativa_em(bombas, x, y)


def explorar_rotas(inicio, mapa, bombas, perigo, tempo_movimento, max_passos):
    """
    BFS modificado que explora apenas células seguras considerando o tempo de chegada.
    Retorna dois dicionários:
    - pais: para cada posição, qual posição anterior e qual ação levou até ela
    - tempos: para cada posição, o tempo acumulado até chegar lá
    O agente só se move para uma célula se chegar lá antes da bomba explodir.
    """
    fila = deque([inicio])
    pais = {inicio: (None, None)}
    tempos = {inicio: 0.0}
    passos = {inicio: 0}

    while fila:
        atual = fila.popleft()
        if passos[atual] >= max_passos:
            continue  # Limite de passos atingido

        for acao, (dx, dy) in MOVIMENTOS.items():
            nx = atual[0] + dx
            ny = atual[1] + dy
            if not posicao_transitavel(mapa, bombas, inicio, nx, ny):
                continue

            chegada = tempos[atual] + tempo_movimento
            destino = (nx, ny)

            # Só vai para células seguras no tempo de chegada
            if not celula_segura(perigo, destino, chegada):
                continue

            # Só atualiza se chegou mais rápido do que um caminho anterior
            if destino in tempos and chegada >= tempos[destino]:
                continue

            pais[destino] = (atual, acao)
            tempos[destino] = chegada
            passos[destino] = passos[atual] + 1
            fila.append(destino)

    return pais, tempos


def reconstruir_rota(destino, pais):
    """
    Reconstrói a sequência de ações do início até o destino
    percorrendo o dicionário de pais de trás para frente.
    """
    rota = []
    atual = destino
    while pais[atual][0] is not None:
        anterior, acao = pais[atual]
        rota.append(acao)
        atual = anterior
    rota.reverse()  # Inverte para ter a ordem início → destino
    return rota


def contar_saidas_seguras(posicao, mapa, bombas, perigo, tempo_base, tempo_movimento):
    """
    Conta quantas direções adjacentes são seguras e transitáveis a partir de uma posição.
    Usado para medir o quão "preso" o agente está.
    """
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
    """
    Retorna a distância de Manhattan até a bomba ativa mais próxima.
    Retorna 8 se não há bombas (valor neutro alto).
    """
    distancias = [
        abs(b.x - posicao[0]) + abs(b.y - posicao[1])
        for b in bombas
        if not b.explodida
    ]
    return min(distancias) if distancias else 8


def distancia_minima_inimigos(player, posicao, jogadores):
    """
    Retorna a distância de Manhattan até o inimigo ativo mais próximo.
    Retorna 8 se não há inimigos (valor neutro alto).
    """
    distancias = [
        abs(p.grid_x - posicao[0]) + abs(p.grid_y - posicao[1])
        for p in jogadores
        if p.ativo and p != player
    ]
    return min(distancias) if distancias else 8


def parede_quebravel_adjacente(mapa, x, y):
    """
    Conta quantas paredes quebráveis (tile 1) existem nas 4 células adjacentes.
    Indica o potencial destrutivo de uma bomba plantada na posição.
    """
    return sum(
        1
        for dx, dy in MOVIMENTOS.values()
        if dentro_mapa(mapa, x + dx, y + dy) and mapa[y + dy][x + dx] == 1
    )


def inimigo_na_linha(player, jogadores, mapa, x, y, alcance):
    """
    Verifica se há algum inimigo dentro do raio de explosão de uma bomba
    plantada em (x, y). Propaga nas 4 direções até o alcance, parando em paredes.
    """
    for dx, dy in MOVIMENTOS.values():
        for passo in range(1, alcance + 1):
            nx = x + dx * passo
            ny = y + dy * passo
            if not dentro_mapa(mapa, nx, ny):
                break
            if mapa[ny][nx] == 2:  # Parede inquebrável bloqueia a linha
                break
            for outro in jogadores:
                if outro.ativo and outro != player and outro.grid_x == nx and outro.grid_y == ny:
                    return True
            if mapa[ny][nx] == 1:  # Parede quebrável bloqueia a linha
                break
    return False


def distancia_manhattan(a, b):
    """Calcula a distância de Manhattan entre dois pontos."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def contar_paredes_no_blast(blast, mapa):
    """Conta quantas paredes quebráveis seriam destruídas pelo blast de uma bomba."""
    return sum(1 for x, y in blast if mapa[y][x] == 1)


def contar_paredes_quebraveis(mapa):
    """Conta o total de paredes quebráveis restantes no mapa."""
    return sum(1 for linha in mapa for tile in linha if tile == 1)


class ControladorDefensivo:
    def __init__(self, jogador_id, q_table_file, log_file):
        """
        Inicializa o agente com seus hiperparâmetros de Q-Learning,
        carrega a Q-Table salva (se existir) e registra salvamento automático.
        """
        self.jogador_id = jogador_id
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.q_table_path = os.path.join(self.base_dir, q_table_file)
        self.log_path = os.path.join(self.base_dir, log_file)

        # Hiperparâmetros do Q-Learning
        self.alpha = 0.25        # Taxa de aprendizado
        self.gamma = 0.92        # Fator de desconto para recompensas futuras
        self.epsilon = 0.14      # Probabilidade inicial de exploração aleatória
        self.epsilon_min = 0.03  # Epsilon mínimo após decaimento
        self.epsilon_decay = 0.9995  # Fator de decaimento do epsilon por ação

        # Versão do estado — muda quando a estrutura da tupla de estado muda,
        # invalidando entradas antigas da Q-Table
        self.versao_estado = 3

        # Carrega Q-Table existente ou começa do zero
        self.q = self._carregar_q()

        # Memória do passo anterior para calcular recompensa e atualizar Q-Table
        self.estado_anterior = None
        self.acao_anterior = None
        self.contexto_anterior = None
        self.motivo_heuristica = None
        self.posicao_anterior = None

        # Contadores e flags de controle
        self.recompensa_acumulada = 0.0
        self.contador = 0
        self.partida_iniciada = False
        self.log_salvo = False
        self.pontos_anteriores = None
        self.jogo_atual = self._proximo_jogo()

        # Controle de tempo para cálculo do bônus de sobrevivência
        self.tempo_partida = None
        self.tempo_restante_anterior = None
        self.tempo_vivo_acumulado = 0.0

        # Registra salvamento automático ao encerrar o programa
        atexit.register(self.salvar_q)
        atexit.register(self.salvar_log_saida)

    def _carregar_q(self):
        """Carrega a Q-Table do arquivo JSON. Retorna dicionário vazio se não existir."""
        if os.path.exists(self.q_table_path):
            with open(self.q_table_path, "r") as arquivo:
                return json.load(arquivo)
        return {}

    def _proximo_jogo(self):
        """
        Lê o log para descobrir qual é o próximo número de jogo.
        Garante numeração contínua entre sessões.
        """
        if not os.path.exists(self.log_path):
            return 1

        with open(self.log_path, "r") as arquivo:
            for linha in reversed(arquivo.readlines()):
                if linha.startswith("Jogo "):
                    return int(linha.split()[1].rstrip(":")) + 1
        return 1

    def salvar_q(self):
        """Salva a Q-Table atual no arquivo JSON."""
        with open(self.q_table_path, "w") as arquivo:
            json.dump(self.q, arquivo)

    def salvar_log_saida(self):
        """
        Salva no log a recompensa acumulada e total de ações da partida atual.
        Evita salvar duplicado com a flag log_salvo.
        """
        if self.log_salvo or not self.partida_iniciada or self.contador == 0:
            return

        with open(self.log_path, "a") as arquivo:
            arquivo.write(
                f"Jogo {self.jogo_atual}: Recompensa acumulada {self.recompensa_acumulada:.2f}, "
                f"Acoes {self.contador}\n"
            )
        self.log_salvo = True

    def bucket_tempo_perigo(self, tempo_perigo):
        """
        Converte o tempo de perigo contínuo em uma faixa discreta (bucket):
        3 = fogo ativo (tempo 0)
        2 = perigo iminente (≤ 0.7s)
        1 = perigo próximo (≤ 1.5s)
        0 = seguro
        """
        if tempo_perigo == 0.0:
            return 3
        if tempo_perigo is not None and tempo_perigo <= 0.7:
            return 2
        if tempo_perigo is not None and tempo_perigo <= 1.5:
            return 1
        return 0

    def bucket_distancia(self, distancia, max_bucket):
        """
        Converte distância contínua em bucket discreto limitado por max_bucket.
        Usado para reduzir o espaço de estados da Q-Table.
        """
        if distancia is None:
            return max_bucket
        return min(int(distancia), max_bucket)

    def get_estado(self, player, mapa, jogadores, bombas, self_state, perigo, tempo_movimento):
        """
        Monta a tupla de 11 valores que representa o estado atual do agente.
        Esta tupla é a chave na Q-Table. Valores contínuos são discretizados
        em buckets para manter o espaço de estados gerenciável.
        """
        x, y = player.grid_x, player.grid_y
        tempo_perigo = perigo.get((x, y))

        # Verifica se há powerup em alguma célula adjacente
        powerup_proximo = any(
            dentro_mapa(mapa, x + dx, y + dy) and mapa[y + dy][x + dx] in (3, 4)
            for dx, dy in MOVIMENTOS.values()
        )

        menor_dist_inimigo = distancia_minima_inimigos(player, (x, y), jogadores)
        menor_dist_bomba = distancia_minima_bombas((x, y), bombas)

        # Avalia o potencial ofensivo de plantar uma bomba na posição atual
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
            self.versao_estado,                                                          # [0] Versão do estado
            self.bucket_tempo_perigo(tempo_perigo),                                      # [1] Nível de perigo atual
            min(contar_saidas_seguras((x, y), mapa, bombas, perigo, 0.0, tempo_movimento), 4),  # [2] Saídas seguras
            self.bucket_distancia(menor_dist_bomba, 4),                                  # [3] Distância da bomba
            self.bucket_distancia(menor_dist_inimigo, 5),                                # [4] Distância do inimigo
            int(inimigo_alinhado),                                                       # [5] Inimigo no raio de blast
            min(parede_quebravel_adjacente(mapa, x, y), 4),                             # [6] Paredes quebráveis adj.
            int(powerup_proximo),                                                        # [7] Powerup próximo
            min(max(0, int(bomba_viavel // 25.0)), 4) if bomba_viavel != float("-inf") else 0,  # [8] Score da bomba
            min(self_state["bombas_ativas"], 2),                                         # [9] Bombas no campo
            min(self_state["bomba_nivel"], 4),                                           # [10] Nível da bomba
        )

    def registrar_tempo_partida(self, tempo_restante, hud_info):
        """
        Registra a duração total da partida na primeira chamada.
        Detecta reinício de partida se o tempo restante aumentou (nova partida).
        """
        tempo_partida_hud = float(hud_info.get("tempo_partida", tempo_restante))
        if self.tempo_partida is None:
            self.tempo_partida = max(tempo_partida_hud, float(tempo_restante), 1.0)
            return

        # Se o tempo aumentou, é uma nova partida — reseta contadores de tempo
        if self.tempo_restante_anterior is not None and tempo_restante > self.tempo_restante_anterior + 1.0:
            self.tempo_partida = max(tempo_partida_hud, float(tempo_restante), 1.0)
            self.tempo_vivo_acumulado = 0.0
            self.tempo_restante_anterior = None

    def bonus_tempo_vivo(self, tempo_restante, tempo_perigo):
        """
        Calcula um bônus de recompensa por sobreviver.
        O bônus cresce conforme o progresso da partida (incentiva sobreviver até o fim).
        É reduzido se o agente estiver em perigo (não recompensa ficar em perigo).
        """
        if self.tempo_restante_anterior is None:
            return 0.0

        # Delta de tempo desde a última ação (limitado a 1 segundo)
        delta_tempo = max(0.0, min(self.tempo_restante_anterior - tempo_restante, 1.0))
        self.tempo_vivo_acumulado += delta_tempo

        # Progresso de 0 a 1 ao longo da partida
        if self.tempo_partida is None or self.tempo_partida <= 0:
            progresso = 0.0
        else:
            progresso = min(1.0, self.tempo_vivo_acumulado / self.tempo_partida)

        # Bônus base de 45 aumenta até 120 no final da partida
        bonus = delta_tempo * (45.0 + 75.0 * progresso)

        # Reduz ou zera o bônus se estiver em perigo
        if tempo_perigo == 0.0:
            return 0.0
        if tempo_perigo is not None and tempo_perigo <= 0.7:
            return bonus * 0.25
        return bonus

    def extrair_contexto(self, player, mapa, jogadores, bombas, perigo, hud_info, self_state, tempo_restante):
        """
        Extrai métricas contextuais da situação atual do agente.
        Usado para calcular deltas entre passos na função de recompensa.
        """
        posicao = (player.grid_x, player.grid_y)
        bomb_score = self.score_ofensivo_bomba(
            player, posicao, mapa, jogadores, bombas, perigo,
            tempo_restante, hud_info, self_state,
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
        """
        Calcula a recompensa do passo anterior com base na situação atual.
        Combina várias fontes de sinal para guiar o aprendizado:
        - Sobrevivência ao longo do tempo
        - Perigo atual
        - Coleta de powerups
        - Aproximação de inimigos
        - Qualidade das ações ofensivas
        """
        idx = jogadores.index(player)
        x, y = player.grid_x, player.grid_y
        tempo_perigo = perigo.get((x, y))
        pontos_atuais = pontos[idx]
        delta_pontos = 0 if self.pontos_anteriores is None else pontos_atuais - self.pontos_anteriores

        # Recompensa base por sobreviver um passo
        recompensa = 1.5

        # Bônus crescente por tempo vivo
        recompensa += self.bonus_tempo_vivo(tempo_restante, tempo_perigo)

        # Recompensa proporcional a pontos ganhos no jogo
        recompensa += delta_pontos / 100.0

        # Penalidade/bônus baseado no nível de perigo da posição atual
        if tempo_perigo == 0.0:
            recompensa -= 60    # Está em fogo ativo — punição severa
        elif tempo_perigo is not None and tempo_perigo <= 0.7:
            recompensa -= 18    # Perigo iminente
        elif tempo_perigo is None:
            recompensa += 6     # Completamente seguro

        # Bônus por estar em célula com powerup
        if mapa[y][x] in (3, 4):
            recompensa += 10

        # Bônus por ter mais saídas disponíveis (menos preso)
        recompensa += contar_saidas_seguras((x, y), mapa, bombas, perigo, 0.0, tempo_movimento) * 0.8

        # Recompensas baseadas em comparação com o passo anterior
        if self.contexto_anterior is not None:
            # Recompensa por se aproximar do inimigo
            delta_inimigo = self.contexto_anterior["dist_inimigo"] - contexto_atual["dist_inimigo"]
            recompensa += delta_inimigo * 4.0

            # Recompensa por melhorar o potencial ofensivo
            delta_bomb_score = contexto_atual["bomb_score"] - self.contexto_anterior["bomb_score"]
            recompensa += max(0.0, delta_bomb_score) * 0.15

            # Recompensa por ter plantado uma bomba bem posicionada
            if self.acao_anterior == "bomba":
                recompensa += min(40.0, self.contexto_anterior["bomb_score"] * 0.3)

            # Penalidade por ficar parado quando deveria agir
            if self.acao_anterior == "parado":
                if self.contexto_anterior["bomb_score"] >= 18.0:
                    recompensa -= 7     # Devia ter plantado bomba
                if self.contexto_anterior["dist_inimigo"] <= 4:
                    recompensa -= 2.5   # Devia ter se aproximado

            # Bônus por mover-se para posição com mais saídas
            if self.acao_anterior in MOVIMENTOS and contexto_atual["saidas_seguras"] > self.contexto_anterior["saidas_seguras"]:
                recompensa += 1.5

        return recompensa

    def score_posicao(self, player, posicao, mapa, jogadores, bombas, perigo, tempo_chegada, tempo_movimento):
        """
        Avalia a qualidade de uma posição para o agente.
        Considera segurança, saídas disponíveis, distância de bombas e inimigos, e powerups.
        Usado nas funções de roteamento para escolher o melhor destino.
        """
        score = 0.0
        tempo_perigo = perigo.get(posicao)

        # Pontuação baseada em segurança
        if tempo_perigo is None:
            score += 28  # Célula completamente segura
        else:
            score += max(0.0, tempo_perigo - tempo_chegada) * 6  # Margem de tempo restante

        # Mais saídas = mais liberdade de movimento
        score += contar_saidas_seguras(posicao, mapa, bombas, perigo, tempo_chegada, tempo_movimento) * 7

        # Distância segura de bombas
        score += min(distancia_minima_bombas(posicao, bombas), 8) * 1.7

        # Distância de inimigos: próximo demais é ruim, distância média é ideal
        distancia_inimigo = min(distancia_minima_inimigos(player, posicao, jogadores), 8)
        if distancia_inimigo <= 1:
            score -= 1.5   # Muito próximo, risco de colisão
        elif distancia_inimigo <= 4:
            score += (5 - distancia_inimigo) * 2.5  # Distância de combate ideal
        else:
            score += max(0, 8 - distancia_inimigo) * 0.4  # Longe, incentivo fraco a aproximar

        # Bônus por powerup na posição
        x, y = posicao
        if mapa[y][x] in (3, 4):
            score += 25

        return score

    def contar_refugios_livres(self, posicao, mapa, bombas, perigo, tempo_movimento):
        """
        A partir de uma posição, usa BFS para contar quantas células seguras
        (sem nenhum perigo) o agente consegue alcançar.
        Retorna (quantidade de refúgios, tempo até o refúgio mais próximo).
        Usado para verificar se há fuga possível antes de plantar bomba.
        """
        pais, tempos = explorar_rotas(
            posicao, mapa, bombas, perigo, tempo_movimento,
            min(len(mapa) * len(mapa[0]), MAX_PASSOS_ROTAS),
        )

        refugios = 0
        melhor_tempo = None
        for destino, tempo_chegada in tempos.items():
            if perigo.get(destino) is None:  # Célula completamente segura
                refugios += 1
                if melhor_tempo is None or tempo_chegada < melhor_tempo:
                    melhor_tempo = tempo_chegada

        return refugios, melhor_tempo

    def jogadores_com_player_virtual(self, jogadores, player_real, player_virtual):
        """
        Substitui o jogador real por um jogador virtual na lista.
        Usado para simular situações hipotéticas (ex: agente em outra posição).
        """
        return [player_virtual if outro == player_real else outro for outro in jogadores]

    def score_ofensivo_bomba(self, player, posicao, mapa, jogadores, bombas, perigo, tempo_restante, hud_info, self_state):
        """
        Simula virtualmente o que aconteceria se o agente plantasse uma bomba
        na posição indicada. Retorna float('-inf') se for impossível ou suicida.
        
        O score considera:
        - Paredes que seriam destruídas (+28 cada)
        - Velocidade de fuga após plantar
        - Impacto sobre inimigos:
          * Morte quase certa: +290
          * Armadilha forte: +95
          * Redução de rotas: +60
        - Sem paredes, relaxa critérios se inimigo estiver próximo
        """
        x, y = posicao
        alcance = alcance_bomba(self_state["bomba_nivel"])

        # Condições que tornam impossível ou inútil plantar
        if self_state["bombas_ativas"] >= self_state["max_bombas"]:
            return float("-inf")  # Limite de bombas atingido
        if bomba_ativa_em(bombas, x, y):
            return float("-inf")  # Já tem bomba aqui
        if perigo.get((x, y)) is not None:
            return float("-inf")  # Posição já está em perigo
        if tempo_restante < hud_info["tempo_explosao"] + 1.0:
            return float("-inf")  # Tempo insuficiente para a bomba explodir

        # Cria bomba virtual para simular o cenário
        bomba_virtual = SimpleNamespace(
            x=x, y=y,
            nivel=self_state["bomba_nivel"],
            explodida=False,
            tempo_explosao=hud_info["tempo_explosao"],
            tempo_fogo=0,
            fogo=[],
        )
        bombas_simuladas = list(bombas) + [bomba_virtual]
        perigo_simulado = mapear_perigo(mapa, bombas_simuladas)

        # Verifica se o próprio agente consegue fugir após plantar
        refugios_proprios, melhor_tempo_refugio = self.contar_refugios_livres(
            (x, y), mapa, bombas_simuladas, perigo_simulado, hud_info["tempo_movimento"],
        )
        if refugios_proprios <= 0:
            return float("-inf")  # Suicídio, sem fuga possível

        # Calcula células atingidas e paredes destruídas
        blast = celulas_explosao_bomba(bomba_virtual, mapa)
        paredes_atingidas = contar_paredes_no_blast(blast, mapa)
        score = paredes_atingidas * 28.0

        # Bônus por fuga rápida
        if melhor_tempo_refugio is not None and melhor_tempo_refugio <= 1.0:
            score += 4.0
        elif melhor_tempo_refugio is not None and melhor_tempo_refugio <= 2.0:
            score += 2.0

        # Avalia o impacto sobre cada inimigo
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
                continue  # Inimigo muito longe para ser afetado

            # Compara refúgios do inimigo antes e depois da bomba
            refugios_antes, _ = self.contar_refugios_livres(
                pos_inimigo, mapa, bombas, perigo, hud_info["tempo_movimento"],
            )
            refugios_depois, melhor_tempo = self.contar_refugios_livres(
                pos_inimigo, mapa, bombas_simuladas, perigo_simulado, hud_info["tempo_movimento"],
            )
            delta_refugios = refugios_antes - refugios_depois
            armadilha_forte = refugios_depois <= 2 and delta_refugios >= 2
            morte_quase_certa = pos_inimigo in blast and refugios_depois == 0

            if pos_inimigo in blast:
                if morte_quase_certa:
                    objetivo_inimigo = True
                    score_inimigos += 150.0  # Inimigo no blast sem fuga
                elif armadilha_forte:
                    objetivo_inimigo = True
                    score_inimigos += 95.0   # Armadilha forte
                elif refugios_depois <= 1 and delta_refugios >= 1:
                    objetivo_inimigo = True
                    score_inimigos += 60.0   # Redução significativa de rotas

                if morte_quase_certa:
                    score_inimigos += 140.0  # Bônus adicional por morte quase certa
                if melhor_tempo is not None and melhor_tempo > 1.5:
                    score_inimigos += 16.0   # Inimigo demora para fugir

            elif dist <= 2 and armadilha_forte:
                objetivo_inimigo = True
                score_inimigos += delta_refugios * 18.0  # Armadilha mesmo fora do blast
            elif dist <= 1 and refugios_depois == 1 and delta_refugios >= 1:
                objetivo_inimigo = True
                score_inimigos += 30.0  # Inimigo adjacente quase sem saída

        score += score_inimigos

        paredes_restantes = contar_paredes_quebraveis(mapa)

        # Sem paredes e sem objetivo de inimigo direto
        if paredes_atingidas == 0 and not objetivo_inimigo:
            if paredes_restantes == 0:
                # Sem paredes no mapa: relaxa critérios se inimigo estiver próximo
                dist_inimigo_minima = 8
                for inimigo in jogadores:
                    if inimigo.ativo and inimigo != player:
                        d = abs(inimigo.grid_x - x) + abs(inimigo.grid_y - y)
                        if d < dist_inimigo_minima:
                            dist_inimigo_minima = d

                if dist_inimigo_minima <= alcance + 2:
                    return max(score, 16.0)  # Score mínimo para forçar ação ofensiva

            return float("-inf")  # Bomba inútil (sem paredes nem inimigos afetados)

        return score

    def encontrar_rota_fuga(self, player, mapa, jogadores, bombas, perigo, tempo_movimento):
        """
        Encontra a melhor rota de fuga quando o agente está em perigo.
        Avalia todos os destinos alcançáveis e escolhe o de maior score,
        dando bônus extra para células completamente seguras.
        Retorna apenas o primeiro passo da rota.
        """
        inicio = (player.grid_x, player.grid_y)
        max_passos = min(len(mapa) * len(mapa[0]), MAX_PASSOS_ROTAS)
        pais, tempos = explorar_rotas(inicio, mapa, bombas, perigo, tempo_movimento, max_passos)

        melhor_destino = None
        melhor_score = float("-inf")
        for destino, tempo_chegada in tempos.items():
            if destino == inicio:
                continue

            score = self.score_posicao(
                player, destino, mapa, jogadores, bombas, perigo, tempo_chegada, tempo_movimento,
            )
            if perigo.get(destino) is None:
                score += 20  # Bônus extra por célula completamente segura

            if score > melhor_score:
                melhor_score = score
                melhor_destino = destino

        if melhor_destino is None:
            return []
        return reconstruir_rota(melhor_destino, pais)

    def encontrar_rota_powerup(self, player, mapa, bombas, perigo, tempo_movimento):
        """
        Encontra a rota até o powerup mais vantajoso.
        Prioriza powerups próximos e com mais saídas seguras ao redor.
        Penaliza retornar à posição anterior (evita vai-e-vem).
        """
        inicio = (player.grid_x, player.grid_y)
        max_passos = min(len(mapa) * len(mapa[0]), MAX_PASSOS_ROTAS)
        pais, tempos = explorar_rotas(inicio, mapa, bombas, perigo, tempo_movimento, max_passos)

        melhor_destino = None
        melhor_score = float("-inf")
        for destino, tempo_chegada in tempos.items():
            if destino == inicio:
                continue

            x, y = destino
            if mapa[y][x] not in (3, 4):
                continue  # Ignora células sem powerup

            score = 100 - tempo_chegada * 20  # Powerups mais próximos valem mais
            score += contar_saidas_seguras(destino, mapa, bombas, perigo, tempo_chegada, tempo_movimento) * 4
            if destino == self.posicao_anterior:
                score -= 6.0  # Penaliza retornar à posição anterior

            if score > melhor_score:
                melhor_score = score
                melhor_destino = destino

        if melhor_destino is None:
            return []
        return reconstruir_rota(melhor_destino, pais)

    def encontrar_rota_bomba(self, player, mapa, jogadores, bombas, perigo, tempo_restante, hud_info, self_state):
        """
        Encontra a melhor posição para se mover e então plantar uma bomba.
        Para cada destino alcançável, simula virtualmente o score da bomba
        e penaliza destinos que custam muito tempo para chegar.
        Só considera destinos onde o score da bomba supera 14.
        """
        inicio = (player.grid_x, player.grid_y)
        max_passos = min(len(mapa) * len(mapa[0]), MAX_PASSOS_ROTAS)
        pais, tempos = explorar_rotas(inicio, mapa, bombas, perigo, hud_info["tempo_movimento"], max_passos)

        melhor_destino = None
        melhor_score = float("-inf")
        for destino, tempo_chegada in tempos.items():
            if destino == inicio:
                continue

            # Simula o agente na posição destino
            player_virtual = SimpleNamespace(grid_x=destino[0], grid_y=destino[1], ativo=True)
            jogadores_virtual = self.jogadores_com_player_virtual(jogadores, player, player_virtual)
            self_state_virtual = dict(self_state)
            self_state_virtual["grid_x"] = destino[0]
            self_state_virtual["grid_y"] = destino[1]

            score_bomba = self.score_ofensivo_bomba(
                player_virtual, destino, mapa, jogadores_virtual,
                bombas, perigo, tempo_restante, hud_info, self_state_virtual,
            )
            if score_bomba < 14.0:
                continue  # Posição não vale a pena para plantar

            # Score final: qualidade da bomba menos custo de deslocamento
            score = score_bomba - tempo_chegada * 18
            score += contar_saidas_seguras(destino, mapa, bombas, perigo, tempo_chegada, hud_info["tempo_movimento"]) * 4
            if destino == self.posicao_anterior:
                score -= 10.0  # Penaliza repetir posição

            if score > melhor_score:
                melhor_score = score
                melhor_destino = destino

        if melhor_destino is None:
            return []
        return reconstruir_rota(melhor_destino, pais)

    def encontrar_rota_pressao(self, player, mapa, jogadores, bombas, perigo, tempo_restante, hud_info, self_state):
        """
        Encontra rota para pressionar o inimigo — se aproximar mantendo ameaça.
        No confronto final (2 jogadores), é mais agressivo: pesos maiores
        para proximidade e alinhamento, penalidades menores para afastamento.
        """
        inicio = (player.grid_x, player.grid_y)
        max_passos = min(len(mapa) * len(mapa[0]), MAX_PASSOS_ROTAS)
        pais, tempos = explorar_rotas(inicio, mapa, bombas, perigo, hud_info["tempo_movimento"], max_passos)
        dist_atual = distancia_minima_inimigos(player, inicio, jogadores)

        jogadores_ativos = sum(1 for j in jogadores if j.ativo)
        eh_confronto_final = jogadores_ativos <= 2
        paredes_restantes = contar_paredes_quebraveis(mapa)

        melhor_destino = None
        melhor_score = float("-inf")
        for destino, tempo_chegada in tempos.items():
            if destino == inicio:
                continue

            dist_inimigo = distancia_minima_inimigos(player, destino, jogadores)
            if dist_inimigo is None:
                continue

            # Simula agente na posição destino
            player_virtual = SimpleNamespace(grid_x=destino[0], grid_y=destino[1], ativo=True)
            jogadores_virtual = self.jogadores_com_player_virtual(jogadores, player, player_virtual)
            self_state_virtual = dict(self_state)
            self_state_virtual["grid_x"] = destino[0]
            self_state_virtual["grid_y"] = destino[1]

            score_bomba = self.score_ofensivo_bomba(
                player_virtual, destino, mapa, jogadores_virtual,
                bombas, perigo, tempo_restante, hud_info, self_state_virtual,
            )

            # Score base maior no confronto final para aumentar agressividade
            score_base = 120.0 if not eh_confronto_final else 180.0
            score = score_base - dist_inimigo * (22.0 if eh_confronto_final else 18.0) - tempo_chegada * 14.0
            score += contar_saidas_seguras(
                destino, mapa, bombas, perigo, tempo_chegada, hud_info["tempo_movimento"],
            ) * (5.0 if eh_confronto_final else 3.0)

            # Bônus por proximidade ao inimigo
            if dist_inimigo <= 2:
                score += (40.0 if eh_confronto_final else 18.0)
            elif dist_inimigo <= 4:
                score += (24.0 if eh_confronto_final else 8.0)

            # Bônus se há potencial ofensivo na posição
            if score_bomba != float("-inf"):
                score += min(60.0 if eh_confronto_final else 42.0, score_bomba * (0.50 if eh_confronto_final else 0.40))
            elif paredes_restantes == 0:
                score += 8.0  # Sem paredes: ainda vale pressionar mesmo sem bomba ideal

            # Bônus se inimigo estaria no raio de explosão
            if inimigo_na_linha(
                player_virtual, jogadores_virtual, mapa,
                destino[0], destino[1], alcance_bomba(self_state["bomba_nivel"]),
            ):
                score += (32.0 if eh_confronto_final else 16.0)

            # Penalidade por se afastar do inimigo sem motivo válido
            if dist_inimigo >= dist_atual and score_bomba == float("-inf") and mapa[destino[1]][destino[0]] not in (3, 4):
                score -= (4.0 if eh_confronto_final else 8.0)

            # Penaliza repetir posição anterior
            if destino == self.posicao_anterior:
                score -= (12.0 if eh_confronto_final else 22.0)

            if score > melhor_score:
                melhor_score = score
                melhor_destino = destino

        if melhor_destino is None:
            return []
        return reconstruir_rota(melhor_destino, pais)

    def deve_colocar_bomba(self, player, mapa, jogadores, bombas, perigo, tempo_restante, hud_info, self_state):
        """
        Decide se o agente deve plantar uma bomba na posição atual.
        Threshold menor quando não há mais paredes (confronto puro).
        """
        posicao = (player.grid_x, player.grid_y)
        score_bomba = self.score_ofensivo_bomba(
            player, posicao, mapa, jogadores, bombas, perigo,
            tempo_restante, hud_info, self_state,
        )

        if score_bomba == float("-inf"):
            return False

        paredes_restantes = contar_paredes_quebraveis(mapa)

        # Sem paredes: threshold menor para forçar ação ofensiva
        if paredes_restantes == 0:
            return score_bomba >= 10.0
        else:
            return score_bomba >= 18.0

    def listar_acoes_validas(self, player, mapa, jogadores, bombas, perigo, tempo_restante, hud_info, self_state):
        """
        Lista todas as ações que o agente pode executar com segurança.
        Separa ações em legais (possíveis) e seguras (sem perigo).
        Prioriza ações seguras; só usa ações legais se não há opção segura.
        Em modo de ataque contínuo (sem paredes), remove 'parado' das opções.
        """
        tempo_movimento = hud_info["tempo_movimento"]
        origem = (player.grid_x, player.grid_y)
        em_perigo = perigo.get(origem) is not None
        # Modo de ataque: sem paredes e inimigos presentes → não pode parar
        ataque_continuo = contar_paredes_quebraveis(mapa) == 0 and distancia_minima_inimigos(player, origem, jogadores) is not None
        acoes_legais = []
        acoes_seguras = []

        # Avalia cada direção de movimento
        for acao, (dx, dy) in MOVIMENTOS.items():
            nx = player.grid_x + dx
            ny = player.grid_y + dy
            if not posicao_transitavel(mapa, bombas, origem, nx, ny):
                continue

            acoes_legais.append(acao)
            if celula_segura(perigo, (nx, ny), tempo_movimento):
                acoes_seguras.append(acao)

        # Adiciona 'parado' apenas se não está em perigo e não é modo ataque
        if not em_perigo and not ataque_continuo and celula_segura(perigo, origem, tempo_movimento):
            acoes_legais.append("parado")
            acoes_seguras.append("parado")
        elif not acoes_legais:
            acoes_legais.append("parado")  # Último recurso

        # Adiciona 'bomba' se vale a pena plantar
        if not em_perigo and self.deve_colocar_bomba(
            player, mapa, jogadores, bombas, perigo, tempo_restante, hud_info, self_state,
        ):
            acoes_legais.append("bomba")
            acoes_seguras.append("bomba")
        elif not em_perigo and contar_paredes_quebraveis(mapa) == 0:
            # Sem paredes: adiciona bomba como opção mesmo abaixo do threshold normal
            dist_inimigo = distancia_minima_inimigos(player, origem, jogadores)
            if dist_inimigo is not None and dist_inimigo <= 4:
                acoes_legais.append("bomba")

        # Retorna ações seguras prioritariamente
        if acoes_seguras:
            return list(dict.fromkeys(acoes_seguras))
        if acoes_legais:
            return list(dict.fromkeys(acoes_legais))
        return ["parado"]

    def escolher_acao_heuristica(self, player, mapa, jogadores, bombas, tempo_restante, hud_info, self_state, perigo):
        """
        Escolhe a melhor ação usando regras heurísticas, sem depender da Q-Table.
        Segue uma hierarquia de prioridades:
        1. Fuga (se em perigo)
        2. Plantar bomba agora (se vantajoso)
        3. Powerup muito próximo
        4. Sem paredes + inimigos: pressão prioritária
        5. Combinações de rota_bomba, pressão e powerup
        6. Fallback: avaliação direta de posições adjacentes
        """
        tempo_movimento = hud_info["tempo_movimento"]
        posicao_atual = (player.grid_x, player.grid_y)
        self.motivo_heuristica = "fallback"

        # PRIORIDADE 1: Fuga se está em perigo
        if perigo.get(posicao_atual) is not None:
            rota_fuga = self.encontrar_rota_fuga(player, mapa, jogadores, bombas, perigo, tempo_movimento)
            if rota_fuga:
                self.motivo_heuristica = "fuga"
                return rota_fuga[0]

        # PRIORIDADE 2: Plantar bomba na posição atual
        if self.deve_colocar_bomba(player, mapa, jogadores, bombas, perigo, tempo_restante, hud_info, self_state):
            self.motivo_heuristica = "bomba"
            return "bomba"

        # Calcula rotas para as 3 estratégias
        rota_bomba = self.encontrar_rota_bomba(
            player, mapa, jogadores, bombas, perigo, tempo_restante, hud_info, self_state,
        )
        rota_pressao = self.encontrar_rota_pressao(
            player, mapa, jogadores, bombas, perigo, tempo_restante, hud_info, self_state,
        )
        rota_powerup = self.encontrar_rota_powerup(player, mapa, bombas, perigo, tempo_movimento)
        paredes_restantes = contar_paredes_quebraveis(mapa)

        jogoadores_ativos = sum(1 for j in jogadores if j.ativo)
        sem_paredes_com_inimigos = (
            paredes_restantes == 0 and jogoadores_ativos > 1
            and distancia_minima_inimigos(player, posicao_atual, jogadores) is not None
        )

        # PRIORIDADE 3: Powerup muito próximo (≤2 passos) sem bomba urgente
        if rota_powerup and len(rota_powerup) <= 2 and not (rota_bomba and len(rota_bomba) <= 1):
            self.motivo_heuristica = "powerup"
            return rota_powerup[0]

        # Casos com apenas uma rota disponível
        if rota_bomba and not rota_powerup and not rota_pressao:
            self.motivo_heuristica = "rota_bomba"
            return rota_bomba[0]
        if rota_pressao and not rota_bomba and not rota_powerup:
            self.motivo_heuristica = "pressao"
            return rota_pressao[0]
        if rota_powerup and not rota_bomba and not rota_pressao:
            self.motivo_heuristica = "powerup"
            return rota_powerup[0]

        # PRIORIDADE 4: Sem paredes com inimigos → pressão tem prioridade
        if sem_paredes_com_inimigos and rota_pressao:
            self.motivo_heuristica = "pressao"
            return rota_pressao[0]

        # Sem paredes: hierarquia especial
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

        # Tie-breaking: bomba vs pressão → prefere bomba se caminho similar
        if rota_bomba and rota_pressao:
            if len(rota_bomba) <= len(rota_pressao) + 1:
                self.motivo_heuristica = "rota_bomba"
                return rota_bomba[0]
            self.motivo_heuristica = "pressao"
            return rota_pressao[0]

        # Tie-breaking: bomba vs powerup
        if rota_bomba and rota_powerup:
            if len(rota_bomba) <= 2:
                self.motivo_heuristica = "rota_bomba"
                return rota_bomba[0]
            if len(rota_powerup) <= 3:
                self.motivo_heuristica = "powerup"
                return rota_powerup[0]
            self.motivo_heuristica = "rota_bomba"
            return rota_bomba[0]

        # Tie-breaking: pressão vs powerup
        if rota_pressao and rota_powerup:
            if len(rota_powerup) <= 2:
                self.motivo_heuristica = "powerup"
                return rota_powerup[0]
            self.motivo_heuristica = "pressao"
            return rota_pressao[0]

        # Fallback para qualquer rota disponível
        if rota_bomba:
            self.motivo_heuristica = "rota_bomba"
            return rota_bomba[0]
        if rota_powerup:
            self.motivo_heuristica = "powerup"
            return rota_powerup[0]
        if rota_pressao:
            self.motivo_heuristica = "pressao"
            return rota_pressao[0]

        # Último fallback: avalia posições adjacentes diretamente
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
                player, destino, mapa, jogadores, bombas, perigo, chegada, tempo_movimento,
            )
            if destino == self.posicao_anterior:
                score -= 12.0  # Penaliza vai-e-vem
            acoes_candidatas.append((score, acao))

        score_atual = self.score_posicao(
            player, posicao_atual, mapa, jogadores, bombas, perigo, 0.0, tempo_movimento,
        )

        # Adiciona 'parado' como candidato com critério diferente por contexto
        if celula_segura(perigo, posicao_atual, tempo_movimento) and paredes_restantes > 0:
            acoes_candidatas.append((score_atual - 1.0, "parado"))
        elif celula_segura(perigo, posicao_atual, tempo_movimento) and paredes_restantes == 0:
            dist_inimigo = distancia_minima_inimigos(player, posicao_atual, jogadores)
            if dist_inimigo is None or dist_inimigo > 6:
                acoes_candidatas.append((score_atual - 1.0, "parado"))  # Só parado se inimigo longe

        if not acoes_candidatas:
            return "parado"

        acoes_candidatas.sort(reverse=True)
        melhor_score, melhor_acao = acoes_candidatas[0]
        # Só age se a posição destino for claramente melhor que a atual
        if melhor_acao != "parado" and score_atual >= melhor_score + 0.5:
            return "parado"
        return melhor_acao

    def escolher_acao(self, estado_atual, acoes_validas, acao_heuristica):
        """
        Implementa a política epsilon-greedy do Q-Learning.
        - Com probabilidade epsilon: explora uma ação aleatória (diferente da heurística)
        - Caso contrário: explota o conhecimento da Q-Table
        A ação heurística recebe um bônus de +0.15 para ser preferida em empates.
        Se nenhuma ação tem valor aprendido, usa a heurística como padrão.
        """
        chave_estado = str(estado_atual)
        q_estado = self.q.setdefault(chave_estado, {})

        # Inicializa valor 0 para ações ainda não vistas neste estado
        for acao in acoes_validas:
            q_estado.setdefault(acao, 0.0)

        # Epsilon decai com o número de ações realizadas
        epsilon_atual = max(self.epsilon_min, self.epsilon * (self.epsilon_decay ** self.contador))

        # Exploração: ação aleatória diferente da heurística
        if random.random() < epsilon_atual:
            exploracao = [acao for acao in acoes_validas if acao != acao_heuristica]
            return random.choice(exploracao or acoes_validas)

        # Explotação: escolhe a ação com maior valor Q
        melhor_valor = None
        melhores = []
        for acao in acoes_validas:
            valor = q_estado.get(acao, 0.0)
            if acao == acao_heuristica:
                valor += 0.15  # Bônus para a ação heurística em empates

            if melhor_valor is None or valor > melhor_valor:
                melhor_valor = valor
                melhores = [acao]
            elif valor == melhor_valor:
                melhores.append(acao)

        # Se nenhuma ação foi aprendida ainda, usa a heurística
        valores_sem_bias = [q_estado.get(acao, 0.0) for acao in acoes_validas]
        if max(valores_sem_bias, default=0.0) == 0.0 and acao_heuristica in acoes_validas:
            return acao_heuristica
        if acao_heuristica in melhores:
            return acao_heuristica
        return random.choice(melhores)

    def decidir_acao(self, player, mapa, jogadores, bombas, tempo_restante, pontos, hud_info, self_state):
        """
        Função principal chamada a cada frame do jogo.
        Coordena todo o fluxo de decisão:
        1. Registra tempo da partida
        2. Mapeia perigo atual
        3. Calcula estado e contexto
        4. Atualiza Q-Table com recompensa do passo anterior
        5. Escolhe ação via heurística ou Q-Learning
        6. Valida a ação (não pode ser suicida ou inválida)
        7. Salva estado para o próximo frame
        """
        self.partida_iniciada = True
        self.log_salvo = False

        # Registra duração da partida (detecta nova partida se tempo aumentou)
        self.registrar_tempo_partida(tempo_restante, hud_info)

        # Mapeia todas as células perigosas com seus tempos de explosão
        perigo = mapear_perigo(mapa, bombas)
        tempo_movimento = hud_info["tempo_movimento"]

        # Calcula representação do estado atual para a Q-Table
        estado_atual = self.get_estado(player, mapa, jogadores, bombas, self_state, perigo, tempo_movimento)

        # Extrai métricas contextuais para calcular recompensa
        contexto_atual = self.extrair_contexto(
            player, mapa, jogadores, bombas, perigo, hud_info, self_state, tempo_restante,
        )

        # Atualiza Q-Table com base na recompensa do passo anterior
        if self.estado_anterior is not None and self.acao_anterior is not None:
            recompensa = self.get_recompensa(
                player, mapa, jogadores, bombas, pontos, perigo,
                tempo_movimento, tempo_restante, contexto_atual,
            )
            self.recompensa_acumulada += recompensa

            # Fórmula do Q-Learning: Q(s,a) += α * (r + γ * max(Q(s')) - Q(s,a))
            q_atual = self.q.get(str(self.estado_anterior), {}).get(self.acao_anterior, 0.0)
            max_q_futuro = max(self.q.get(str(estado_atual), {}).values()) if self.q.get(str(estado_atual)) else 0.0
            self.q[str(self.estado_anterior)] = self.q.get(str(self.estado_anterior), {})
            self.q[str(self.estado_anterior)][self.acao_anterior] = q_atual + self.alpha * (
                recompensa + self.gamma * max_q_futuro - q_atual
            )

        # Obtém sugestão da heurística
        acao_heuristica = self.escolher_acao_heuristica(
            player, mapa, jogadores, bombas, tempo_restante, hud_info, self_state, perigo,
        )

        posicao_atual = (player.grid_x, player.grid_y)

        # Se está em perigo e a heurística sugere movimento → segue direto sem Q-Learning
        if perigo.get(posicao_atual) is not None and acao_heuristica in MOVIMENTOS:
            acao = acao_heuristica
        else:
            acoes_validas = self.listar_acoes_validas(
                player, mapa, jogadores, bombas, perigo, tempo_restante, hud_info, self_state,
            )

            # Para motivos críticos (bomba, powerup), segue heurística diretamente
            if self.motivo_heuristica in {"bomba", "rota_bomba", "powerup"} and acao_heuristica in acoes_validas:
                acao = acao_heuristica
            elif (
                self.motivo_heuristica == "pressao"
                and contar_paredes_quebraveis(mapa) == 0
                and acao_heuristica in acoes_validas
            ):
                acao = acao_heuristica  # Confronto final: segue pressão diretamente
            else:
                acao = self.escolher_acao(estado_atual, acoes_validas, acao_heuristica)

        # Validação final: garante que a ação escolhida é segura e válida
        if acao == "bomba":
            # Verifica novamente se bomba ainda é válida
            if not self.deve_colocar_bomba(player, mapa, jogadores, bombas, perigo, tempo_restante, hud_info, self_state):
                acao = acao_heuristica if acao_heuristica != "bomba" else "parado"
        elif acao in MOVIMENTOS:
            dx, dy = MOVIMENTOS[acao]
            destino = (player.grid_x + dx, player.grid_y + dy)
            # Verifica se o destino é transitável e seguro
            if not posicao_transitavel(mapa, bombas, (player.grid_x, player.grid_y), destino[0], destino[1]):
                acao = acao_heuristica
            elif not celula_segura(perigo, destino, tempo_movimento):
                acao = acao_heuristica

        # Salva estado atual para uso no próximo frame
        self.estado_anterior = estado_atual
        self.acao_anterior = acao
        self.contexto_anterior = contexto_atual
        self.posicao_anterior = posicao_atual
        self.contador += 1
        self.pontos_anteriores = pontos[jogadores.index(player)]
        self.tempo_restante_anterior = tempo_restante

        # Salva Q-Table a cada 200 ações para não perder progresso
        if self.contador % 200 == 0:
            self.salvar_q()

        return acao


def criar_decisor(jogador_id, q_table_file, log_file):
    """
    Interface pública do módulo.
    Cria o controlador e retorna apenas a função decidir_acao,
    que é chamada pelo main.py a cada frame passando o estado do jogo.
    """
    controlador = ControladorDefensivo(jogador_id, q_table_file, log_file)
    return controlador.decidir_acao