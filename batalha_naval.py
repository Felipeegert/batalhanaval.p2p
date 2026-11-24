import argparse
import socket
import sys
import time
import threading
import queue
import re
from collections import Counter
from dataclasses import dataclass

from tabuleiro import Tabuleiro, posicionar_frota, LINHAS, TAMANHO, FROTA

VERSAO_PROTOCOLO = "1"
BUFFER = 4096
TIMEOUT = 5
RECONEXAO = 60
MAX_REENVIOS = 3


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


def criar_conexao(args, limite=None):
    if args.escutar is not None:
        servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            servidor.bind(("0.0.0.0", args.escutar))
            servidor.listen(1)
            servidor.settimeout(limite)
            print(f"[REDE] Aguardando conexão na porta {args.escutar}...")
            sock, endereco = servidor.accept()
            print(f"[REDE] Conectado a {endereco[0]}:{endereco[1]}.")
        finally:
            servidor.close()
    else:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(f"[REDE] Conectando a {args.conectar}:{args.porta}...")
        sock.settimeout(limite)
        try:
            sock.connect((args.conectar, args.porta))
        except OSError:
            sock.close()
            raise
        print("[REDE] Conexão estabelecida.")
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    sock.settimeout(None)
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
    if p[2] == "AFUNDOU" and len(p) in (4, 5) and p[3] in dict(FROTA):
        if len(p) == 5 and p[4] != "FIM":
            raise ErroProtocolo("Sufixo inválido em RESULTADO.")
        return f"AFUNDOU {p[3]}", len(p) == 5
    raise ErroProtocolo(f"RESULTADO inválido: {msg!r}.")


def conferir_frota(mensagem, historico):
    """Reconstrói a frota e reproduz tiros em ordem de sequência."""
    try:
        p = mensagem.split()
        if not p or p[0] != "FROTA":
            raise ValueError("Esperava FROTA")
        tab = Tabuleiro()
        codigos = []
        for item in p[1:]:
            codigo, casa, orientacao = item.split(":")
            if codigo not in dict(FROTA) or not re.fullmatch(r"[A-J](10|[1-9])", casa) or orientacao not in ("H", "V"):
                raise ValueError("Navio inválido: " + item)
            tab.posicionar_navio(codigo, dict(FROTA)[codigo], casa, orientacao)
            codigos.append(codigo)
        if Counter(codigos) != Counter(c for c, _ in FROTA):
            raise ValueError("Composição incorreta da frota")
        erros = []
        for seq, (coord, resultado, fim) in sorted(historico.items()):
            esperado = tab.registrar_tiro(coord)
            if esperado != (resultado, fim):
                erros.append(f"Tiro {seq} {coord}: esperado {esperado}, recebido {(resultado, fim)}")
        return erros
    except ValueError as exc:
        return [str(exc)]


