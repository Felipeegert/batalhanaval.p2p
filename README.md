# Como executar o projeto

## 1. Pré-requisitos

- Python 3.10 ou superior instalado.
- Dois computadores conectados à mesma rede (ou com comunicação entre si pela internet).
- Porta TCP 5000 liberada no firewall do computador anfitrião.

## 2. Preparação do ambiente

Abra o terminal na pasta do projeto.

Crie o ambiente virtual:

```powershell
py -m venv venv
```

Ative o ambiente virtual:

```powershell
.\venv\Scripts\Activate.ps1
```

Não é necessário instalar dependências adicionais, pois o projeto utiliza apenas bibliotecas nativas do Python.

## 3. Executando o jogo

O programa possui dois modos de execução: anfitrião e convidado.

### Anfitrião

O anfitrião é responsável por aguardar a conexão do outro jogador.

No primeiro computador, execute:

```powershell
python batalha_naval.py --escutar 5000 --apelido ana
```

- `--escutar`: indica que o jogador será o anfitrião.
- `5000`: porta TCP utilizada para receber a conexão.
- `--apelido`: nome utilizado para identificar o jogador.

### Convidado

O convidado deve conhecer o endereço IP do computador anfitrião.

No segundo computador, execute:

```powershell
python batalha_naval.py --conectar 127.0.0.1 5000 --apelido beto
```

- `--conectar`: indica que o jogador será o convidado.
- `192.168.1.100`: endereço IP do computador anfitrião.
- `5000`: porta utilizada pelo anfitrião.
- `--apelido`: nome utilizado para identificar o jogador.

**Importante:** substitua `192.168.1.100` pelo endereço IP real do computador anfitrião.

## 4. Como descobrir o endereço IP

No computador anfitrião, abra o PowerShell e execute:

```powershell
ipconfig
```

Procure pelo adaptador de rede que está sendo utilizado (Wi-Fi ou Ethernet).

Localize o campo:

```text
Endereço IPv4 . . . . . . . . . . : 192.168.1.100
```

Utilize esse endereço no comando `--conectar` do convidado.

## 5. Firewall do Windows

Caso os computadores não consigam estabelecer conexão, verifique se o firewall permite conexões TCP na porta 5000.

No computador anfitrião, pode ser necessário criar uma regra de entrada permitindo essa porta.

## 6. Ordem de execução

1. O anfitrião executa o programa com `--escutar`.
2. O convidado executa o programa com `--conectar`, informando o IP do anfitrião.
3. Os jogadores estabelecem a conexão TCP.
4. Ambos enviam a mensagem `OLA` com a versão do protocolo e seus apelidos.
5. Ambos enviam `PRONTO` para sincronizar o início da partida.

O anfitrião é o primeiro a jogar.

## 7. Encerramento

Para encerrar a conexão nesta versão inicial, pressione ENTER no terminal de qualquer um dos jogadores.
## Atualização — etapas 5, 6 e 7

Durante sua vez, digite `sair` para encerrar ou `ajuda` para instruções. Não há mais pausa com ENTER. Use `python -m unittest -v` para rodar os testes automatizados.

Timeout de RESULTADO: 5 segundos; até 3 reenvios antes de tentar reconectar. Prazo de reconexão: 60 segundos. O estado é preservado em memória enquanto os processos estão vivos. Consulte PROTOCOLO.md e TESTES.md. Os tempos e a semântica de RETOMAR precisam ser confirmados com a turma.
