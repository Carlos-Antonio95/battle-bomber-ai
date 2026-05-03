import json
import random
import subprocess
import os
import time
import csv
import matplotlib.pyplot as plt

# =========================
# ARQUIVOS DE SAÍDA
# =========================

ARQUIVO_RESULTADO = "resultado_treino.json"
ARQUIVO_RELATORIO_JSON = "relatorio_treino.json"
ARQUIVO_RELATORIO_CSV = "relatorio_treino.csv"
ARQUIVO_GRAFICO = "grafico_treino.png"

# =========================
# CONFIGURAÇÕES GERAIS
# =========================

JOGADORES = [1, 2, 3, 4]
TAMANHO_POPULACAO = 10

# =========================
# LIMITES DOS GENES
# =========================

TEMPO_FUGA_MIN = 10
TEMPO_FUGA_MAX = 80

CHANCE_BOMBA_MIN = 0.08
CHANCE_BOMBA_MAX = 0.50

MARGEM_MIN = 1
MARGEM_MAX = 3

CAUTELA_BOMBA_MIN = 0.3
CAUTELA_BOMBA_MAX = 2.0

# Novo gene: chance de colocar bomba quando tiver inimigo no raio
CHANCE_ATAQUE_MIN = 0.10
CHANCE_ATAQUE_MAX = 0.60

# Novo gene: distância máxima para começar a perseguir inimigo
DISTANCIA_PERSEGUIR_MIN = 2
DISTANCIA_PERSEGUIR_MAX = 7

# Novo gene: distância máxima para tentar bloqueio tático de rota
DISTANCIA_BLOQUEIO_MIN = 3
DISTANCIA_BLOQUEIO_MAX = 8

# Novo gene: chance de plantar bomba no ponto de bloqueio tático
CHANCE_BLOQUEIO_MIN = 0.20
CHANCE_BLOQUEIO_MAX = 0.70

#tempo para ele fugir em casa de travar ou perigo iminente  define com quantos segundos restantes a IA entra em fuga emergencial
TEMPO_PERIGO_IMINENTE_MIN = 0.45
TEMPO_PERIGO_IMINENTE_MAX = 1.20

MAX_PASSOS_FUGA_MIN = 6
MAX_PASSOS_FUGA_MAX = 12

MARGEM_TEMPO_BASE_MIN = 0.30
MARGEM_TEMPO_BASE_MAX = 0.55

PERSISTENCIA_MOVIMENTO_MIN = 1
PERSISTENCIA_MOVIMENTO_MAX = 4

# =========================
# ENTRADAS DO USUÁRIO
# =========================

def perguntar_int(texto, minimo, padrao):
    entrada = input(f"{texto} [padrão: {padrao}]: ").strip()

    if entrada == "":
        return padrao

    try:
        valor = int(entrada)
        if valor >= minimo:
            return valor
    except:
        pass

    print("Valor inválido. Usando padrão.")
    return padrao


GERACOES = perguntar_int("Quantas gerações deseja treinar?", 1, 10)
PARTIDAS_POR_GENE = perguntar_int("Quantas partidas por gene?", 1, 5)


# =========================
# NOMES DOS ARQUIVOS
# =========================

def arquivo_genes(jogador):
    return f"genes_jogador{jogador}.json"


def arquivo_melhor(jogador):
    return f"melhor_gene_jogador{jogador}.json"


# =========================
# CRIAÇÃO DO GENE
# =========================

