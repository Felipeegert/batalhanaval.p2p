import socket
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from batalha_naval import ConexaoTCP, Partida, conferir_frota
from tabuleiro import Tabuleiro, FROTA

def frota():
    t = Tabuleiro()
    for i, (codigo, tamanho) in enumerate(FROTA):
        t.posicionar_navio(codigo, tamanho, chr(65+i)+'1', 'H')
    return t

class Testes(unittest.TestCase):
    def partida(self):
        return Partida(Mock(), SimpleNamespace(escutar=None, apelido='B'), 'A', frota())

    def test_fluxo(self):
        a,b = socket.socketpair()
        with a,b:
            con = ConexaoTCP.criar(b)
            a.sendall(b'OLA 1 A\nPRONTO\nTI')
            self.assertEqual(con.receber(),'OLA 1 A')
            self.assertEqual(con.receber(),'PRONTO')
            b.settimeout(.02)
            with self.assertRaises(socket.timeout): con.receber()
            a.sendall(b'RO 1 B7\n')
            self.assertEqual(con.receber(),'TIRO 1 B7')

    def test_duplicado(self):
        p = self.partida()
        p.processar('TIRO 1 A1')
        p.processar('TIRO 1 A1')
        self.assertEqual(len(p.tab.tiros_recebidos),1)
        self.assertEqual(p.con.enviar.call_count,2)
        p.con.enviar.assert_called_with('RESULTADO 1 ACERTOU')
        p.processar('TIRO 1 A2')
        p.con.enviar.assert_called_with('ERRO sequencia_reutilizada')

    def test_invalido(self):
        p=self.partida()
        p.processar('TIRO 1 K1')
        self.assertFalse(p.cache)
        p.processar('TIRO 1 A1')
        p.processar('TIRO 2 A2')
        p.con.enviar.assert_called_with('ERRO fora_de_turno')

    def test_timeout(self):
        p=self.partida();p.minha_vez=True
        p.disparar('J10');p.prazo=0
        p.con.receber.side_effect=socket.timeout
        p.passo()
        self.assertEqual(p.con.enviar.call_count,2)
        p.con.enviar.assert_called_with('TIRO 1 J10')
        p.processar('RESULTADO 1 AGUA');p.processar('RESULTADO 1 AGUA')
        self.assertEqual(len(p.historico),1)
        self.assertFalse(p.minha_vez)

    def test_conferencia(self):
        msg='FROTA '+frota().serializar_frota()
        self.assertEqual(conferir_frota(msg,{1:('A1','ACERTOU',False)}),[])
        self.assertTrue(conferir_frota(msg,{1:('A1','AGUA',False)}))
        self.assertTrue(conferir_frota('FROTA DE:A1:H',{}))

if __name__=='__main__': unittest.main()
