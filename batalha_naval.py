
import argparse
import socket
import sys

VERSAO_PROTOCOLO = "1"
TAMANHO_BUFFER = 4096


# ==========================================
# COMUNICACAO TCP
# ==========================================

class ConexaoTCP:

    def __init__(self, sock):
        self.sock = sock
        self.buffer = bytearray()

    def enviar(self, mensagem):

        if "\n" in mensagem or "\r" in mensagem:
            raise ValueError("Mensagem não pode conter quebra de linha.")

        dados = (mensagem + "\n").encode("utf-8")

        self.sock.sendall(dados)

    def receber(self):

        # Continua recebendo até encontrar uma quebra de linha.
        while b"\n" not in self.buffer:

            dados = self.sock.recv(TAMANHO_BUFFER)

            if not dados:
                raise ConnectionError("Conexão encerrada pelo outro jogador.")

            self.buffer.extend(dados)

        # Separa a primeira mensagem do restante.
        linha, restante = self.buffer.split(b"\n", 1)

        self.buffer = bytearray(restante)

        return linha.decode("utf-8").rstrip("\r")

    def fechar(self):

        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

        self.sock.close()


# ==========================================
# ESTABELECIMENTO DA CONEXAO
# ==========================================

def criar_conexao(args):

    # PAPEL DE ANFITRIAO
    if args.escutar is not None:

        servidor = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        servidor.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )

        try:

            servidor.bind(("0.0.0.0", args.escutar))

            servidor.listen(1)

            print(f"[REDE] Aguardando jogador na porta {args.escutar}...")

            sock, endereco = servidor.accept()

            print(f"[REDE] Conectado com {endereco[0]}:{endereco[1]}")

        finally:
            servidor.close()

    # PAPEL DE CONVIDADO
    else:

        sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        print(f"[REDE] Conectando a {args.conectar}:{args.porta}...")

        sock.connect((args.conectar, args.porta))

        print("[REDE] Conexão estabelecida.")

    sock.setsockopt(
        socket.IPPROTO_TCP,
        socket.TCP_NODELAY,
        1
    )

    return ConexaoTCP(sock)


# ==========================================
# PROTOCOLO OLA
# ==========================================

def apresentar_jogador(conexao, apelido):

    # Envia nossa identificação.
    conexao.enviar(
        f"OLA {VERSAO_PROTOCOLO} {apelido}"
    )

    # Recebe identificação do adversário.
    resposta = conexao.receber()

    partes = resposta.split(" ", 2)

    if len(partes) != 3 or partes[0] != "OLA":

        conexao.enviar("ERRO mensagem_inicial_invalida")

        raise ValueError("Mensagem OLA inválida.")

    versao = partes[1]
    oponente = partes[2]

    if versao != VERSAO_PROTOCOLO:

        conexao.enviar("ERRO versao_incompativel")

        raise ValueError("Versões incompatíveis.")

    if not oponente.strip():

        raise ValueError("Apelido inválido.")

    print(f"[PROTOCOLO] Jogando contra: {oponente}")

    return oponente


# ==========================================
# SINCRONIZACAO PRONTO
# ==========================================

def sincronizar_pronto(conexao):

    # Informa que estamos prontos.
    conexao.enviar("PRONTO")

    # Aguarda o outro jogador.
    resposta = conexao.receber()

    if resposta != "PRONTO":

        raise ValueError(
            f"Esperava PRONTO, mas recebeu: {resposta}"
        )

    print("[JOGO] Ambos os jogadores estão prontos!")


# ==========================================
# EXECUCAO PRINCIPAL
# ==========================================

def executar(args):

    conexao = None

    try:

        # Estabelece conexão TCP.
        conexao = criar_conexao(args)

        # Troca identificação.
        oponente = apresentar_jogador(
            conexao,
            args.apelido
        )

        # Sincroniza início.
        sincronizar_pronto(conexao)

        if args.escutar is not None:

            print("[JOGO] Você é o anfitrião.")
            print("[JOGO] Você começa atirando.")

        else:

            print(f"[JOGO] Você é o convidado.")
            print(f"[JOGO] {oponente} começa atirando.")

        print("\nComunicação TCP funcionando!")

        input("\nPressione ENTER para encerrar...")

        try:
            conexao.enviar("TCHAU")
        except OSError:
            pass

    except (OSError, ConnectionError, ValueError) as erro:

        print(f"[ERRO] {erro}", file=sys.stderr)

        return 1

    finally:

        if conexao is not None:
            conexao.fechar()

    print("[REDE] Conexão encerrada.")

    return 0


# ==========================================
# ARGUMENTOS DO TERMINAL
# ==========================================

def main():

    parser = argparse.ArgumentParser(
        description="Batalha Naval P2P sobre TCP"
    )

    papeis = parser.add_mutually_exclusive_group(
        required=True
    )

    papeis.add_argument(
        "--escutar",
        type=int,
        metavar="PORTA"
    )

    papeis.add_argument(
        "--conectar",
        metavar="IP"
    )

    parser.add_argument(
        "porta",
        nargs="?",
        type=int
    )

    parser.add_argument(
        "--apelido",
        required=True
    )

    args = parser.parse_args()

    if args.conectar is not None and args.porta is None:
        parser.error("Informe a porta do anfitrião.")

    if args.escutar is not None and args.porta is not None:
        parser.error("Não informe uma segunda porta ao escutar.")

    if args.escutar is not None and not (1 <= args.escutar <= 65535):
        parser.error("Porta inválida.")

    if args.conectar is not None and not (1 <= args.porta <= 65535):
        parser.error("Porta inválida.")

    if not args.apelido.strip() or " " in args.apelido:
        parser.error("O apelido deve ser uma palavra sem espaços.")

    return executar(args)


if __name__ == "__main__":
    main()