def criar_gene():
    return {
        "tempo_fuga": random.randint(TEMPO_FUGA_MIN, TEMPO_FUGA_MAX),

        "chance_bomba": round(random.uniform(CHANCE_BOMBA_MIN, CHANCE_BOMBA_MAX), 2),

        "margem_seguranca": random.randint(MARGEM_MIN, MARGEM_MAX),

        "cautela_bomba": round(random.uniform(CAUTELA_BOMBA_MIN, CAUTELA_BOMBA_MAX), 2),

        # Gene de ataque:
        # controla a chance de jogar bomba quando o inimigo está no raio
        "chance_ataque": round(random.uniform(CHANCE_ATAQUE_MIN, CHANCE_ATAQUE_MAX), 2),

        # Gene de perseguição:
        # define até qual distância a IA tenta perseguir outro jogador
        "distancia_perseguir": random.randint(DISTANCIA_PERSEGUIR_MIN, DISTANCIA_PERSEGUIR_MAX),

        # Gene de bloqueio tático:
        # define até qual distância a IA tenta se posicionar para bloquear a rota do inimigo
        "distancia_bloqueio": random.randint(DISTANCIA_BLOQUEIO_MIN, DISTANCIA_BLOQUEIO_MAX),

        # Gene de bloqueio tático:
        # controla a chance de colocar bomba no ponto crítico de bloqueio
        "chance_bloqueio": round(random.uniform(CHANCE_BLOQUEIO_MIN, CHANCE_BLOQUEIO_MAX), 2),

        "tempo_perigo_iminente": round(random.uniform(TEMPO_PERIGO_IMINENTE_MIN, TEMPO_PERIGO_IMINENTE_MAX), 2),
        "max_passos_fuga": random.randint(MAX_PASSOS_FUGA_MIN, MAX_PASSOS_FUGA_MAX),

        "margem_tempo_base": round(random.uniform(MARGEM_TEMPO_BASE_MIN, MARGEM_TEMPO_BASE_MAX), 2),

        "persistencia_movimento": random.randint(PERSISTENCIA_MOVIMENTO_MIN, PERSISTENCIA_MOVIMENTO_MAX)
        
    }


# =========================
# SALVAR GENE DO JOGADOR
# =========================

def salvar_gene(jogador, gene):
    with open(arquivo_genes(jogador), "w") as f:
        json.dump(gene, f, indent=4)


# =========================
# RODAR UMA PARTIDA
# =========================

