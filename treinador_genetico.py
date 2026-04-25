import json
import random
import subprocess
import os
import time

ARQUIVO_RESULTADO = "resultado_treino.json"

JOGADORES = [1, 2, 3, 4]

TAMANHO_POPULACAO = 10

TEMPO_FUGA_MIN = 15
TEMPO_FUGA_MAX = 55

CHANCE_BOMBA_MIN = 0.08
CHANCE_BOMBA_MAX = 0.35


MARGEM_MIN = 0
MARGEM_MAX = 3


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


# =========================
# GENE COMPLETO
# =========================
def criar_gene():
    return {
        "tempo_fuga": random.randint(TEMPO_FUGA_MIN, TEMPO_FUGA_MAX),
        "chance_bomba": round(random.uniform(CHANCE_BOMBA_MIN, CHANCE_BOMBA_MAX), 2),
        "margem_seguranca": random.randint(MARGEM_MIN, MARGEM_MAX)
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


# =========================
# MUTAÇÃO COMPLETA
# =========================
def mutar(gene):
    novo = gene.copy()

    if random.random() < 0.5:
        novo["tempo_fuga"] += random.randint(-5, 5)

    if random.random() < 0.5:
        novo["chance_bomba"] += random.uniform(-0.03, 0.03)

    if random.random() < 0.5:
        novo["margem_seguranca"] += random.randint(-1, 1)

    novo["tempo_fuga"] = max(TEMPO_FUGA_MIN, min(TEMPO_FUGA_MAX, novo["tempo_fuga"]))
    novo["chance_bomba"] = max(CHANCE_BOMBA_MIN, min(CHANCE_BOMBA_MAX, novo["chance_bomba"]))
    novo["margem_seguranca"] = max(MARGEM_MIN, min(MARGEM_MAX, novo["margem_seguranca"]))

    novo["chance_bomba"] = round(novo["chance_bomba"], 2)

    return novo

def cruzar(g1, g2):
    filho = {
        "tempo_fuga": random.choice([g1["tempo_fuga"], g2["tempo_fuga"]]),
        "chance_bomba": random.choice([g1["chance_bomba"], g2["chance_bomba"]]),
        "margem_seguranca": random.choice([g1["margem_seguranca"], g2["margem_seguranca"]])
    }
    return mutar(filho)

def criar_populacoes():
    return {j: [criar_gene() for _ in range(TAMANHO_POPULACAO)] for j in JOGADORES}


# =========================
# LOOP PRINCIPAL
# =========================
def main():
    populacoes = criar_populacoes()
    melhores_gerais = {j: None for j in JOGADORES}

    for geracao in range(1, GERACOES + 1):
        print(f"\n==== GERAÇÃO {geracao} ====")

        resultados_por_jogador = {j: [] for j in JOGADORES}

        for i in range(TAMANHO_POPULACAO):
            genes_rodada = {j: populacoes[j][i] for j in JOGADORES}

            print(f"\nTeste {i+1}")
            print(genes_rodada)

            avaliacoes = avaliar_genes(genes_rodada)

            for j, a in avaliacoes.items():
                resultados_por_jogador[j].append(a)

        for j in JOGADORES:
            resultados = sorted(resultados_por_jogador[j], key=lambda r: r["fitness"], reverse=True)

            melhor = resultados[0]

            if melhores_gerais[j] is None or melhor["fitness"] > melhores_gerais[j]["fitness"]:
                melhores_gerais[j] = melhor

            # salva SEMPRE o melhor geral (corrigido)
            salvar_gene(j, melhores_gerais[j]["gene"])

            with open(arquivo_melhor(j), "w") as f:
                json.dump(melhores_gerais[j], f, indent=4)

            pais = [r["gene"] for r in resultados[:4]]

            nova_pop = pais.copy()

            while len(nova_pop) < TAMANHO_POPULACAO:
                p1 = random.choice(pais)
                p2 = random.choice(pais)
                nova_pop.append(cruzar(p1, p2))

            populacoes[j] = nova_pop

    print("\nTREINO FINALIZADO!")

if __name__ == "__main__":
    main()