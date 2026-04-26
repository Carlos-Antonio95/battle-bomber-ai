import json
import random
import subprocess
import os
import time
import csv
import matplotlib.pyplot as plt

ARQUIVO_RESULTADO = "resultado_treino.json"
ARQUIVO_RELATORIO_JSON = "relatorio_treino.json"
ARQUIVO_RELATORIO_CSV = "relatorio_treino.csv"
ARQUIVO_GRAFICO = "grafico_treino.png"

JOGADORES = [1, 2, 3, 4]
TAMANHO_POPULACAO = 10

TEMPO_FUGA_MIN = 10
TEMPO_FUGA_MAX = 80

CHANCE_BOMBA_MIN = 0.08
CHANCE_BOMBA_MAX = 0.50

MARGEM_MIN = 0
MARGEM_MAX = 3

CAUTELA_BOMBA_MIN = 0.3
CAUTELA_BOMBA_MAX = 2.0


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


def arquivo_genes(jogador):
    return f"genes_jogador{jogador}.json"


def arquivo_melhor(jogador):
    return f"melhor_gene_jogador{jogador}.json"


def criar_gene():
    return {
        "tempo_fuga": random.randint(TEMPO_FUGA_MIN, TEMPO_FUGA_MAX),
        "chance_bomba": round(random.uniform(CHANCE_BOMBA_MIN, CHANCE_BOMBA_MAX), 2),
        "margem_seguranca": random.randint(MARGEM_MIN, MARGEM_MAX),
         "cautela_bomba": round(random.uniform(CAUTELA_BOMBA_MIN, CAUTELA_BOMBA_MAX), 2)
    }


def salvar_gene(jogador, gene):
    with open(arquivo_genes(jogador), "w") as f:
        json.dump(gene, f, indent=4)


def rodar_partida():
    if os.path.exists(ARQUIVO_RESULTADO):
        os.remove(ARQUIVO_RESULTADO)

    env = os.environ.copy()
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


def avaliar_genes(genes_por_jogador):
    for jogador, gene in genes_por_jogador.items():
        salvar_gene(jogador, gene)

    total_pontos = {j: 0 for j in JOGADORES}
    total_vitorias = {j: 0 for j in JOGADORES}

    for _ in range(PARTIDAS_POR_GENE):
        resultado = rodar_partida()

        if resultado is None:
            continue

        pontos = resultado["pontos"]
        vencedor = resultado["vencedor"]

        for jogador in JOGADORES:
            index = jogador - 1
            total_pontos[jogador] += pontos[index]

            if vencedor == index:
                total_vitorias[jogador] += 1

        time.sleep(0.1)

    avaliacoes = {}

    for jogador in JOGADORES:
        media = total_pontos[jogador] / PARTIDAS_POR_GENE
        vitorias = total_vitorias[jogador]
        fitness = media + (vitorias * 2000)

        avaliacoes[jogador] = {
            "gene": genes_por_jogador[jogador],
            "media_pontos": media,
            "vitorias": vitorias,
            "fitness": fitness
        }

    return avaliacoes


def mutar(gene):
    novo = gene.copy()

    if random.random() < 0.5:
        novo["tempo_fuga"] += random.randint(-5, 5)

    if random.random() < 0.5:
        novo["chance_bomba"] += random.uniform(-0.03, 0.03)

    if random.random() < 0.5:
        novo["margem_seguranca"] += random.randint(-1, 1)

    if random.random() < 0.5:
        novo["cautela_bomba"] += random.uniform(-0.15, 0.15)

    novo["tempo_fuga"] = max(TEMPO_FUGA_MIN, min(TEMPO_FUGA_MAX, novo["tempo_fuga"]))
    novo["chance_bomba"] = max(CHANCE_BOMBA_MIN, min(CHANCE_BOMBA_MAX, novo["chance_bomba"]))
    novo["margem_seguranca"] = max(MARGEM_MIN, min(MARGEM_MAX, novo["margem_seguranca"]))
    novo["cautela_bomba"] = max(CAUTELA_BOMBA_MIN, min(CAUTELA_BOMBA_MAX, novo["cautela_bomba"]))

    novo["chance_bomba"] = round(novo["chance_bomba"], 2)
    novo["cautela_bomba"] = round(novo["cautela_bomba"], 2)

    return novo

def cruzar(g1, g2):
    filho = {
        "tempo_fuga": random.choice([g1["tempo_fuga"], g2["tempo_fuga"]]),
        "chance_bomba": random.choice([g1["chance_bomba"], g2["chance_bomba"]]),
        "margem_seguranca": random.choice([g1["margem_seguranca"], g2["margem_seguranca"]]),
        "cautela_bomba": random.choice([g1["cautela_bomba"], g2["cautela_bomba"]])
    }

    return mutar(filho)


def criar_populacoes():
    return {
        jogador: [criar_gene() for _ in range(TAMANHO_POPULACAO)]
        for jogador in JOGADORES
    }

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
            "cautela_bomba_max": CAUTELA_BOMBA_MAX
        },
        "historico": historico,
        "melhores_gerais": melhores_gerais
    }

    with open(ARQUIVO_RELATORIO_JSON, "w") as f:
        json.dump(relatorio, f, indent=4)
def salvar_relatorio_csv(historico):
    with open(ARQUIVO_RELATORIO_CSV, "w", newline="") as f:
        writer = csv.writer(f)

        writer.writerow([
            "geracao",
            "jogador",
            "media_pontos",
            "vitorias",
            "fitness",
            "tempo_fuga",
            "chance_bomba",
            "margem_seguranca",
            "cautela_bomba"
        ])

        for item in historico:
            gene = item["gene"]

            writer.writerow([
                item["geracao"],
                item["jogador"],
                item["media_pontos"],
                item["vitorias"],
                item["fitness"],
                gene["tempo_fuga"],
                gene["chance_bomba"],
                gene["margem_seguranca"],
                gene["cautela_bomba"]
            ])

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


def main():
    populacoes = criar_populacoes()
    melhores_gerais = {j: None for j in JOGADORES}
    historico = []

    for geracao in range(1, GERACOES + 1):
        print(f"\n==== GERAÇÃO {geracao} ====")

        resultados_por_jogador = {j: [] for j in JOGADORES}

        for i in range(TAMANHO_POPULACAO):
            genes_rodada = {j: populacoes[j][i] for j in JOGADORES}

            print(f"\nTeste {i + 1}/{TAMANHO_POPULACAO}")
            print(genes_rodada)

            avaliacoes = avaliar_genes(genes_rodada)

            for jogador, avaliacao in avaliacoes.items():
                resultados_por_jogador[jogador].append(avaliacao)

        for jogador in JOGADORES:
            resultados = sorted(
                resultados_por_jogador[jogador],
                key=lambda r: r["fitness"],
                reverse=True
            )

            melhor = resultados[0]

            if melhores_gerais[jogador] is None or melhor["fitness"] > melhores_gerais[jogador]["fitness"]:
                melhores_gerais[jogador] = melhor

            historico.append({
                "geracao": geracao,
                "jogador": jogador,
                "gene": melhor["gene"],
                "media_pontos": melhor["media_pontos"],
                "vitorias": melhor["vitorias"],
                "fitness": melhor["fitness"]
            })

            salvar_gene(jogador, melhores_gerais[jogador]["gene"])

            with open(arquivo_melhor(jogador), "w") as f:
                json.dump(melhores_gerais[jogador], f, indent=4)

            pais = [r["gene"] for r in resultados[:4]]
            nova_pop = pais.copy()

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