def rodar_partida():
    # Remove resultado antigo para evitar ler resultado de partida passada
    if os.path.exists(ARQUIVO_RESULTADO):
        os.remove(ARQUIVO_RESULTADO)

    env = os.environ.copy()

    # Ativa o modo treino dentro do main.py
    env["MODO_TREINO"] = "1"

    subprocess.run(
        ["python", "main.py"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    if not os.path.exists(ARQUIVO_RESULTADO):
        return None

    with open(ARQUIVO_RESULTADO, "r") as f:
        return json.load(f)


# =========================
# AVALIAR UM CONJUNTO DE GENES
# =========================

def avaliar_genes(genes_por_jogador):
    # Salva os genes atuais nos arquivos genes_jogador1, 2, 3 e 4
    for jogador, gene in genes_por_jogador.items():
        salvar_gene(jogador, gene)

    total_pontos = {j: 0 for j in JOGADORES}
    total_vitorias = {j: 0 for j in JOGADORES}
    total_tempo_vivo = {j: 0 for j in JOGADORES}
    total_kills = {j: 0 for j in JOGADORES}
    total_bombas = {j: 0 for j in JOGADORES}
    total_mortes = {j: 0 for j in JOGADORES}

    for _ in range(PARTIDAS_POR_GENE):
        resultado = rodar_partida()

        if resultado is None:
            continue

        pontos = resultado.get("pontos", [0, 0, 0, 0])
        vencedor = resultado.get("vencedor", None)

        tempo_vivo = resultado.get("tempo_vivo", [0, 0, 0, 0])
        kills = resultado.get("kills", [0, 0, 0, 0])
        bombas_colocadas = resultado.get("bombas_colocadas", [0, 0, 0, 0])
        mortes = resultado.get("mortes", [0, 0, 0, 0])

        for jogador in JOGADORES:
            index = jogador - 1

            total_pontos[jogador] += pontos[index]

            if vencedor == index:
                total_vitorias[jogador] += 1

            total_tempo_vivo[jogador] += tempo_vivo[index]
            total_kills[jogador] += kills[index]
            total_bombas[jogador] += bombas_colocadas[index]
            total_mortes[jogador] += mortes[index]

        time.sleep(0.1)

    avaliacoes = {}

    for jogador in JOGADORES:
        media = total_pontos[jogador] / PARTIDAS_POR_GENE
        vitorias = total_vitorias[jogador]

        media_tempo_vivo = total_tempo_vivo[jogador] / PARTIDAS_POR_GENE
        kills_total = total_kills[jogador]
        bombas_total = total_bombas[jogador]
        mortes_total = total_mortes[jogador]

        # FITNESS MELHORADO
        fitness = media
        fitness += vitorias * 2500
        fitness += media_tempo_vivo * 8
        fitness += kills_total * 900
        fitness -= mortes_total * 800

        # Penaliza bomba demais sem resultado
        bombas_sem_resultado = max(0, bombas_total - (kills_total * 3))
        fitness -= bombas_sem_resultado * 40

        # Penaliza quem nunca venceu
        if vitorias == 0:
            fitness -= 500

        # Penaliza morte muito rápida
        if media_tempo_vivo < 10:
            fitness -= 800

        if mortes_total >= PARTIDAS_POR_GENE:
            fitness -= 1500

        avaliacoes[jogador] = {
            "gene": genes_por_jogador[jogador],
            "media_pontos": media,
            "vitorias": vitorias,
            "tempo_vivo_medio": media_tempo_vivo,
            "kills": kills_total,
            "bombas_colocadas": bombas_total,
            "mortes": mortes_total,
            "fitness": fitness
        }

    return avaliacoes
# =========================
# MUTAÇÃO DO GENE
# =========================

def mutar(gene):
    novo = gene.copy()

    # Cada gene tem chance de sofrer pequena alteração
    if random.random() < 0.5:
        novo["tempo_fuga"] += random.randint(-5, 5)

    if random.random() < 0.5:
        novo["chance_bomba"] += random.uniform(-0.03, 0.03)

    if random.random() < 0.5:
        novo["margem_seguranca"] += random.randint(-1, 1)

    if random.random() < 0.5:
        novo["cautela_bomba"] += random.uniform(-0.15, 0.15)

    # Novo gene de ataque
    if random.random() < 0.5:
        novo["chance_ataque"] += random.uniform(-0.05, 0.05)

    # Novo gene de perseguição
    if random.random() < 0.5:
        novo["distancia_perseguir"] += random.randint(-1, 1)

    # Novo gene de bloqueio tático
    if random.random() < 0.5:
        novo["distancia_bloqueio"] += random.randint(-1, 1)

    # Novo gene de chance de bloqueio tático
    if random.random() < 0.5:
        novo["chance_bloqueio"] += random.uniform(-0.05, 0.05)

    if random.random() < 0.5:
        novo["tempo_perigo_iminente"] += random.uniform(-0.10, 0.10)

    if random.random() < 0.5:
        novo["max_passos_fuga"] += random.randint(-1, 1)

    if random.random() < 0.5:
        novo["margem_tempo_base"] += random.uniform(-0.03, 0.03)

    if random.random() < 0.5:
        novo["persistencia_movimento"] += random.randint(-1, 1)

    # Garante que nenhum gene passe dos limites definidos
    novo["tempo_fuga"] = max(TEMPO_FUGA_MIN, min(TEMPO_FUGA_MAX, novo["tempo_fuga"]))
    novo["chance_bomba"] = max(CHANCE_BOMBA_MIN, min(CHANCE_BOMBA_MAX, novo["chance_bomba"]))
    novo["margem_seguranca"] = max(MARGEM_MIN, min(MARGEM_MAX, novo["margem_seguranca"]))
    novo["cautela_bomba"] = max(CAUTELA_BOMBA_MIN, min(CAUTELA_BOMBA_MAX, novo["cautela_bomba"]))
    novo["chance_ataque"] = max(CHANCE_ATAQUE_MIN, min(CHANCE_ATAQUE_MAX, novo["chance_ataque"]))
    novo["distancia_perseguir"] = max(DISTANCIA_PERSEGUIR_MIN, min(DISTANCIA_PERSEGUIR_MAX, novo["distancia_perseguir"]))
    novo["distancia_bloqueio"] = max(DISTANCIA_BLOQUEIO_MIN, min(DISTANCIA_BLOQUEIO_MAX, novo["distancia_bloqueio"]))
    novo["chance_bloqueio"] = max(CHANCE_BLOQUEIO_MIN, min(CHANCE_BLOQUEIO_MAX, novo["chance_bloqueio"]))
    novo["tempo_perigo_iminente"] = max(TEMPO_PERIGO_IMINENTE_MIN,min(TEMPO_PERIGO_IMINENTE_MAX, novo["tempo_perigo_iminente"]))
    novo["max_passos_fuga"] = max(MAX_PASSOS_FUGA_MIN, min(MAX_PASSOS_FUGA_MAX, novo["max_passos_fuga"]))
    novo["margem_tempo_base"] = max(MARGEM_TEMPO_BASE_MIN, min(MARGEM_TEMPO_BASE_MAX, novo["margem_tempo_base"]))

    novo["persistencia_movimento"] = max(PERSISTENCIA_MOVIMENTO_MIN, min(PERSISTENCIA_MOVIMENTO_MAX, novo["persistencia_movimento"]))

    # Arredonda genes decimais
    novo["chance_bomba"] = round(novo["chance_bomba"], 2)
    novo["cautela_bomba"] = round(novo["cautela_bomba"], 2)
    novo["chance_ataque"] = round(novo["chance_ataque"], 2)
    novo["chance_bloqueio"] = round(novo["chance_bloqueio"], 2)
    novo["tempo_perigo_iminente"] = round(novo["tempo_perigo_iminente"], 2)
    novo["margem_tempo_base"] = round(novo["margem_tempo_base"], 2)
    

    return novo


# =========================
# CRUZAMENTO ENTRE DOIS GENES
# =========================

def cruzar(g1, g2):
    # O filho herda cada característica de um dos pais
    filho = {
        "tempo_fuga": random.choice([g1["tempo_fuga"], g2["tempo_fuga"]]),
        "chance_bomba": random.choice([g1["chance_bomba"], g2["chance_bomba"]]),
        "margem_seguranca": random.choice([g1["margem_seguranca"], g2["margem_seguranca"]]),
        "cautela_bomba": random.choice([g1["cautela_bomba"], g2["cautela_bomba"]]),
        "chance_ataque": random.choice([g1["chance_ataque"], g2["chance_ataque"]]),
        "distancia_perseguir": random.choice([g1["distancia_perseguir"], g2["distancia_perseguir"]]),
        "distancia_bloqueio": random.choice([g1["distancia_bloqueio"], g2["distancia_bloqueio"]]),
        "chance_bloqueio": random.choice([g1["chance_bloqueio"], g2["chance_bloqueio"]]),
        "tempo_perigo_iminente": random.choice([g1["tempo_perigo_iminente"], g2["tempo_perigo_iminente"]]) ,
        "max_passos_fuga": random.choice([g1["max_passos_fuga"], g2["max_passos_fuga"]]),

        "margem_tempo_base": random.choice([g1["margem_tempo_base"], g2["margem_tempo_base"]]),

        "persistencia_movimento": random.choice([g1["persistencia_movimento"], g2["persistencia_movimento"]])
    }

    return mutar(filho)


# =========================
# POPULAÇÃO INICIAL
# =========================

def criar_populacoes():
    return {
        jogador: [criar_gene() for _ in range(TAMANHO_POPULACAO)]
        for jogador in JOGADORES
    }


# =========================
# RELATÓRIO JSON
# =========================

def salvar_relatorio_json(historico, melhores_gerais):
    relatorio = {
        "configuracao": {
            "geracoes": GERACOES,
            "partidas_por_gene": PARTIDAS_POR_GENE,
            "tamanho_populacao": TAMANHO_POPULACAO,

            "tempo_fuga_min": TEMPO_FUGA_MIN,
            "tempo_fuga_max": TEMPO_FUGA_MAX,

            "chance_bomba_min": CHANCE_BOMBA_MIN,
            "chance_bomba_max": CHANCE_BOMBA_MAX,

            "margem_min": MARGEM_MIN,
            "margem_max": MARGEM_MAX,

            "cautela_bomba_min": CAUTELA_BOMBA_MIN,
            "cautela_bomba_max": CAUTELA_BOMBA_MAX,

            "chance_ataque_min": CHANCE_ATAQUE_MIN,
            "chance_ataque_max": CHANCE_ATAQUE_MAX,

            "distancia_perseguir_min": DISTANCIA_PERSEGUIR_MIN,
            "distancia_perseguir_max": DISTANCIA_PERSEGUIR_MAX,

            "distancia_bloqueio_min": DISTANCIA_BLOQUEIO_MIN,
            "distancia_bloqueio_max": DISTANCIA_BLOQUEIO_MAX,

            "chance_bloqueio_min": CHANCE_BLOQUEIO_MIN,
            "chance_bloqueio_max": CHANCE_BLOQUEIO_MAX,

            "tempo_perigo_iminente_min": TEMPO_PERIGO_IMINENTE_MIN,
            "tempo_perigo_iminente_max": TEMPO_PERIGO_IMINENTE_MAX,

            "max_passos_fuga_min": MAX_PASSOS_FUGA_MIN,
            "max_passos_fuga_max": MAX_PASSOS_FUGA_MAX,

            "margem_tempo_base_min": MARGEM_TEMPO_BASE_MIN,
            "margem_tempo_base_max": MARGEM_TEMPO_BASE_MAX,

            "persistencia_movimento_min": PERSISTENCIA_MOVIMENTO_MIN,
            "persistencia_movimento_max": PERSISTENCIA_MOVIMENTO_MAX
        },
        "historico": historico,
        "melhores_gerais": melhores_gerais
    }

    with open(ARQUIVO_RELATORIO_JSON, "w") as f:
        json.dump(relatorio, f, indent=4)


# =========================
# RELATÓRIO CSV
# =========================

def salvar_relatorio_csv(historico):
    with open(ARQUIVO_RELATORIO_CSV, "w", newline="") as f:
        writer = csv.writer(f)

        writer.writerow([
            "geracao",
            "jogador",
            "media_pontos",
            "vitorias",
            "tempo_vivo_medio",
            "kills",
            "bombas_colocadas",
            "mortes",
            "fitness",
            "tempo_fuga",
            "chance_bomba",
            "margem_seguranca",
            "cautela_bomba",
            "chance_ataque",
            "distancia_perseguir",
            "distancia_bloqueio",
            "chance_bloqueio",
            "tempo_perigo_iminente",
            "max_passos_fuga",
            "margem_tempo_base",
            "persistencia_movimento"
        ])

        for item in historico:
            gene = item["gene"]

            writer.writerow([
                item["geracao"],
                item["jogador"],
                item["media_pontos"],
                item["vitorias"],
                item["tempo_vivo_medio"],
                item["kills"],
                item["bombas_colocadas"],
                item["mortes"],
                item["fitness"],
                gene["tempo_fuga"],
                gene["chance_bomba"],
                gene["margem_seguranca"],
                gene["cautela_bomba"],
                gene["chance_ataque"],
                gene["distancia_perseguir"],
                gene["distancia_bloqueio"],
                gene["chance_bloqueio"],
                gene["tempo_perigo_iminente"],
                gene["max_passos_fuga"],
                gene["margem_tempo_base"],
                gene["persistencia_movimento"]
            ])
# =========================
# GRÁFICO DE EVOLUÇÃO
# =========================

def gerar_grafico(historico):
    plt.figure(figsize=(10, 6))

    for jogador in JOGADORES:
        dados = [h for h in historico if h["jogador"] == jogador]
        geracoes = [h["geracao"] for h in dados]
        fitness = [h["fitness"] for h in dados]

        plt.plot(geracoes, fitness, marker="o", label=f"Jogador {jogador}")

    plt.title("Evolução do Fitness por Geração")
    plt.xlabel("Geração")
    plt.ylabel("Fitness")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(ARQUIVO_GRAFICO)
    plt.close()


# =========================
# TREINAMENTO PRINCIPAL
# =========================

def main():
    populacoes = criar_populacoes()
    melhores_gerais = {j: None for j in JOGADORES}
    historico = []

    for geracao in range(1, GERACOES + 1):
        print(f"\n==== GERAÇÃO {geracao} ====")

        resultados_por_jogador = {j: [] for j in JOGADORES}

        # Testa cada indivíduo da população
        for i in range(TAMANHO_POPULACAO):
            genes_rodada = {j: populacoes[j][i] for j in JOGADORES}

            print(f"\nTeste {i + 1}/{TAMANHO_POPULACAO}")
            print(genes_rodada)

            avaliacoes = avaliar_genes(genes_rodada)

            for jogador, avaliacao in avaliacoes.items():
                resultados_por_jogador[jogador].append(avaliacao)

        # Seleciona os melhores de cada jogador
        for jogador in JOGADORES:
            resultados = sorted(
                resultados_por_jogador[jogador],
                key=lambda r: r["fitness"],
                reverse=True
            )

            melhor = resultados[0]

            # Atualiza o melhor geral daquele jogador
            if melhores_gerais[jogador] is None or melhor["fitness"] > melhores_gerais[jogador]["fitness"]:
                melhores_gerais[jogador] = melhor

            historico.append({
                "geracao": geracao,
                "jogador": jogador,
                "gene": melhor["gene"],
                "media_pontos": melhor["media_pontos"],
                "vitorias": melhor["vitorias"],
                "tempo_vivo_medio": melhor["tempo_vivo_medio"],
                "kills": melhor["kills"],
                "bombas_colocadas": melhor["bombas_colocadas"],
                "mortes": melhor["mortes"],
                "fitness": melhor["fitness"]
            })

            # Salva o melhor gene no arquivo usado pela IA
            salvar_gene(jogador, melhores_gerais[jogador]["gene"])

            # Salva também um arquivo separado com o melhor gene completo
            with open(arquivo_melhor(jogador), "w") as f:
                json.dump(melhores_gerais[jogador], f, indent=4)

            # Pega os 4 melhores como pais da próxima geração
            pais = [r["gene"] for r in resultados[:4]]
            nova_pop = pais.copy()

            # Completa a nova população criando filhos dos melhores pais
            while len(nova_pop) < TAMANHO_POPULACAO:
                p1 = random.choice(pais)
                p2 = random.choice(pais)
                nova_pop.append(cruzar(p1, p2))

            populacoes[jogador] = nova_pop

        salvar_relatorio_json(historico, melhores_gerais)
        salvar_relatorio_csv(historico)
        gerar_grafico(historico)

        print("\nMelhores da geração:")
        for jogador in JOGADORES:
            ultimo = [h for h in historico if h["jogador"] == jogador][-1]
            print(
                f"Jogador {jogador}: "
                f"fitness={ultimo['fitness']}, "
                f"média={ultimo['media_pontos']}, "
                f"vitórias={ultimo['vitorias']}, "
                f"gene={ultimo['gene']}"
            )

    print("\nTREINO FINALIZADO!")
    print(f"Relatório JSON salvo em: {ARQUIVO_RELATORIO_JSON}")
    print(f"Relatório CSV salvo em: {ARQUIVO_RELATORIO_CSV}")
    print(f"Gráfico salvo em: {ARQUIVO_GRAFICO}")


if __name__ == "__main__":
    main()