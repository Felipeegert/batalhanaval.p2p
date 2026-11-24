import argparse
import socket
import sys
from dataclasses import dataclass

from tabuleiro import Tabuleiro, posicionar_frota, LINHAS, TAMANHO

VERSAO_PROTOCOLO = "1"
BUFFER = 4096


class ErroProtocolo(Exception):
    pass


@dataclass
class ConexaoTCP:
    sock: socket.socket
    buffer: bytearray

    @classmethod
    def criar(cls, sock):
        return cls(sock, bytearray())

    def enviar(self, mensagem: str):
        if "\n" in mensagem or "\r" in mensagem:
            raise ErroProtocolo("Mensagem não pode conter quebra de linha.")
        self.sock.sendall((mensagem + "\n").encode("utf-8"))

    def receber(self) -> str:
        while b"\n" not in self.buffer:
            bloco = self.sock.recv(BUFFER)
            if not bloco:
                raise ConnectionError("Conexão encerrada pelo outro jogador.")
            self.buffer.extend(bloco)
        linha, resto = self.buffer.split(b"\n", 1)
        self.buffer = bytearray(resto)
        try:
            return linha.decode("utf-8").rstrip("\r")
        except UnicodeDecodeError as exc:
            raise ErroProtocolo("Mensagem recebida não é UTF-8 válido.") from exc

    def fechar(self):
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()


def criar_conexao(args):
    if args.escutar is not None:
        servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            servidor.bind(("0.0.0.0", args.escutar))
            servidor.listen(1)
            print(f"[REDE] Aguardando conexão na porta {args.escutar}...")
            sock, endereco = servidor.accept()
            print(f"[REDE] Conectado a {endereco[0]}:{endereco[1]}.")
        finally:
            servidor.close()
    else:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(f"[REDE] Conectando a {args.conectar}:{args.porta}...")
        sock.connect((args.conectar, args.porta))
        print("[REDE] Conexão estabelecida.")
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    return ConexaoTCP.criar(sock)


def handshake(con, apelido):
    con.enviar(f"OLA {VERSAO_PROTOCOLO} {apelido}")
    msg = con.receber()
    partes = msg.split(" ", 2)
    if len(partes) != 3 or partes[0] != "OLA":
        con.enviar("ERRO mensagem_inicial_invalida")
        raise ErroProtocolo(f"Esperava OLA; recebeu {msg!r}.")
    if partes[1] != VERSAO_PROTOCOLO:
        con.enviar("ERRO versao_incompativel")
        raise ErroProtocolo(f"Versão incompatível: {partes[1]}.")
    if not partes[2].strip():
        raise ErroProtocolo("Apelido vazio recebido.")
    print(f"[PROTOCOLO] Jogando contra {partes[2]} (versão {partes[1]}).")
    return partes[2]


def sincronizar_pronto(con):
    con.enviar("PRONTO")
    resposta = con.receber()
    if resposta != "PRONTO":
        raise ErroProtocolo(f"Esperava PRONTO; recebeu {resposta!r}.")


def desenhar_tiros(tiros):
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
    print("     . não jogado | o água | X acerto")


def mostrar_painel(apelido, oponente, tabuleiro, tiros, minha_vez, seq):
    print("\n" + "=" * 58)
    print(f" BATALHA NAVAL  |  {apelido} vs {oponente}")
    print("=" * 58)
    print(f" SUA VEZ: {'SIM — escolha um alvo' if minha_vez else 'NÃO — aguardando oponente'}")
    print(f" Próximo número de tiro enviado: {seq + 1}")
    print("\n[1] SEU TABULEIRO — navios e tiros recebidos")
    tabuleiro.exibir(mostrar_navios=True)
    print("\n[2] TABULEIRO DO OPONENTE — seus tiros")
    desenhar_tiros(tiros)
    print("Legenda: PA porta-aviões | EN encouraçado | CR cruzador | DE destróier")
    print("         o água | X acerto | . desconhecido")
    print("=" * 58)


def interpretar_resultado(msg, seq_esperado):
    p = msg.split()
    if len(p) < 3 or p[0] != "RESULTADO":
        raise ErroProtocolo(f"Esperava RESULTADO; recebeu {msg!r}.")
    try:
        seq = int(p[1])
    except ValueError as exc:
        raise ErroProtocolo("Sequência inválida em RESULTADO.") from exc
    if seq != seq_esperado:
        raise ErroProtocolo(f"RESULTADO seq {seq}; esperado {seq_esperado}.")
    if p[2] in ("AGUA", "ACERTOU") and len(p) == 3:
        return p[2], False
    if p[2] == "AFUNDOU" and len(p) in (4, 5):
        if len(p) == 5 and p[4] != "FIM":
            raise ErroProtocolo("Sufixo inválido em RESULTADO.")
        return f"AFUNDOU {p[3]}", len(p) == 5
    raise ErroProtocolo(f"RESULTADO inválido: {msg!r}.")


def trocar_frotas(con, tabuleiro):
    con.enviar(f"FROTA {tabuleiro.serializar_frota()}")
    resposta = con.receber()
    if not resposta.startswith("FROTA "):
        raise ErroProtocolo(f"Esperava FROTA; recebeu {resposta!r}.")
    print("\n[CONFERÊNCIA] Frota recebida do adversário:")
    print(resposta[6:])
    print("[CONFERÊNCIA] Tua frota:")
    print(tabuleiro.serializar_frota())


