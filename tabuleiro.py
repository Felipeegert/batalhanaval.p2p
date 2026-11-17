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


@dataclass(frozen=True)
class Navio:
    codigo: str
    tamanho: int
    inicial: str
    orientacao: str
    casas: tuple[str, ...]


class Tabuleiro:
    def __init__(self):
        self.grade = [["." for _ in range(TAMANHO)] for _ in range(TAMANHO)]
        self.navios: list[Navio] = []

    @staticmethod
    def coordenada_para_indices(coordenada: str) -> tuple[int, int]:
        coordenada = coordenada.strip().upper()
        if len(coordenada) < 2 or coordenada[0] not in LINHAS:
            raise ValueError("Coordenada inválida. Use A1 até J10 (exemplo: B7).")

        linha = LINHAS.index(coordenada[0])
        try:
            coluna = int(coordenada[1:]) - 1
        except ValueError as exc:
            raise ValueError("Coluna inválida. Use um número de 1 a 10.") from exc

        if not 0 <= coluna < TAMANHO:
            raise ValueError("Coluna fora do tabuleiro. Use de 1 a 10.")

        return linha, coluna

    @staticmethod
    def indices_para_coordenada(linha: int, coluna: int) -> str:
        return f"{LINHAS[linha]}{coluna + 1}"

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

        for casa in casas:
            linha, coluna = self.coordenada_para_indices(casa)
            if self.grade[linha][coluna] != ".":
                raise ValueError(f"A casa {casa} já está ocupada por outro navio.")

        navio = Navio(
            codigo=codigo,
            tamanho=tamanho,
            inicial=inicial.strip().upper(),
            orientacao=orientacao.strip().upper(),
            casas=casas,
        )

        for casa in casas:
            linha, coluna = self.coordenada_para_indices(casa)
            self.grade[linha][coluna] = codigo

        self.navios.append(navio)

    def exibir(self):
        print("\n       " + " ".join(f"{n:2}" for n in range(1, 11)))
        print("     +" + "---" * 10 + "+")
        for i, letra in enumerate(LINHAS):
            conteudo = " ".join(f"{celula:2}" for celula in self.grade[i])
            print(f"     {letra}|{conteudo}|")
        print("     +" + "---" * 10 + "+")
        print("     . = água / PA = porta-aviões / EN = encouraçado")
        print("     CR = cruzador / DE = destróier\n")

    def serializar_frota(self) -> str:
        """Gera os itens do formato definido pela turma: CODIGO:INICIAL:H|V."""
        return " ".join(
            f"{navio.codigo}:{navio.inicial}:{navio.orientacao}"
            for navio in self.navios
        )


def posicionar_frota() -> Tabuleiro:
    tabuleiro = Tabuleiro()
    print("\n=== POSICIONAMENTO DA FROTA ===")
    print("Informe a coordenada inicial e a orientação de cada navio.")
    print("H = horizontal (cresce para a direita); V = vertical (cresce para baixo).")

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