import json
import random
import os

def gerar_gene():
    return {
        "tempo_fuga": random.randint(20, 35),
        "chance_bomba": round(random.uniform(0.05, 0.20), 2)
    }

def salvar_json(nome_arquivo, dados):
    with open(nome_arquivo, "w") as f:
        json.dump(dados, f, indent=4)

def carregar_json(nome_arquivo):
    if os.path.exists(nome_arquivo):
        with open(nome_arquivo, "r") as f:
            return json.load(f)
    return None

def treinar_jogador(numero):
    arquivo_genes = f"genes_jogador{numero}.json"
    arquivo_melhor = f"melhor_gene_jogador{numero}.json"

    melhor_gene = carregar_json(arquivo_melhor)
    melhor_pontuacao = melhor_gene.get("pontuacao", -1) if melhor_gene else -1

    quantidade_testes = int(input(f"Quantos testes para o jogador {numero}? "))

    for i in range(quantidade_testes):
        gene = gerar_gene()
        salvar_json(arquivo_genes, gene)

        print(f"\nTESTE {i + 1} - JOGADOR {numero}")
        print(gene)
        print("Agora rode: python main.py")

        input("Depois da partida, pressione ENTER...")

        pontuacao = int(input("Pontuação final do jogador: "))
        sobreviveu = input("Sobreviveu? (s/n): ").lower()

        if sobreviveu == "s":
            pontuacao += 1000

        gene["pontuacao"] = pontuacao

        if pontuacao > melhor_pontuacao:
            melhor_pontuacao = pontuacao
            salvar_json(arquivo_melhor, gene)
            salvar_json(arquivo_genes, {
                "tempo_fuga": gene["tempo_fuga"],
                "chance_bomba": gene["chance_bomba"]
            })
            print("Novo melhor gene salvo!")
        else:
            print("Não superou o melhor gene.")

def main():
    jogador = int(input("Qual jogador deseja treinar? (1, 2, 3 ou 4): "))
    treinar_jogador(jogador)

if __name__ == "__main__":
    main()