def jogar(con, apelido, oponente, tabuleiro, anfitriao):
    minha_vez = anfitriao
    seq_enviado = 0
    seq_recebido = 1
    tiros_feitos = set()
    tiros_oponente = {}

    while True:
        mostrar_painel(apelido, oponente, tabuleiro, tiros_oponente, minha_vez, seq_enviado)

        if minha_vez:
            print("\n[AÇÃO] Digite uma coordenada (A1 a J10). Comandos: ajuda, sair.")
            while True:
                coord = input("Seu tiro > ").strip().upper()
                if coord.lower() == "SAIR":
                    con.enviar("TCHAU")
                    print("[JOGO] Você encerrou a partida.")
                    return
                if coord.lower() == "AJUDA":
                    print("Escolha uma casa ainda não atingida do tabuleiro adversário.")
                    continue
                try:
                    coord = tabuleiro.normalizar_coordenada(coord)
                except ValueError as exc:
                    print(f"[ENTRADA INVÁLIDA] {exc}")
                    continue
                if coord in tiros_feitos:
                    print("[ENTRADA INVÁLIDA] Você já atirou nessa coordenada.")
                    continue
                break

            seq_enviado += 1
            tiros_feitos.add(coord)
            con.enviar(f"TIRO {seq_enviado} {coord}")
            print(f"[ENVIO] TIRO {seq_enviado} {coord}")
            resposta = con.receber()
            if resposta == "TCHAU":
                print("[JOGO] O adversário encerrou a partida.")
                return
            if resposta.startswith("ERRO "):
                print(f"[PROTOCOLO] O adversário rejeitou o tiro: {resposta[5:]}")
                tiros_feitos.discard(coord)
                seq_enviado -= 1
                continue
            resultado, fim = interpretar_resultado(resposta, seq_enviado)
            tiros_oponente[coord] = resultado
            print(f"\n[RESULTADO] {coord}: {resultado}")
            if resultado == "AGUA":
                print("O tiro caiu na água.")
            elif resultado == "ACERTOU":
                print("Você atingiu um navio!")
            else:
                print(f"Você afundou um navio: {resultado.split()[1]}!")
            if fim:
                print("\n*** VITÓRIA! Você afundou toda a frota adversária! ***")
                trocar_frotas(con, tabuleiro)
                return
            input("\nPressione ENTER para atualizar o painel...")
            minha_vez = False

        else:
            print("\n[AGUARDANDO] É a vez do adversário. Aguardando TIRO...")
            msg = con.receber()
            if msg == "TCHAU":
                print("[JOGO] O adversário encerrou a partida.")
                return
            if not msg.startswith("TIRO "):
                con.enviar("ERRO mensagem_inesperada")
                print(f"[ERRO] Mensagem inesperada: {msg}")
                continue
            p = msg.split()
            if len(p) != 3:
                con.enviar("ERRO formato_tiro_invalido")
                continue
            try:
                seq = int(p[1])
            except ValueError:
                con.enviar("ERRO sequencia_invalida")
                continue
            if seq != seq_recebido:
                con.enviar("ERRO sequencia_fora_de_ordem")
                continue
            coord = p[2].upper()
            try:
                resultado, fim = tabuleiro.registrar_tiro(coord)
            except ValueError as exc:
                con.enviar("ERRO coordenada_invalida_ou_repetida")
                print(f"[TIRO REJEITADO] {exc}")
                continue
            seq_recebido += 1
            resposta = f"RESULTADO {seq} {resultado}" + (" FIM" if fim else "")
            con.enviar(resposta)
            print(f"\n[TIRO RECEBIDO] {coord} — {resultado}")
            if resultado == "AGUA":
                print("O adversário errou: água.")
            elif resultado == "ACERTOU":
                print("Seu navio foi atingido!")
            else:
                print(f"Seu navio {resultado.split()[1]} foi afundado!")
            tabuleiro.exibir(mostrar_navios=True)
            if fim:
                print("\n*** DERROTA! Toda sua frota foi afundada. ***")
                trocar_frotas(con, tabuleiro)
                return
            input("\nPressione ENTER para passar o controle...")
            minha_vez = True


def executar(args):
    con = None
    try:
        con = criar_conexao(args)
        oponente = handshake(con, args.apelido)
        tabuleiro = posicionar_frota()
        print("\n[STATUS] Frota pronta. Aguardando o outro jogador...")
        sincronizar_pronto(con)
        print("[STATUS] Ambos estão prontos. Partida iniciada!")
        jogar(con, args.apelido, oponente, tabuleiro, args.escutar is not None)
    except (OSError, ConnectionError, ErroProtocolo) as exc:
        print(f"\n[ERRO DE REDE/PROTOCOLO] {exc}", file=sys.stderr)
        return 1
    finally:
        if con:
            con.fechar()
    print("[REDE] Conexão encerrada.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Batalha Naval P2P sobre TCP — etapa 4.")
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--escutar", type=int, metavar="PORTA")
    grupo.add_argument("--conectar", metavar="IP")
    parser.add_argument("porta", nargs="?", type=int)
    parser.add_argument("--apelido", required=True)
    args = parser.parse_args()
    if args.conectar is not None and args.porta is None:
        parser.error("informe a PORTA depois do IP")
    if args.escutar is not None and args.porta is not None:
        parser.error("não informe uma segunda porta com --escutar")
    porta = args.escutar if args.escutar is not None else args.porta
    if not 1 <= porta <= 65535:
        parser.error("porta deve estar entre 1 e 65535")
    if not args.apelido or " " in args.apelido:
        parser.error("apelido deve ser uma palavra sem espaços")
    raise SystemExit(executar(args))


if __name__ == "__main__":
    main()