class Partida:
    def __init__(self, con, args, oponente, tabuleiro):
        self.con, self.args, self.oponente, self.tab = con, args, oponente, tabuleiro
        self.minha_vez = args.escutar is not None
        self.enviado = 0
        self.cache = {}  # seq -> (coordenada, mensagem RESULTADO)
        self.historico = {}  # seq -> (coordenada, resultado, fim)
        self.tiros = {}
        self.pendente = None
        self.prazo = 0
        self.reenvios = 0
        self.fim = False
        self.frota_recebida = False
        self.frota_enviada = False
        self.encerrado = False
        self.entrada = queue.Queue()
        self.lendo = False

    def enviar(self, msg):
        self.con.enviar(msg)
        print("[ENVIO]", msg)

    def erro(self, motivo):
        self.enviar("ERRO " + motivo)

    def tiro_recebido(self, p):
        if len(p) != 3 or not p[1].isdigit() or len(p[1]) > 3 or not re.fullmatch(r"[A-J](10|[1-9])", p[2]):
            self.erro("formato_tiro_invalido")
            return
        seq, coord = int(p[1]), p[2]
        # Consultar cache ANTES de verificar o turno: uma retransmissão
        # legítima pode chegar quando já é nossa vez de jogar.
        if seq in self.cache:
            anterior, resposta = self.cache[seq]
            if coord != anterior:
                self.erro("sequencia_reutilizada")
            else:
                self.enviar(resposta)
            return
        if self.minha_vez or self.pendente or self.fim:
            self.erro("fora_de_turno")
            return
        if seq != len(self.cache) + 1:
            self.erro("sequencia_fora_de_ordem")
            return
        try:
            resultado, fim = self.tab.registrar_tiro(coord)
        except ValueError:
            self.erro("coordenada_invalida_ou_repetida")
            return
        resposta = f"RESULTADO {seq} {resultado}" + (" FIM" if fim else "")
        # Registrar antes de enviar, para sobreviver a falha no sendall.
        self.cache[seq] = (coord, resposta)
        self.minha_vez = not fim
        self.fim = fim
        print(f"[TIRO RECEBIDO] {coord}: {resultado}")
        self.enviar(resposta)
        if fim:
            print("[DERROTA] Frota afundada.")

    def resultado_recebido(self, p, msg):
        if len(p) < 2 or not p[1].isdigit() or len(p[1]) > 3:
            self.erro("resultado_invalido")
            return
        seq = int(p[1])
        try:
            resultado, fim = interpretar_resultado(msg, seq)
        except ErroProtocolo:
            self.erro("resultado_invalido")
            return
        if seq in self.historico:
            if self.historico[seq][1:] != (resultado, fim):
                self.erro("resultado_divergente")
            return
        if not self.pendente or seq != self.pendente[0]:
            self.erro("resultado_fora_de_ordem")
            return
        coord = self.pendente[1]
        self.historico[seq] = (coord, resultado, fim)
        self.tiros[coord] = resultado
        self.pendente = None
        self.minha_vez = False
        self.fim = fim
        print(f"[RESULTADO] {coord}: {resultado}")
        if fim:
            print("[VITÓRIA] Frota adversária afundada.")

    def processar(self, msg):
        p = msg.split()
        tipo = p[0] if p else ""
        if tipo == "TIRO":
            self.tiro_recebido(p)
        elif tipo == "RESULTADO":
            self.resultado_recebido(p, msg)
        elif tipo == "FROTA" and self.fim:
            erros = conferir_frota(msg, self.historico)
            print("[CONFERÊNCIA] " + ("; ".join(erros) if erros else "Frota coerente com todos os tiros."))
            self.frota_recebida = True
        elif msg == "TCHAU":
            self.encerrado = True
        elif tipo == "ERRO":
            print("[PEER]", msg)
            # Não reutilizar uma sequência cujo processamento é incerto.
            # O temporizador repetirá o tiro pendente, se houver.
        else:
            self.erro("mensagem_inesperada")

    def disparar(self, coord):
        self.enviado += 1
        self.pendente = (self.enviado, coord)
        self.reenvios = 0
        self.prazo = time.monotonic() + TIMEOUT
        self.enviar(f"TIRO {self.enviado} {coord}")

    def solicitar_entrada(self):
        self.lendo = True
        def ler():
            try:
                self.entrada.put(input("Seu tiro (ou ajuda/sair) > "))
            except (EOFError, OSError):
                self.entrada.put("sair")
        threading.Thread(target=ler, daemon=True).start()

    def reconectar(self):
        print("[PAUSADO] Conexão perdida. Tentando retomar por até 60 segundos.")
        self.con.fechar()
        limite = time.monotonic() + RECONEXAO
        while time.monotonic() < limite:
            nova = None
            try:
                restante = limite - time.monotonic()
                nova = criar_conexao(self.args, limite=min(3, restante))
                nova.sock.settimeout(min(TIMEOUT, max(0.1, limite-time.monotonic())))
                nova.enviar(f"RETOMAR {self.enviado} {len(self.cache)}")
                p = nova.receber().split()
                if len(p) != 3 or p[0] != "RETOMAR" or not all(x.isdigit() and len(x) <= 3 for x in p[1:]):
                    nova.enviar("ERRO retomar_invalido")
                    raise ErroProtocolo("RETOMAR inválido")
                enviados_peer, recebidos_peer = map(int, p[1:])
                if not (len(self.historico) <= recebidos_peer <= self.enviado and len(self.cache) <= enviados_peer <= len(self.cache)+1):
                    nova.enviar("ERRO estado_incompativel")
                    raise ErroProtocolo("Estado incompatível")
                self.con = nova
                # Se o peer já recebeu nosso tiro, ele reenvia seu resultado
                # em cache quando repetirmos a solicitação. Se não, processa.
                if self.pendente:
                    seq, coord = self.pendente
                    self.enviar(f"TIRO {seq} {coord}")
                    self.prazo = time.monotonic() + TIMEOUT
                    self.reenvios = 0
                # A frota pode ter sido perdida junto com a conexão.
                self.frota_enviada = False
                nova.sock.settimeout(0.2)
                print("[REDE] Partida retomada.")
                return
            except (OSError, ErroProtocolo) as exc:
                if nova:
                    nova.fechar()
                print("[REDE] Tentativa sem sucesso:", exc)
                time.sleep(min(1, max(0, limite-time.monotonic())))
        raise ConnectionError("Prazo de reconexão esgotado.")

    def rodar(self):
        self.con.sock.settimeout(0.2)
        try:
            while not self.encerrado:
                try:
                    self.passo()
                except (OSError, ConnectionError):
                    self.reconectar()
        finally:
            self.con.fechar()

    def passo(self):
        if self.fim and not self.frota_enviada:
            self.enviar("FROTA " + self.tab.serializar_frota())
            self.frota_enviada = True
        if self.fim and self.frota_recebida:
            self.enviar("TCHAU")
            self.encerrado = True
            return
        if self.pendente and time.monotonic() >= self.prazo:
            if self.reenvios >= MAX_REENVIOS:
                raise ConnectionError("Sem confirmação após retransmissões")
            seq, coord = self.pendente
            print("[TIMEOUT] Reenviando o mesmo tiro.")
            self.enviar(f"TIRO {seq} {coord}")
            self.reenvios += 1
            self.prazo = time.monotonic() + TIMEOUT
        if self.minha_vez and not self.pendente and not self.fim:
            if not self.lendo:
                mostrar_painel(self.args.apelido, self.oponente, self.tab, self.tiros, True, self.enviado)
                self.solicitar_entrada()
            try:
                coord = self.entrada.get_nowait().strip().upper()
            except queue.Empty:
                pass
            else:
                self.lendo = False
                if coord == "SAIR":
                    self.enviar("TCHAU")
                    self.encerrado = True
                    return
                if coord == "AJUDA":
                    print("Escolha uma coordenada de A1 a J10 ainda não usada.")
                elif not re.fullmatch(r"[A-J](10|[1-9])", coord) or coord in self.tiros:
                    print("[ERRO] Coordenada inválida ou repetida.")
                else:
                    self.disparar(coord)
        try:
            msg = self.con.receber()
        except socket.timeout:
            return
        except ErroProtocolo:
            self.erro("utf8_invalido")
            return
        self.processar(msg)


def executar(args):
    con = None
    try:
        con = criar_conexao(args)
        oponente = handshake(con, args.apelido)
        tabuleiro = posicionar_frota()
        print("\n[STATUS] Frota pronta. Aguardando o outro jogador...")
        sincronizar_pronto(con)
        print("[STATUS] Ambos estão prontos. Partida iniciada!")
        Partida(con, args, oponente, tabuleiro).rodar()
    except (OSError, ConnectionError, ErroProtocolo) as exc:
        print(f"\n[ERRO DE REDE/PROTOCOLO] {exc}", file=sys.stderr)
        return 1
    finally:
        if con:
            con.fechar()
    print("[REDE] Conexão encerrada.")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Batalha Naval P2P sobre TCP — etapas 5 a 7.")
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
