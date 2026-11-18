from dataclasses import dataclass

TAMANHO = 10
LINHAS = "ABCDEFGHIJ"

FROTA = [
    ("PA", 5),
    ("EN", 4),
    ("CR", 3),
    ("CR", 3),
    ("DE", 2),
    ("DE", 2),
]


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
        # Cada célula guarda o índice do navio que ocupa a posição, ou None.
        self.grade = [[None for _ in range(TAMANHO)] for _ in range(TAMANHO)]
        self.navios: list[Navio] = []
        self.tiros_recebidos: dict[str, str] = {}

    @staticmethod
    def coordenada_para_indices(coordenada: str) -> tuple[int, int]:
        coordenada = coordenada.strip().upper()
        if len(coordenada) < 2 or coordenada[0] not in LINHAS:
            raise ValueError("Coordenada inválida. Use A1 até J10 (exemplo: B7).")
        try:
            coluna = int(coordenada[1:]) - 1
        except ValueError as exc:
            raise ValueError("Coluna inválida. Use um número de 1 a 10.") from exc
        if not 0 <= coluna < TAMANHO:
            raise ValueError("Coluna fora do tabuleiro. Use de 1 a 10.")
        return LINHAS.index(coordenada[0]), coluna

    @staticmethod
    def indices_para_coordenada(linha: int, coluna: int) -> str:
        return f"{LINHAS[linha]}{coluna + 1}"

    def normalizar_coordenada(self, coordenada: str) -> str:
        linha, coluna = self.coordenada_para_indices(coordenada)
        return self.indices_para_coordenada(linha, coluna)

    def calcular_casas(self, inicial: str, orientacao: str, tamanho: int) -> tuple[str, ...]:
        linha, coluna = self.coordenada_para_indices(inicial)
        orientacao = orientacao.strip().upper()
        if orientacao not in ("H", "V"):
            raise ValueError("Orientação inválida. Digite H (horizontal) ou V (vertical).")

        casas = []
        for deslocamento in range(tamanho):
            nova_linha = linha + (deslocamento if orientacao == "V" else 0)
            nova_coluna = coluna + (deslocamento if orientacao == "H" else 0)
            if nova_linha >= TAMANHO or nova_coluna >= TAMANHO:
                raise ValueError("O navio ultrapassa os limites do tabuleiro.")
            casas.append(self.indices_para_coordenada(nova_linha, nova_coluna))
        return tuple(casas)

    def posicionar_navio(self, codigo: str, tamanho: int, inicial: str, orientacao: str):
        casas = self.calcular_casas(inicial, orientacao, tamanho)
        if any(
            self.grade[self.coordenada_para_indices(c)[0]][self.coordenada_para_indices(c)[1]]
            is not None
            for c in casas
        ):
            raise ValueError("Uma ou mais casas já estão ocupadas por outro navio.")

        indice_navio = len(self.navios)
        navio = Navio(
            codigo=codigo,
            tamanho=tamanho,
            inicial=self.normalizar_coordenada(inicial),
            orientacao=orientacao.strip().upper(),
            casas=casas,
            acertos=set(),
        )
        self.navios.append(navio)
        for casa in casas:
            linha, coluna = self.coordenada_para_indices(casa)
            self.grade[linha][coluna] = indice_navio

    def esta_completo(self) -> bool:
        return len(self.navios) == len(FROTA)

    def validar_coordenada_tiro(self, coordenada: str) -> str:
        coordenada = self.normalizar_coordenada(coordenada)
        if coordenada in self.tiros_recebidos:
            raise ValueError(f"A casa {coordenada} já recebeu um tiro.")
        return coordenada

    def registrar_tiro(self, coordenada: str) -> tuple[str, bool]:
        """Retorna (resultado, fim). resultado: AGUA, ACERTOU ou AFUNDOU CODIGO."""
        coordenada = self.validar_coordenada_tiro(coordenada)
        linha, coluna = self.coordenada_para_indices(coordenada)
        indice_navio = self.grade[linha][coluna]

        if indice_navio is None:
            self.tiros_recebidos[coordenada] = "AGUA"
            return "AGUA", False

        navio = self.navios[indice_navio]
        navio.acertos.add(coordenada)
        if len(navio.acertos) == navio.tamanho:
            self.tiros_recebidos[coordenada] = f"AFUNDOU {navio.codigo}"
            fim = all(len(n.acertos) == n.tamanho for n in self.navios)
            return f"AFUNDOU {navio.codigo}", fim

        self.tiros_recebidos[coordenada] = "ACERTOU"
        return "ACERTOU", False

    def exibir(self, mostrar_navios=True):
        print("\n       " + " ".join(f"{n:2}" for n in range(1, 11)))
        print("     +" + "---" * 10 + "+")
        for i, letra in enumerate(LINHAS):
            celulas = []
            for j in range(TAMANHO):
                indice = self.grade[i][j]
                coord = self.indices_para_coordenada(i, j)
                if coord in self.tiros_recebidos:
                    marca = "o" if self.tiros_recebidos[coord] == "AGUA" else "X"
                elif indice is not None and mostrar_navios:
                    marca = self.navios[indice].codigo
                else:
                    marca = "."
                celulas.append(f"{marca:2}")
            print(f"     {letra}|" + " ".join(celulas) + "|")
        print("     +" + "---" * 10 + "+")
        print("     . = desconhecido/vazio | o = tiro na água | X = navio atingido")
        if mostrar_navios:
            print("     PA = porta-aviões | EN = encouraçado | CR = cruzador | DE = destróier")
        print()

    def serializar_frota(self) -> str:
        return " ".join(
            f"{n.codigo}:{n.inicial}:{n.orientacao}" for n in self.navios
        )


def posicionar_frota() -> Tabuleiro:
    tabuleiro = Tabuleiro()
    print("\n=== POSICIONAMENTO DA FROTA ===")
    print("H = horizontal (para a direita); V = vertical (para baixo).")
    for numero, (codigo, tamanho) in enumerate(FROTA, start=1):
        while True:
            tabuleiro.exibir()
            print(f"Navio {numero}/{len(FROTA)}: {codigo} ({tamanho} casas)")
            inicial = input("Casa inicial (ex.: B7): ").strip()
            orientacao = input("Orientação (H/V): ").strip()
            try:
                tabuleiro.posicionar_navio(codigo, tamanho, inicial, orientacao)
                break
            except ValueError as erro:
                print(f"[POSICIONAMENTO] {erro} Tente novamente.\n")
    tabuleiro.exibir()
    print("[JOGO] Frota posicionada com sucesso.")
    return tabuleiro