import json
import random
import subprocess
import sys
import os

def gerar_gene():
    return {
        "tempo_fuga": random.randint(20, 35),
        "chance_bomba": round(random.uniform(0.05, 0.20), 2)
    }

def salvar_json(arquivo, dados):
    with open(arquivo, "w") as f:
        json.dump(dados, f, indent=4)

def carregar_json(arquivo):
    if not os.path.exists(arquivo):
        return None

    with open(arquivo, "r") as f:
        conteudo = f.read().strip()
        if not conteudo:
            return None
        return json.loads(conteudo)

def treinar(jogador, testes):
    arquivo_genes = f"genes_jogador{jogador}.json"
    arquivo_melhor = f"melhor_gene_jogador{jogador}.json"

    melhor = carregar_json(arquivo_melhor)
    melhor_pontuacao = melhor.get("pontuacao", -1) if melhor else -1

    for i in range(testes):
        gene = gerar_gene()
        salvar_json(arquivo_genes, gene)

        print(f"\nTESTE {i + 1}")
        print(gene)

        env = os.environ.copy()
        env["MODO_TREINO"] = "1"

        subprocess.run([sys.executable, "main.py"], env=env)

        resultado = carregar_json("resultado_treino.json")

        if not resultado:
            print("Erro: resultado_treino.json não foi gerado.")
            continue

        pontos = resultado["pontos"][jogador - 1]
        venceu = resultado["vencedor"] == jogador - 1

        fitness = pontos

        if venceu:
            fitness += 1000

        gene["pontuacao"] = fitness
        gene["pontos_jogo"] = pontos
        gene["venceu"] = venceu

        print(f"Pontuação: {pontos}")
        print(f"Venceu: {venceu}")
        print(f"Fitness: {fitness}")

        if fitness > melhor_pontuacao:
            melhor_pontuacao = fitness
            salvar_json(arquivo_melhor, gene)
            salvar_json(arquivo_genes, {
                "tempo_fuga": gene["tempo_fuga"],
                "chance_bomba": gene["chance_bomba"]
            })

            print("Novo melhor gene salvo!")
        else:
            print("Não superou o melhor.")

    print("\nTreinamento finalizado.")

if __name__ == "__main__":
    jogador = int(input("Qual jogador deseja treinar? (1, 2, 3 ou 4): "))
    testes = int(input("Quantos testes deseja rodar? "))

    treinar(jogador, testes)