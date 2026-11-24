# Roteiro de testes e relatório

Automatizados: `python -m unittest -v`. Consulte resultado_testes.txt para o resultado obtido no ambiente de desenvolvimento. Não equivale a teste entre implementações independentes.

## Interoperabilidade (preencher após executar)

| Colega | Data | Versão/commit | Resultado e falhas |
|---|---|---|---|
| 1 | | | |
| 2 | | | |

## Wireshark

Inicie captura na interface de rede usada (loopback para teste local, Npcap no Windows). Filtro de exibição `tcp.port == 5000`. Jogue uma partida inteira. Anote SYN, SYN/ACK, ACK, um TIRO/RESULTADO e FIN/ACK (ou RST se falha). Use Follow TCP Stream para conferir mensagens; para demonstrar agrupamento/fragmentação, examine bytes de segmentos individuais. O teste automatizado demonstra delimitação, mas não garante segmentação específica na captura. Salve pcapng e números dos quadros.

## Degradação com tc (Linux/VM)

Em interface de teste Linux, substitua eth0 pela interface correta (ou lo se teste local). Execute `sudo tc qdisc add dev eth0 root netem delay 100ms loss 5%`. Jogue, capture e registre o comportamento; remova com `sudo tc qdisc del dev eth0 root`. Não execute em uma interface de acesso remoto da qual dependa. Perda de segmentos pode ser recuperada pelo próprio TCP sem disparar timeout de aplicação.

## Queda e retorno

Durante partida, interrompa temporariamente a rede de teste ou force o fechamento da conexão TCP mantendo os processos vivos. Restabeleça a rede dentro do prazo de retomada após detecção. Confira RETOMAR, continuidade das sequências e ausência de tiros duplicados. Uma interrupção silenciosa pode não ser detectada durante ociosidade até haver tráfego. Não finalize os processos, pois estado não é persistido em disco.

Registre data, parâmetros, quadros da captura, mensagens observadas e resultado real. Capturas, interoperabilidade, tc e queda de rede física ainda não executados neste relatório.
