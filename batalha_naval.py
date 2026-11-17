import argparse
import socket
import sys
from dataclasses import dataclass

from tabuleiro import posicionar_frota

VERSAO_PROTOCOLO = "1"
CODIFICACAO = "utf-8"
TAMANHO_BUFFER = 4096


class ErroProtocolo(Exception):
    pass


@dataclass
class ConexaoTCP:
    """Camada de transporte: transforma o fluxo TCP em mensagens terminadas em LF."""

    sock: socket.socket
    buffer: bytearray

    @classmethod
    def criar(cls, sock):
        return cls(sock=sock, buffer=bytearray())

    def enviar(self, mensagem: str) -> None:
        if "\n" in mensagem or "\r" in mensagem:
            raise ErroProtocolo("Uma mensagem não pode conter quebras de linha.")
        self.sock.sendall((mensagem + "\n").encode(CODIFICACAO))

    def receber(self) -> str:
        while b"\n" not in self.buffer:
            bloco = self.sock.recv(TAMANHO_BUFFER)
            if not bloco:
                raise ConnectionError("O outro jogador encerrou a conexão.")
            self.buffer.extend(bloco)

        linha, restante = self.buffer.split(b"\n", 1)
        self.buffer = bytearray(restante)

        try:
            return linha.decode(CODIFICACAO).rstrip("\r")
        except UnicodeDecodeError as exc:
            raise ErroProtocolo("Mensagem recebida não está em UTF-8.") from exc

    def fechar(self):
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()


def criar_conexao(args) -> ConexaoTCP:
    if args.escutar is not None:
        servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            servidor.bind(("0.0.0.0", args.escutar))
            servidor.listen(1)
            print(f"[REDE] Aguardando um jogador na porta {args.escutar}...")
            sock, endereco = servidor.accept()
            print(f"[REDE] Conectado com {endereco[0]}:{endereco[1]}")
        finally:
            servidor.close()
    else:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(f"[REDE] Conectando a {args.conectar}:{args.porta}...")
        sock.connect((args.conectar, args.porta))
        print("[REDE] Conexão estabelecida.")

    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    return ConexaoTCP.criar(sock)


def apresentar_e_validar_protocolo(conexao: ConexaoTCP, apelido: str):
    conexao.enviar(f"OLA {VERSAO_PROTOCOLO} {apelido}")
    resposta = conexao.receber()
    partes = resposta.split(" ", 2)

    if len(partes) != 3 or partes[0] != "OLA":
        conexao.enviar("ERRO mensagem_inicial_invalida")
        raise ErroProtocolo(f"Esperava OLA, mas recebeu: {resposta!r}")

    if partes[1] != VERSAO_PROTOCOLO:
        conexao.enviar("ERRO versao_incompativel")
        raise ErroProtocolo(
            f"Versão incompatível: colega usa {partes[1]}, "
            f"esta implementação usa {VERSAO_PROTOCOLO}."
        )

    apelido_oponente = partes[2].strip()
    if not apelido_oponente:
        raise ErroProtocolo("O colega enviou um apelido vazio.")

    print(f"[PROTOCOLO] Oponente: {apelido_oponente} (versão {partes[1]}).")
    return apelido_oponente


def sincronizar_pronto(conexao: ConexaoTCP):
    conexao.enviar("PRONTO")
    resposta = conexao.receber()

    if resposta != "PRONTO":
        raise ErroProtocolo(f"Esperava PRONTO, mas recebeu: {resposta!r}")

    print("[JOGO] Os dois jogadores enviaram PRONTO. A partida pode começar.")


def executar(args):
    conexao = None
    try:
        conexao = criar_conexao(args)
        oponente = apresentar_e_validar_protocolo(conexao, args.apelido)

        # Cada jogador monta a própria frota localmente. Nenhuma posição é enviada.
        tabuleiro = posicionar_frota()

        # PRONTO só é enviado depois de concluir o posicionamento.
        sincronizar_pronto(conexao)

        if args.escutar is not None:
            print("[JOGO] Tu és o anfitrião. O primeiro tiro será teu.")
        else:
            print(f"[JOGO] Tu és o convidado. {oponente} atira primeiro.")

        print(f"[DEBUG] Frota local: {tabuleiro.serializar_frota()}")
        print("[JOGO] Etapa 2 concluída: tabuleiro e frota posicionados.")

        input("\nPressione ENTER para encerrar a conexão...")
        try:
            conexao.enviar("TCHAU")
        except OSError:
            pass

    except (OSError, ConnectionError, ErroProtocolo) as exc:
        print(f"[ERRO] {exc}", file=sys.stderr)
        return 1
    finally:
        if conexao is not None:
            conexao.fechar()

    print("[REDE] Conexão encerrada.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Batalha Naval P2P sobre TCP."
    )
    papel = parser.add_mutually_exclusive_group(required=True)
    papel.add_argument("--escutar", type=int, metavar="PORTA")
    papel.add_argument("--conectar", metavar="IP")
    parser.add_argument("porta", nargs="?", type=int)
    parser.add_argument("--apelido", required=True)
    args = parser.parse_args()

    if args.conectar is not None and args.porta is None:
        parser.error("informe a PORTA depois do IP ao usar --conectar")
    if args.escutar is not None and args.porta is not None:
        parser.error("não informe uma segunda porta junto com --escutar")
    porta = args.escutar if args.escutar is not None else args.porta
    if not 1 <= porta <= 65535:
        parser.error("porta deve estar entre 1 e 65535")
    if not args.apelido.strip() or " " in args.apelido:
        parser.error("apelido deve ser uma palavra sem espaços")

    raise SystemExit(executar(args))


if __name__ == "__main__":
    main()
