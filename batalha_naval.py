import argparse
import socket
import sys
from dataclasses import dataclass

from tabuleiro import Tabuleiro, posicionar_frota

VERSAO_PROTOCOLO = "1"
CODIFICACAO = "utf-8"
TAMANHO_BUFFER = 4096


class ErroProtocolo(Exception):
    pass


@dataclass
class ConexaoTCP:
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
        raise ErroProtocolo(f"Versão incompatível: {partes[1]}.")
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
    print("[JOGO] Ambos enviaram PRONTO. A partida vai começar.")


def interpretar_resultado(mensagem: str, seq_esperado: int):
    partes = mensagem.split()
    if len(partes) < 3 or partes[0] != "RESULTADO":
        raise ErroProtocolo(f"Esperava RESULTADO, recebeu: {mensagem!r}")
    try:
        seq = int(partes[1])
    except ValueError as exc:
        raise ErroProtocolo("Número de sequência inválido no RESULTADO.") from exc
    if seq != seq_esperado:
        raise ErroProtocolo(
            f"RESULTADO com seq {seq}; era esperado seq {seq_esperado}."
        )

    if partes[2] == "AGUA" and len(partes) == 3:
        return "AGUA", False
    if partes[2] == "ACERTOU" and len(partes) == 3:
        return "ACERTOU", False
    if partes[2] == "AFUNDOU" and len(partes) in (4, 5):
        fim = len(partes) == 5 and partes[4] == "FIM"
        if len(partes) == 5 and not fim:
            raise ErroProtocolo("Sufixo inválido no RESULTADO.")
        return f"AFUNDOU {partes[3]}", fim
    raise ErroProtocolo(f"Conteúdo inválido no RESULTADO: {mensagem!r}")


def trocar_frotas_no_fim(conexao: ConexaoTCP, tabuleiro: Tabuleiro):
    # A troca está prevista no protocolo e ocorre somente depois do FIM.
    conexao.enviar(f"FROTA {tabuleiro.serializar_frota()}")
    resposta = conexao.receber()
    if not resposta.startswith("FROTA "):
        raise ErroProtocolo(f"Esperava FROTA no encerramento, recebeu: {resposta!r}")
    print(f"[CONFERÊNCIA] Frota informada pelo oponente: {resposta[6:]}")
    print(f"[CONFERÊNCIA] Tua frota: {tabuleiro.serializar_frota()}")
    print("[CONFERÊNCIA] A comparação detalhada das frotas será implementada na etapa 5.")


