import os
import json
import csv
import subprocess
from datetime import datetime

# ======================================================
# CAMPEONATO BOMBERMAN AI - RELATÓRIO DE APRESENTAÇÃO
# ======================================================

ARQUIVO_RESULTADO = "resultado_partida.json"
ARQUIVO_JSON = "relatorio_campeonato.json"
ARQUIVO_CSV = "relatorio_campeonato.csv"
ARQUIVO_TXT = "relatorio_campeonato.txt"
ARQUIVO_APRESENTACAO = "relatorio_apresentacao.txt"

MEDALHAS = ["🥇", "🥈", "🥉", "🏅", "🎖️"]


def perguntar_int(texto, minimo=1, padrao=3):
    entrada = input(f"{texto} [padrão: {padrao}]: ").strip()

    if entrada == "":
        return padrao

    try:
        valor = int(entrada)
        if valor >= minimo:
            return valor
    except Exception:
        pass

    print("Valor inválido. Usando padrão.")
    return padrao


def rodar_partida(numero):
    if os.path.exists(ARQUIVO_RESULTADO):
        os.remove(ARQUIVO_RESULTADO)

    env = os.environ.copy()
    env["MODO_CAMPEONATO"] = "1"
    env["ARQUIVO_RESULTADO"] = ARQUIVO_RESULTADO

    print("\n==============================")
    print(f"🎮 PARTIDA {numero} INICIANDO")
    print("==============================\n")

    subprocess.run(["python", "main.py"], env=env)

    if not os.path.exists(ARQUIVO_RESULTADO):
        print("ERRO: resultado da partida não foi gerado.")
        return None

    with open(ARQUIVO_RESULTADO, "r", encoding="utf-8") as f:
        return json.load(f)


def gerar_analise(jogador):
    analises = []

    if jogador["vitorias"] > 0:
        analises.append("mostrou poder de decisão e conseguiu vencer partida")

    if jogador["kills"] >= 3:
        analises.append("teve postura ofensiva forte")
    elif jogador["kills"] > 0:
        analises.append("conseguiu eliminar adversários em momentos importantes")

    if jogador["mortes"] == 0:
        analises.append("foi muito consistente defensivamente")
    elif jogador["mortes"] >= 3:
        analises.append("sofreu bastante pressão durante o campeonato")

    if jogador["suicidios"] > 0:
        analises.append("precisa melhorar a fuga após plantar bombas")

    if jogador["bombas_colocadas"] > 0 and jogador["kills"] == 0:
        analises.append("plantou bombas, mas não converteu em eliminações")

    if jogador["tempo_vivo_medio"] >= 120:
        analises.append("teve excelente sobrevivência")
    elif jogador["tempo_vivo_medio"] < 40:
        analises.append("costumou cair cedo nas partidas")

    if not analises:
        analises.append("teve desempenho regular, sem grande destaque positivo ou negativo")

    return "; ".join(analises)


def frase_evento(evento):
    tempo = evento.get("tempo", 0)

    if evento.get("tipo") == "suicidio":
        return (
            f"Aos {tempo}s, {evento['nome_morto']} se complicou com a própria bomba "
            f"e acabou cometendo suicídio dentro da arena."
        )

    return (
        f"Aos {tempo}s, {evento['nome_assassino']} acertou em cheio e eliminou "
        f"{evento['nome_morto']} da partida."
    )


def gerar_narracao_partida(numero, resultado):
    nomes = resultado["nomes_jogadores"]
    vencedor_idx = resultado["vencedor"]
    vencedor_nome = nomes[vencedor_idx] if vencedor_idx is not None else "sem vencedor"
    eventos = resultado.get("eventos_morte", [])

    linhas = []
    linhas.append(f"🎬 PARTIDA {numero}")
    linhas.append("-" * 45)
    linhas.append("A arena foi aberta e os competidores entraram buscando espaço, poder-ups e eliminações.")

    if eventos:
        linhas.append("\nMomentos decisivos:")
        for evento in eventos:
            linhas.append(f"• {frase_evento(evento)}")
    else:
        linhas.append("\nA partida foi mais estratégica, sem eliminações registradas no relatório.")

    linhas.append(f"\n🏆 Resultado da partida: {vencedor_nome} saiu como vencedor.")

    linhas.append("\nPlacar da partida:")
    for i, nome in enumerate(nomes):
        linhas.append(
            f"• {nome}: {resultado['pontos'][i]} pontos | "
            f"Kills: {resultado['kills'][i]} | "
            f"Mortes: {resultado['mortes'][i]} | "
            f"Suicídios: {resultado.get('suicidios', [0] * len(nomes))[i]}"
        )

    return "\n".join(linhas)


