# 💣 Battle Bomber AI

Arena no estilo Bomberman, feita em **Python + Pygame**, onde quatro inteligências artificiais disputam partidas entre si. Cada IA foi desenvolvida separadamente e usa uma estratégia diferente — de regras com busca de caminho até **Q-learning** e parâmetros ajustados por **algoritmo genético**. Um script de campeonato roda várias partidas seguidas e gera ranking e relatórios.

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white) ![Pygame](https://img.shields.io/badge/Pygame-1B8A2E?style=flat-square&logo=python&logoColor=white) ![Q-learning](https://img.shields.io/badge/Q--learning-555555?style=flat-square) ![Algoritmo genético](https://img.shields.io/badge/Algoritmo_gen%C3%A9tico-555555?style=flat-square)

## Como funciona

- `main.py` monta a arena em Pygame (mapa, bombas, explosões, power-ups e placar) e carrega as quatro IAs dinamicamente com `importlib`.
- Cada IA fica em um módulo `ia_jogadorN.py` e expõe uma única função, `decidir_acao(...)`, que recebe o estado do jogo e devolve a ação: `cima`, `baixo`, `esquerda`, `direita`, `bomba` ou `parado`.
- `campeonato.py` executa várias partidas, soma pontos, vitórias, eliminações, mortes e suicídios, e gera os relatórios em CSV, JSON e TXT (ranking final e narração das partidas).

## As IAs

| Jogador | Estratégia |
|---|---|
| 1 | Regras com busca em largura (BFS) para achar rota segura e buscar itens |
| 2 | Ações aleatórias — serve de referência para comparar as outras |
| 3 | Regras com BFS para fuga, com parâmetros (margem de segurança, cautela com bombas, persistência de movimento) lidos de `genes_jogador3.json`, ajustados por algoritmo genético |
| 4 | **Q-learning** com exploração ε-greedy e decaimento do ε; a tabela aprendida fica em `q_table_jogador4.json` |

O desenvolvimento e o treino de cada IA estão nas branches `ia-1` a `ia-4`.

## Como rodar

```bash
pip install pygame

# uma partida
python main.py

# campeonato com várias partidas e relatórios
python campeonato.py
```

## Equipe

- [Carlos Antonio](https://github.com/Carlos-Antonio95)
- [João Vitor Santana Lins](https://github.com/Joaovitor8708)
- [Marcos Felipe](https://github.com/Marcos-Felipe1)

## Licença

MIT