def jogar(conexao: ConexaoTCP, tabuleiro: Tabuleiro, anfitriao: bool):
    minha_vez = anfitriao
    seq_enviado = 0
    proximo_seq_recebido = 1
    tiros_feitos: set[str] = set()
    tiros_oponente: dict[str, str] = {}

    print("\n=== PARTIDA INICIADA ===")
    print("Tu podes digitar 'sair' para encerrar a partida.")
    while True:
        if minha_vez:
            print("\n[VEZ] É tua vez de atirar.")
            print("Teus tiros no tabuleiro adversário:")
            exibir_tabuleiro_tiros(tiros_oponente)
            while True:
                coordenada = input("Coordenada para disparar (ex.: B7): ").strip().upper()
                if coordenada.lower() == "sair":
                    conexao.enviar("TCHAU")
                    print("[JOGO] Tu encerraste a partida.")
                    return
                try:
                    # Reutiliza a validação de coordenadas do tabuleiro.
                    coordenada = tabuleiro.normalizar_coordenada(coordenada)
                except ValueError as erro:
                    print(f"[TIRO] {erro}")
                    continue
                if coordenada in tiros_feitos:
                    print(f"[TIRO] Tu já disparaste em {coordenada}. Escolhe outra casa.")
                    continue
                break

            seq_enviado += 1
            tiros_feitos.add(coordenada)
            conexao.enviar(f"TIRO {seq_enviado} {coordenada}")
            print(f"[REDE] Enviado: TIRO {seq_enviado} {coordenada}")

            resposta = conexao.receber()
            if resposta.startswith("ERRO "):
                print(f"[PROTOCOLO] O oponente rejeitou o tiro: {resposta[5:]}")
                # A etapa de confiabilidade tratará a recuperação de seq/tiro.
                tiros_feitos.discard(coordenada)
                seq_enviado -= 1
                continue
            resultado, fim = interpretar_resultado(resposta, seq_enviado)
            tiros_oponente[coordenada] = resultado
            print(f"[RESULTADO] Tiro em {coordenada}: {resultado}")
            if fim:
                print("\n🎉 Tu venceste! Toda a frota adversária foi afundada.")
                trocar_frotas_no_fim(conexao, tabuleiro)
                return
            minha_vez = False

        else:
            print("\n[VEZ] Aguardando o tiro do oponente...")
            mensagem = conexao.receber()
            if mensagem == "TCHAU":
                print("[JOGO] O oponente encerrou a conexão.")
                return
            if not mensagem.startswith("TIRO "):
                conexao.enviar("ERRO mensagem_inesperada")
                print(f"[PROTOCOLO] Mensagem inesperada: {mensagem}")
                continue

            partes = mensagem.split()
            if len(partes) != 3:
                conexao.enviar("ERRO formato_tiro_invalido")
                continue
            try:
                seq_recebido = int(partes[1])
            except ValueError:
                conexao.enviar("ERRO sequencia_invalida")
                continue

            if seq_recebido != proximo_seq_recebido:
                conexao.enviar("ERRO sequencia_fora_de_ordem")
                print("[PROTOCOLO] Número de sequência inesperado.")
                continue

            coordenada = partes[2].upper()
            try:
                resultado, fim = tabuleiro.registrar_tiro(coordenada)
            except ValueError as erro:
                conexao.enviar("ERRO coordenada_invalida_ou_repetida")
                print(f"[TIRO] Tiro rejeitado: {erro}")
                continue

            proximo_seq_recebido += 1
            resposta = f"RESULTADO {seq_recebido} {resultado}"
            if fim:
                resposta += " FIM"
            conexao.enviar(resposta)
            print(f"[REDE] Recebido: TIRO {seq_recebido} {coordenada}")
            print(f"[RESULTADO] Teu tabuleiro: {coordenada} -> {resultado}")
            tabuleiro.exibir()

            if fim:
                print("\n[DERROTA] Toda a tua frota foi afundada.")
                trocar_frotas_no_fim(conexao, tabuleiro)
                return
            minha_vez = True


def exibir_tabuleiro_tiros(tiros: dict[str, str]):
    from tabuleiro import LINHAS, TAMANHO
    print("       " + " ".join(f"{n:2}" for n in range(1, 11)))
    print("     +" + "---" * 10 + "+")
    for i, letra in enumerate(LINHAS):
        celulas = []
        for j in range(TAMANHO):
            coord = f"{letra}{j+1}"
            resultado = tiros.get(coord)
            marca = "." if resultado is None else ("o" if resultado == "AGUA" else "X")
            celulas.append(f"{marca:2}")
        print(f"     {letra}|" + " ".join(celulas) + "|")
    print("     +" + "---" * 10 + "+")
    print("     . = ainda não atingido | o = água | X = acerto/afundado")


def executar(args):
    conexao = None
    try:
        conexao = criar_conexao(args)
        oponente = apresentar_e_validar_protocolo(conexao, args.apelido)
        tabuleiro = posicionar_frota()
        sincronizar_pronto(conexao)
        if args.escutar is not None:
            print("[JOGO] Tu és o anfitrião. Começas atirando.")
        else:
            print(f"[JOGO] Tu és o convidado. {oponente} começa atirando.")
        jogar(conexao, tabuleiro, anfitriao=(args.escutar is not None))
    except (OSError, ConnectionError, ErroProtocolo) as exc:
        print(f"[ERRO] {exc}", file=sys.stderr)
        return 1
    finally:
        if conexao is not None:
            conexao.fechar()
    print("[REDE] Conexão encerrada.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Batalha Naval P2P sobre TCP.")
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