def gerar_titulo_campeao(ranking):
    if not ranking:
        return "Nenhum campeão definido."

    campeao = ranking[0]
    return (
        f"🥇 O grande campeão foi {campeao['nome']}, com {campeao['score_final']} pontos de score final, "
        f"{campeao['vitorias']} vitória(s), {campeao['kills']} kill(s) e "
        f"{campeao['suicidios']} suicídio(s)."
    )


def main():
    qtd_partidas = perguntar_int("Quantas partidas você vai fazer?", 1, 3)

    partidas = []
    acumulado = {}

    for numero in range(1, qtd_partidas + 1):
        resultado = rodar_partida(numero)

        if resultado is None:
            continue

        partidas.append({
            "partida": numero,
            "resultado": resultado
        })

        nomes = resultado["nomes_jogadores"]

        for i, nome in enumerate(nomes):
            if i not in acumulado:
                acumulado[i] = {
                    "jogador": i,
                    "nome": nome,
                    "pontos": 0,
                    "vitorias": 0,
                    "kills": 0,
                    "mortes": 0,
                    "suicidios": 0,
                    "bombas_colocadas": 0,
                    "tempo_vivo_total": 0
                }

            acumulado[i]["pontos"] += resultado["pontos"][i]
            acumulado[i]["kills"] += resultado["kills"][i]
            acumulado[i]["mortes"] += resultado["mortes"][i]
            acumulado[i]["suicidios"] += resultado.get("suicidios", [0] * len(nomes))[i]
            acumulado[i]["bombas_colocadas"] += resultado["bombas_colocadas"][i]
            acumulado[i]["tempo_vivo_total"] += resultado["tempo_vivo"][i]

            if resultado["vencedor"] == i:
                acumulado[i]["vitorias"] += 1

    if not partidas:
        print("\nNenhuma partida válida foi finalizada. Verifique o erro exibido pelo main.py.")
        return

    partidas_validas = len(partidas)
    ranking = []

    for jogador in acumulado.values():
        jogador["tempo_vivo_medio"] = round(jogador["tempo_vivo_total"] / partidas_validas, 2)

        jogador["score_final"] = (
            jogador["pontos"]
            + jogador["vitorias"] * 3000
            + jogador["kills"] * 1200
            - jogador["mortes"] * 700
            - jogador["suicidios"] * 1000
        )

        jogador["analise"] = gerar_analise(jogador)
        ranking.append(jogador)

    ranking.sort(key=lambda x: x["score_final"], reverse=True)

    relatorio = {
        "data": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "partidas_solicitadas": qtd_partidas,
        "partidas_validas": partidas_validas,
        "ranking": ranking,
        "partidas": partidas
    }

    with open(ARQUIVO_JSON, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, indent=4, ensure_ascii=False)

    with open(ARQUIVO_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "posicao", "jogador", "pontos", "vitorias", "kills", "mortes",
            "suicidios", "bombas_colocadas", "tempo_vivo_medio", "score_final", "analise"
        ])

        for pos, jogador in enumerate(ranking, start=1):
            medalha = MEDALHAS[pos - 1] if pos - 1 < len(MEDALHAS) else "🎖️"
            writer.writerow([
                f"{medalha} {pos}", jogador["nome"], jogador["pontos"], jogador["vitorias"],
                jogador["kills"], jogador["mortes"], jogador["suicidios"],
                jogador["bombas_colocadas"], jogador["tempo_vivo_medio"],
                jogador["score_final"], jogador["analise"]
            ])

    with open(ARQUIVO_TXT, "w", encoding="utf-8") as f:
        f.write("RELATÓRIO TÉCNICO DO CAMPEONATO BOMBERMAN\n")
        f.write("=" * 55 + "\n\n")
        f.write(f"Data: {relatorio['data']}\n")
        f.write(f"Partidas válidas: {partidas_validas}\n\n")

        f.write("RANKING FINAL\n")
        f.write("-" * 55 + "\n")

        for pos, jogador in enumerate(ranking, start=1):
            medalha = MEDALHAS[pos - 1] if pos - 1 < len(MEDALHAS) else "🎖️"
            f.write(
                f"{medalha} {pos}º - {jogador['nome']} | "
                f"Score: {jogador['score_final']} | "
                f"Pontos: {jogador['pontos']} | "
                f"Vitórias: {jogador['vitorias']} | "
                f"Kills: {jogador['kills']} | "
                f"Mortes: {jogador['mortes']} | "
                f"Suicídios: {jogador['suicidios']} | "
                f"Tempo médio vivo: {jogador['tempo_vivo_medio']}s\n"
            )
            f.write(f"Análise: {jogador['analise']}\n\n")

        f.write("DETALHES POR PARTIDA\n")
        f.write("=" * 55 + "\n\n")

        for partida in partidas:
            f.write(gerar_narracao_partida(partida["partida"], partida["resultado"]))
            f.write("\n\n")

    with open(ARQUIVO_APRESENTACAO, "w", encoding="utf-8") as f:
        f.write("🎥 ROTEIRO DE APRESENTAÇÃO - CAMPEONATO BOMBERMAN AI\n")
        f.write("=" * 60 + "\n\n")
        f.write("Hoje tivemos uma sequência de batalhas entre inteligências artificiais dentro da arena Bomberman.\n")
        f.write("Cada jogador foi avaliado por pontuação, vitórias, eliminações, mortes, suicídios e tempo de sobrevivência.\n\n")

        f.write(gerar_titulo_campeao(ranking))
        f.write("\n\n")

        f.write("📊 RANKING FINAL COM MEDALHAS\n")
        f.write("-" * 60 + "\n")

        for pos, jogador in enumerate(ranking, start=1):
            medalha = MEDALHAS[pos - 1] if pos - 1 < len(MEDALHAS) else "🎖️"
            f.write(
                f"{medalha} {pos}º lugar: {jogador['nome']}\n"
                f"   Score final: {jogador['score_final']}\n"
                f"   Pontos: {jogador['pontos']} | Vitórias: {jogador['vitorias']} | "
                f"Kills: {jogador['kills']} | Mortes: {jogador['mortes']} | "
                f"Suicídios: {jogador['suicidios']}\n"
                f"   Análise: {jogador['analise']}\n\n"
            )

        f.write("🎬 NARRAÇÃO DAS PARTIDAS\n")
        f.write("=" * 60 + "\n\n")

        for partida in partidas:
            f.write(gerar_narracao_partida(partida["partida"], partida["resultado"]))
            f.write("\n\n")

        f.write("🎙️ FECHAMENTO PARA O VÍDEO\n")
        f.write("-" * 60 + "\n")
        f.write("Com isso, encerramos o campeonato das IAs no Bomberman.\n")
        f.write("O ranking final mostra não apenas quem venceu, mas também quem foi mais agressivo, quem sobreviveu melhor e quem precisa evoluir na tomada de decisão.\n")
        f.write("Esse relatório ajuda a comparar o comportamento das inteligências artificiais e entender qual estratégia funcionou melhor dentro da arena.\n")

    print("\n🏁 CAMPEONATO FINALIZADO!")
    print(f"Relatório de apresentação: {ARQUIVO_APRESENTACAO}")
    print(f"Relatório técnico TXT: {ARQUIVO_TXT}")
    print(f"Relatório JSON: {ARQUIVO_JSON}")
    print(f"Relatório CSV: {ARQUIVO_CSV}")

    print("\n📊 RANKING FINAL:")
    for pos, jogador in enumerate(ranking, start=1):
        medalha = MEDALHAS[pos - 1] if pos - 1 < len(MEDALHAS) else "🎖️"
        print(
            f"{medalha} {pos}º - {jogador['nome']} | "
            f"Score: {jogador['score_final']} | "
            f"Vitórias: {jogador['vitorias']} | "
            f"Kills: {jogador['kills']} | "
            f"Suicídios: {jogador['suicidios']}"
        )


if __name__ == "__main__":
    main()
