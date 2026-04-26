import random
from collections import deque

DIRS = {
    "cima": (0,-1),
    "baixo": (0,1),
    "esquerda": (-1,0),
    "direita": (1,0)
}

mem = {}

def dentro(x,y,mapa):
    return 0 <= y < len(mapa) and 0 <= x < len(mapa[0])

def livre(x,y,mapa,bombas):
    if not dentro(x,y,mapa):
        return False

    if mapa[y][x] not in [0,3,4]:
        return False

    for b in bombas:
        if not b.explodida and b.x == x and b.y == y:
            return False
    return True

def perigo(x,y,bombas):
    for b in bombas:
        alcance = b.nivel

        if b.explodida:
            if (x,y) in b.fogo:
                return True

        else:
            if b.x == x and abs(b.y-y) <= alcance:
                return True
            if b.y == y and abs(b.x-x) <= alcance:
                return True
    return False

def rota_segura(px,py,mapa,bombas):
    fila = deque()
    fila.append((px,py,[]))
    visitado = {(px,py)}

    while fila:
        x,y,path = fila.popleft()

        if not perigo(x,y,bombas):
            return path

        for acao,(dx,dy) in DIRS.items():
            nx,ny = x+dx,y+dy

            if (nx,ny) not in visitado and livre(nx,ny,mapa,bombas):
                visitado.add((nx,ny))
                fila.append((nx,ny,path+[acao]))

    return []

def buscar_item(px,py,mapa,bombas):
    fila = deque()
    fila.append((px,py,[]))
    visitado = {(px,py)}

    while fila:
        x,y,path = fila.popleft()

        if mapa[y][x] in [3,4] and (x,y)!=(px,py):
            return path

        for acao,(dx,dy) in DIRS.items():
            nx,ny = x+dx,y+dy

            if (nx,ny) not in visitado and livre(nx,ny,mapa,bombas):
                if not perigo(nx,ny,bombas):
                    visitado.add((nx,ny))
                    fila.append((nx,ny,path+[acao]))
    return []

def decidir_acao(player,mapa,players,bombas,*args):
    pid = id(player)

    if pid not in mem:
        mem[pid] = {"fuga":0}

    x = player.grid_x
    y = player.grid_y

    # PRIORIDADE MAXIMA = FUGIR
    if perigo(x,y,bombas):
        rota = rota_segura(x,y,mapa,bombas)
        if rota:
            return rota[0]

    # acabou de plantar bomba
    if mem[pid]["fuga"] > 0:
        mem[pid]["fuga"] -= 1
        rota = rota_segura(x,y,mapa,bombas)
        if rota:
            return rota[0]

    # buscar powerup
    rota = buscar_item(x,y,mapa,bombas)
    if rota:
        return rota[0]

    # bloco perto = bomba
    for dx,dy in DIRS.values():
        nx,ny = x+dx,y+dy
        if dentro(nx,ny,mapa):
            if mapa[ny][nx] == 1:
                mem[pid]["fuga"] = 10
                return "bomba"

    # andar normal
    moves = []

    for acao,(dx,dy) in DIRS.items():
        nx,ny = x+dx,y+dy
        if livre(nx,ny,mapa,bombas):
            if not perigo(nx,ny,bombas):
                moves.append(acao)

    if moves:
        return random.choice(moves)

<<<<<<< HEAD
    return "parado"
=======
    return "parado"
>>>>>>> 5ba6ebeda2be5d025c1b7515597e306ba68fa5f3
