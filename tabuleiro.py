from dataclasses import dataclass

TAMANHO = 10
LINHAS = "ABCDEFGHIJ"
FROTA = [("PA", 5), ("EN", 4), ("CR", 3), ("CR", 3), ("DE", 2), ("DE", 2)]


@dataclass
class Navio:
    codigo: str
    tamanho: int
    inicial: str
    orientacao: str
    casas: tuple[str, ...]
    acertos: set[str]


class Tabuleiro:
    def __init__(self):
        self.grade = [[None for _ in range(TAMANHO)] for _ in range(TAMANHO)]
        self.navios: list[Navio] = []
        self.tiros_recebidos: dict[str, str] = {}

    @staticmethod
    def coordenada_para_indices(coordenada: str) -> tuple[int, int]:
        c = coordenada.strip().upper()
        if len(c) < 2 or c[0] not in LINHAS:
            raise ValueError("Coordenada inválida. Use A1 até J10.")
        try:
            coluna = int(c[1:]) - 1
        except ValueError as exc:
            raise ValueError("A coluna precisa ser um número de 1 a 10.") from exc
        if not 0 <= coluna < TAMANHO:
            raise ValueError("A coluna precisa estar entre 1 e 10.")
        return LINHAS.index(c[0]), coluna

    @staticmethod
    def indices_para_coordenada(linha: int, coluna: int) -> str:
        return f"{LINHAS[linha]}{coluna + 1}"

    def normalizar_coordenada(self, coordenada: str) -> str:
        l, c = self.coordenada_para_indices(coordenada)
        return self.indices_para_coordenada(l, c)

    def calcular_casas(self, inicial: str, orientacao: str, tamanho: int) -> tuple[str, ...]:
        l, c = self.coordenada_para_indices(inicial)
        orientacao = orientacao.strip().upper()
        if orientacao not in ("H", "V"):
            raise ValueError("Orientação inválida: use H ou V.")
        casas = []
        for deslocamento in range(tamanho):
            nl = l + (deslocamento if orientacao == "V" else 0)
            nc = c + (deslocamento if orientacao == "H" else 0)
            if nl >= TAMANHO or nc >= TAMANHO:
                raise ValueError("O navio ultrapassa os limites do tabuleiro.")
            casas.append(self.indices_para_coordenada(nl, nc))
        return tuple(casas)

    def posicionar_navio(self, codigo: str, tamanho: int, inicial: str, orientacao: str):
        casas = self.calcular_casas(inicial, orientacao, tamanho)
        for casa in casas:
            l, c = self.coordenada_para_indices(casa)
            if self.grade[l][c] is not None:
                raise ValueError(f"A casa {casa} já está ocupada.")
        indice = len(self.navios)
        navio = Navio(codigo, tamanho, self.normalizar_coordenada(inicial),
                      orientacao.strip().upper(), casas, set())
        self.navios.append(navio)
        for casa in casas:
            l, c = self.coordenada_para_indices(casa)
            self.grade[l][c] = indice

    def registrar_tiro(self, coordenada: str) -> tuple[str, bool]:
        coord = self.normalizar_coordenada(coordenada)
        if coord in self.tiros_recebidos:
            raise ValueError(f"A casa {coord} já recebeu um tiro.")
        l, c = self.coordenada_para_indices(coord)
        indice = self.grade[l][c]
        if indice is None:
            self.tiros_recebidos[coord] = "AGUA"
            return "AGUA", False
        navio = self.navios[indice]
        navio.acertos.add(coord)
        if len(navio.acertos) == navio.tamanho:
            self.tiros_recebidos[coord] = f"AFUNDOU {navio.codigo}"
            fim = all(len(n.acertos) == n.tamanho for n in self.navios)
            return f"AFUNDOU {navio.codigo}", fim
        self.tiros_recebidos[coord] = "ACERTOU"
        return "ACERTOU", False

    def serializar_frota(self) -> str:
        return " ".join(f"{n.codigo}:{n.inicial}:{n.orientacao}" for n in self.navios)

    def exibir(self, mostrar_navios=True):
        print("       " + " ".join(f"{n:2}" for n in range(1, 11)))
        print("     +" + "---" * 10 + "+")
        for i, letra in enumerate(LINHAS):
            itens = []
            for j in range(TAMANHO):
                coord = self.indices_para_coordenada(i, j)
                indice = self.grade[i][j]
                if coord in self.tiros_recebidos:
                    marca = "o" if self.tiros_recebidos[coord] == "AGUA" else "X"
                elif indice is not None and mostrar_navios:
                    marca = self.navios[indice].codigo
                else:
                    marca = "."
                itens.append(f"{marca:2}")
            print(f"     {letra}|" + " ".join(itens) + "|")
        print("     +" + "---" * 10 + "+")


def posicionar_frota() -> Tabuleiro:
    tab = Tabuleiro()
    print("\n=== POSICIONAMENTO DA FROTA ===")
    print("H = horizontal (direita) | V = vertical (baixo)")
    for i, (codigo, tamanho) in enumerate(FROTA, 1):
        while True:
            print(f"\nNavio {i}/6: {codigo} — {tamanho} casas")
            tab.exibir()
            inicial = input("Casa inicial (ex.: B7): ").strip()
            orientacao = input("Orientação (H/V): ").strip()
            try:
                tab.posicionar_navio(codigo, tamanho, inicial, orientacao)
                break
            except ValueError as erro:
                print(f"[POSICIONAMENTO] {erro}")
    print("\nFrota posicionada:")
    tab.exibir()
    return tab