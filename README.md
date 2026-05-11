# 💣 Battle Bomber AI

Bem-vindo ao **Battle Bomber AI**! Este é um jogo inspirado no clássico Bomberman, desenvolvido especificamente como um ambiente de simulação para o treinamento e testes de agentes de Inteligência Artificial.

## 🎓 Sobre o Projeto

Este projeto foi criado como um trabalho prático para uma competição de uma disciplina universitária de **Inteligência Artificial**. 

O desenvolvimento e as estratégias estão sendo conduzidos por uma equipe de 4 pessoas (eu e mais 3 colegas). Nossa dinâmica de trabalho é focada na experimentação: cada membro da equipe está responsável por desenvolver, modelar e treinar suas próprias versões de IA de forma independente. Ao final do período de treinamento, realizaremos um torneio interno para avaliar as estratégias, e o modelo que apresentar o **melhor desempenho** geral e a maior taxa de vitória será escolhido como a versão final que representará nosso grupo na competição da disciplina.

## 🧠 O Modelo de IA: Reinforcement Learning

A abordagem principal utilizada neste repositório para dar "vida" ao agente é o **Aprendizado por Reforço (Reinforcement Learning)**, implementado através do algoritmo de Q-Learning.

O agente observa o estado do tabuleiro (posições das bombas, blocos, inimigos, paredes e rotas de fuga) e toma decisões calculadas. A cada ação, ele recebe uma **recompensa** (positiva ao quebrar blocos, pegar power-ups ou matar inimigos, e negativa ao morrer ou ficar encurralado). Com o tempo, através da repetição e da exploração (epsilon-greedy), ele atualiza sua tabela de estados (*Q-Table*) e começa a adotar comportamentos defensivos e ofensivos muito mais sofisticados para sobreviver até o final da partida.

## 🛠️ Tecnologias e Bibliotecas Utilizadas

O projeto foi construído inteiramente em **Python** e não depende de frameworks complexos de Deep Learning, focando na lógica algorítmica e na implementação manual de RL clássico.

* **Python 3**: Linguagem base do projeto.
* **Pygame**: Biblioteca principal utilizada para a renderização gráfica, controle da janela de exibição, HUD e o _game loop_ em tempo real.
* **Bibliotecas nativas do Python**:
  * `json`: Utilizada para persistir e carregar a Q-Table e os "genes" dos modelos entre as partidas.
  * `collections.deque`: Usada fortemente na implementação de algoritmos de busca (como o BFS - Busca em Largura) para o cálculo espacial de rotas de fuga seguras e busca por power-ups.
  * `random`: Usada para introduzir a taxa de exploração do modelo de IA (epsilon) e as probabilidades de geração de cenário.
  * `hashlib`: Aplicada para gerar checksums e garantir que as IAs não trapaceiem alterando atributos do próprio mapa ou de outros jogadores diretamente na memória.

## 🚀 Como Executar

1. Certifique-se de ter o Python instalado na sua máquina.
2. Instale as dependências necessárias executando o comando abaixo:

```bash
pip install pygame
```

3. Para iniciar a arena de combate, rode o arquivo principal:

```bash
python main.py
```
