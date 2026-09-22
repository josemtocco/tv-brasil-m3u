# 🇧🇷 Gerador automático M3U — TV Brasil / SS IPTV

Este projeto transforma fontes M3U/JSON públicas e autorizadas em uma única playlist `tv-brasil.m3u`, removendo duplicidades e verificando a disponibilidade dos streams.

## O que ele faz

1. Baixa as fontes definidas em `fontes.json`.
2. Aceita:
   - M3U / M3U8
   - JSON em formato de lista de canais
3. Filtra canais do Brasil conforme as regras de cada fonte.
4. Remove duplicidades.
5. Testa as URLs HTTP/HTTPS.
6. Gera `tv-brasil.m3u`.
7. Gera `status.json` com estatísticas.
8. O GitHub Actions executa o processo automaticamente.

> Importante: o projeto não fornece nem redistribui streams protegidos. Cadastre somente fontes e URLs que você tenha autorização para usar/distribuir ou que sejam explicitamente públicas para esse uso.

## Arquivos

- `fontes.json` — fontes de entrada.
- `filtros.json` — palavras permitidas/bloqueadas.
- `gerar_m3u.py` — motor do gerador.
- `tv-brasil.m3u` — playlist final.
- `status.json` — relatório da última execução.
- `.github/workflows/gerar-m3u.yml` — automação.

## Configurando fontes

Edite `fontes.json`:

```json
[
  {
    "name": "Minha fonte autorizada",
    "url": "https://exemplo.com/lista.m3u",
    "format": "m3u",
    "enabled": true
  }
]
```

Para JSON, use:

```json
{
  "name": "Minha API autorizada",
  "url": "https://exemplo.com/canais.json",
  "format": "json",
  "enabled": true
}
```

O JSON pode retornar uma lista com objetos contendo:

- `name`
- `url`
- `logo`
- `group`
- `tvg_id`
- `country`
- `enabled`

## Filtro

O arquivo `filtros.json` permite controlar o que entra na lista.

O projeto prioriza canais identificados como brasileiros e pode excluir termos indesejados.

Se uma fonte já contém somente canais brasileiros, use:

```json
"brazil_only": false
```

## Teste local

```bash
python gerar_m3u.py
```

Para exigir que os streams estejam respondendo:

```bash
python gerar_m3u.py --check-streams
```

Para testar apenas algumas URLs:

```bash
python gerar_m3u.py --check-streams --workers 12
```

## GitHub Actions

O workflow pode ser executado manualmente ou em horários programados. O agendamento usa o fuso de São Paulo.

Depois da execução, o arquivo `tv-brasil.m3u` será gravado no repositório.

GitHub documenta workflows agendados e execução manual em Actions:
https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax

## URL para SS IPTV

Depois que o repositório for público:

```text
https://raw.githubusercontent.com/SEU-USUARIO/SEU-REPOSITORIO/main/tv-brasil.m3u
```

O SS IPTV usa Extended M3U e requer que a playlist esteja disponível externamente. A documentação oficial também descreve requisitos de CORS para servidores que entregam playlists diretamente ao cliente.

## Observação sobre disponibilidade

Um teste HTTP bem-sucedido não garante que um canal esteja reproduzindo vídeo. Alguns servidores de vídeo exigem cabeçalhos, tokens, referer, cookies ou bloqueiam HEAD/GET automatizados. Nesses casos, mantenha a URL somente se você souber que ela é válida para seu uso no SS IPTV.

## EPG

O projeto deixa o cabeçalho M3U preparado para EPG, mas não baixa um EPG de terceiros automaticamente. Isso pode ser adicionado depois usando uma fonte XMLTV autorizada.
