# Lurdens

[![CI](https://github.com/lucasks2001/Lurdens/actions/workflows/ci.yml/badge.svg)](https://github.com/lucasks2001/Lurdens/actions/workflows/ci.yml)
[![Executáveis](https://github.com/lucasks2001/Lurdens/actions/workflows/release.yml/badge.svg)](https://github.com/lucasks2001/Lurdens/actions/workflows/release.yml)

Player complementar para o **Spotify Desktop**
Para:**Linux (KDE Plasma 6)**, **Windows 10/11** e **macOS**.

| Sistema | Como o Lurdens fala com o Spotify | Como instalar |
|---|---|---|
| Linux (Fedora KDE Plasma 6) | MPRIS pelo D-Bus de sessão | [`./install.sh`](#instalação) |
| Windows 10/11 (x64) | controles de mídia do Windows (SMTC) | `Lurdens-<versão>-windows-x64.zip` em [Releases](https://github.com/lucasks2001/Lurdens/releases) |
| macOS 11+ (Apple Silicon) | AppleScript do próprio Spotify | `Lurdens-<versão>-macos-arm64.zip` em [Releases](https://github.com/lucasks2001/Lurdens/releases) |

> **Em andamento:** o suporte a Windows e macOS chega na versão 1.3 (PRs #1–#7).
> Até lá, a versão publicada (1.2.0) roda só no Linux e os `.zip` de Windows/macOS
> ainda não estão nas Releases.

A interface é a mesma nos três (Qt 6 / QML pelo PySide6). Veja
[Windows e macOS](#windows-e-macos) para o que muda em cada sistema.

---

## Requisitos (Linux)

| Item | Observação |
|---|---|
| Fedora com KDE Plasma 6 | Wayland (padrão) ou X11 |
| Python 3.11+ | já vem no Fedora |
| PySide6 (Qt 6) | `sudo dnf install python3-pyside6` — ou `./install.sh --venv` |
| Spotify Desktop | RPM (ex.: negativo17/RPM Fusion) ou Flatpak `com.spotify.Client` |
| JetBrains Mono (opcional) | `sudo dnf install jetbrains-mono-fonts-all` — sem ela, o Lurdens usa outra fonte monoespaçada |

Não há outras dependências: a comunicação D-Bus é feita por um cliente
próprio em Python puro (`lurdens/dbus/wire.py`).

## Instalação

```bash
sudo dnf install python3-pyside6     # único passo que usa sudo (opcional, veja abaixo)
./install.sh
```

Tudo é instalado **só para o seu usuário**, sem permissões de administrador:

- `~/.local/share/lurdens/app/` — código
- `~/.local/bin/lurdens` — lançador
- `~/.local/share/applications/lurdens.desktop` — entrada no menu do KDE
- `~/.local/share/icons/hicolor/*/apps/lurdens.{png,svg}` — ícones

Prefere não instalar pacotes no sistema? Use um ambiente virtual isolado
(baixa o PySide6 do PyPI para `~/.local/share/lurdens/venv`):

```bash
./install.sh --venv
```

Depois abra **Lurdens** pelo menu de aplicativos ou rode `lurdens`.

### Executar sem instalar

```bash
./run.sh            # usa .venv/ do projeto, se existir; senão o python3 do sistema
```

### Atualizar para uma versão nova

Extraia o zip novo e rode `bash install.sh` de novo, dentro da pasta nova.
A cópia antiga é substituída e suas configurações em `~/.config/lurdens` são
mantidas. Feche o Lurdens antes (menu › Sair).

### Voltar para a versão anterior

Ao atualizar, o instalador guarda a versão que estava instalada em
`~/.local/share/lurdens/app.previous`. Para voltar a ela:

```bash
bash install.sh --rollback      # rode de novo para desfazer a reversão
```

As configurações são compatíveis entre versões: chaves novas são ignoradas
pelas versões antigas.

### Desinstalar

```bash
./uninstall.sh            # mantém ~/.config/lurdens
./uninstall.sh --purge    # remove também as configurações
```

## Windows e macOS

### Instalar

1. Baixe o `.zip` do seu sistema na página
   [Releases](https://github.com/lucasks2001/Lurdens/releases).
2. **Windows**: extraia a pasta `Lurdens` onde preferir (ex.: `Documentos`) e
   abra `Lurdens.exe`. **macOS**: extraia e arraste `Lurdens.app` para
   **Aplicativos**.
3. Abra o Spotify Desktop e toque uma música.

Os executáveis ainda não têm assinatura digital. Na primeira abertura:

- **Windows**: o SmartScreen avisa → *Mais informações* › *Executar assim mesmo*.
- **macOS**: clique com o botão direito em `Lurdens.app` › *Abrir* (ou rode
  `xattr -dr com.apple.quarantine /Applications/Lurdens.app`). Em seguida o
  macOS pede permissão para o Lurdens **controlar o Spotify** — aceite. Se
  negar sem querer: Ajustes do Sistema › Privacidade e Segurança ›
  Automação › Lurdens › Spotify.

### Executar a partir do código-fonte

```bash
python -m pip install -r requirements.txt   # PySide6 (+ PyWinRT no Windows)
python -m lurdens
```

### O que muda em cada sistema

| Recurso | Linux | Windows | macOS |
|---|---|---|---|
| Capa, título, artista, álbum, progresso | sim | sim | sim |
| Tocar/pausar, anterior/próxima, busca | sim | sim | sim |
| Volume | se o Spotify expuser | não — o SMTC não tem volume por app (use o Spotify ou o mixer) | sim |
| Aleatório | sim | sim | sim |
| Repetição | desligado → lista → faixa | desligado → lista → faixa | desligado ↔ lista (o AppleScript do Spotify não tem "repetir faixa") |
| Notificações ao trocar de faixa | serviço do Plasma | Central de Ações (precisa do ícone na bandeja) | Central de Notificações (precisa do ícone na bandeja) |
| Atalhos globais | kglobalaccel (KDE) | — (as teclas de mídia já controlam o Spotify) | — (idem) |
| Iniciar com o sistema | XDG autostart | `HKCU\…\CurrentVersion\Run` | LaunchAgent |
| Sempre no topo | dica do Qt / script do KWin | dica do Qt | dica do Qt |

No Windows, o Spotify só publica a sessão de mídia depois que alguma música
começa a tocar: se o Lurdens disser "Spotify fechado" com ele aberto, dê
play uma vez.

### Onde ficam os arquivos

| | Windows | macOS |
|---|---|---|
| Configurações | `%APPDATA%\Lurdens\settings.json` | `~/Library/Application Support/Lurdens/settings.json` |
| Histórico e tempo de uso | `%LOCALAPPDATA%\Lurdens\state\` | `~/Library/Application Support/Lurdens/state/` |
| Capas (cache) | `%LOCALAPPDATA%\Lurdens\cache\` | `~/Library/Caches/Lurdens/` |

Para desinstalar, apague a pasta (Windows) ou o app (macOS), desligue
"Iniciar com o sistema" antes, se estiver ligado, e apague as pastas acima.

## Uso

- **Janela**: abre compacta e vertical. Redimensione, maximize ou use tela
  cheia (F11). Com a janela larga (maximizada), a capa vai para a esquerda e os
  controles para a direita; com altura pequena vira um mini player horizontal.
  Ao voltar ao tamanho normal, a composição vertical retorna.
- **Barra superior**: ícone e nome, indicador de conexão (● conectado,
  ○ Spotify fechado), configurações e menu (Configurações, Modo compacto,
  Sempre no topo, Tela cheia, Ocultar na bandeja, Sobre, Sair). Minimizar,
  maximizar e fechar ficam na barra de título nativa do KWin.
- **Selo de versão** (ao lado de LURDENS): mostra a versão instalada e abre
  *Novidades*, com o histórico de mudanças. Fica preenchido enquanto houver
  uma versão nova que você ainda não abriu. O histórico também está em
  `CHANGELOG.md`.
- **Spotify fechado**: aparece um aviso discreto com o botão *Abrir Spotify*.
  O Lurdens detecta o Spotify sozinho quando ele abre, fecha ou reinicia.
- **Recursos não suportados** (volume, aleatório, repetição em versões do
  Spotify que não os expõem): o controle aparece esmaecido e a dica explica o
  motivo; ele não finge funcionar.

### Atalhos

| Tecla | Ação |
|---|---|
| Espaço | reproduzir / pausar |
| Ctrl+→ / Ctrl+← | próxima / anterior |
| → / ← | avançar / voltar 5 s |
| ↑ / ↓ | volume ±5 % |
| S / R | aleatório / repetição (desligado → lista → faixa) |
| F11 / Esc | tela cheia / sair da tela cheia ou fechar a página aberta |
| Ctrl+Y | histórico |
| Ctrl+T | temporizador para dormir |
| Ctrl+M | modo compacto |
| Ctrl+, | configurações |
| Ctrl+H | ocultar na bandeja |
| Ctrl+Q | sair |

As teclas multimídia do teclado e os controles de mídia do Plasma continuam
indo direto para o Spotify (ele é o player MPRIS). O Lurdens não se registra
como um segundo player — isso evitaria comandos duplicados — e apenas reflete
na hora o que mudou.

### Minimizar, ocultar e encerrar

- **Minimizar** (botão do KWin): a janela vai para a barra de tarefas.
- **Ocultar** (menu › *Ocultar na bandeja*, Ctrl+H): some da barra de tarefas;
  volta clicando no ícone da bandeja ou abrindo o Lurdens de novo.
- **Encerrar** (menu › *Sair*, Ctrl+Q, bandeja › *Sair*): fecha o programa.
- O botão **fechar** encerra, a não ser que *Fechar para a bandeja* esteja ligado.
- Abrir o Lurdens com ele já aberto apenas traz a janela existente para frente.

## Novidades da 1.3

- **Windows 10/11 e macOS**: o Lurdens passa a funcionar fora do Linux,
  com executáveis prontos nas releases (veja [Windows e macOS](#windows-e-macos)).
- Backends de reprodução por sistema (`lurdens/backends/`): MPRIS no Linux,
  SMTC no Windows e AppleScript no macOS, todos sem conta nem login.
- Pastas, inicialização automática, notificações e textos da interface
  conforme o sistema.
- CI no GitHub Actions com testes e autoteste da interface nos três sistemas.

## Novidades da 1.2

| Recurso | Onde | Detalhes |
|---|---|---|
| **Histórico** | botão ⟲ na barra, menu, Ctrl+Y | Uma linha por reprodução: capa, música, artista, álbum, horário. Voltar a uma música já ouvida cria nova linha; repetir a mesma faixa também. Pausas, buscas e atualizações de metadados não duplicam. Anúncios são ignorados. Fica em memória; opcionalmente salvo em `~/.local/state/lurdens/history.json` (Configurações › Histórico). Botão de lixeira limpa. |
| **Temporizador para dormir** | lua na barra, menu, bandeja, Ctrl+T | 15/30/45/60 min ou personalizado (1–720). Mostra a contagem na barra; +5 min, reiniciar, cancelar. Ao terminar envia **Pause** ao Spotify (nunca encerra nada, nunca desliga o PC). Mede por prazo absoluto no relógio de boot: funciona com a janela oculta e não atrasa se o PC suspender. Spotify fechado no fim: apenas avisa. |
| **Notificações** | Configurações › Notificações | Pelo serviço de notificações do Plasma (respeita “Não perturbe” e as preferências do KDE). Capa, título, artista. Não avisa ao abrir o app, ao reconectar ao Spotify, com a janela do Lurdens em foco, nem várias vezes em trocas rápidas (aguarda ~1 s e cada aviso substitui o anterior). |
| **Atalhos globais** | Configurações › Atalhos globais | Registrados no serviço de atalhos do KDE (kglobalaccel), que funciona em Wayland e X11. Padrões: **Meta+Alt+P** tocar/pausar, **Meta+Alt+N** próxima, **Meta+Alt+B** anterior, **Meta+Alt+L** mostrar/ocultar. Se uma combinação já estiver em uso, o KDE recusa e a tela mostra “em uso” para você escolher outra. Também editáveis em Configurações do Sistema › Atalhos › Lurdens. |
| **Iniciar com o KDE** | Configurações › Comportamento | Cria `~/.config/autostart/lurdens.desktop` (`lurdens --autostart`): abre na bandeja; se já estiver aberto, não faz nada. Removível também em Configurações do Sistema › Inicialização automática. |
| **Tempo de uso** | Configurações › Tempo de uso | Mede quanto tempo **o Lurdens fica aberto** (inclusive oculto na bandeja), não o tempo de música. Suspensão não conta. Mostra sessão atual, total de hoje e início da sessão; reinicia o contador da sessão. O total do dia (opcional) fica em `~/.local/state/lurdens/usage.json`, só o dia atual, zerando à meia-noite. Nada é enviado para fora. |
| **Bandeja** | ícone do Lurdens | Música atual (▶/❚❚), tocar/pausar, anterior, próxima, temporizador, mostrar/ocultar, sair. Clique: mostra/oculta; clique do meio: tocar/pausar. |
| **JetBrains Mono** | toda a interface | Usada se instalada (sistema, `~/.local/share/fonts` ou `.ttf` em `lurdens/resources/fonts/`). Senão: Source Code Pro → Noto Sans Mono → DejaVu Sans Mono → fonte fixa do sistema. Configurações › Aparência mostra qual está em uso. A fonte não é distribuída junto (licença OFL permite, mas preferimos o pacote do Fedora). |

### Easter egg

<details><summary>Spoiler</summary>

Tocando **“Ludens”, do Bring Me The Horizon**, o fundo do Lurdens ganha uma
arte em hachuras derivada de `Bring icon.png` (a estrela de seis pontas):
traços de nanquim, cada região com hachura num ângulo, hachura cruzada no
centro e pontilhado em volta. Fica atrás da capa e dos controles, com
opacidade baixa e transição suave de ~1 s.

- Exige título “Ludens” **e** artista Bring Me The Horizon (ou BMTH), tocando.
  Tolera maiúsculas, acentos, espaços e sufixos como “- 2020” ou
  “(From Death Stranding…)”. Remix, ao vivo, acústico etc. não ativam.
  Sem artista nos metadados, não ativa.
- Funciona nas edições *Death Stranding: Timefall* e *POST HUMAN: SURVIVAL
  HORROR* — e em qualquer outra, porque o álbum é só complementar (aparece no
  diagnóstico).
- Pausado: fica um rastro bem discreto. Retomou: volta. Outra música: some.
- Nada é salvo: ao reabrir, depende só do que está tocando.
- A arte é gerada por `tools/make_easter.py` a partir de
  `lurdens/resources/easter/Bring icon.png` (versões para tema claro e escuro).
  Para usar outro arquivo: `python3 tools/make_easter.py "caminho/Bring icon.png"`.
  Se a arte faltar, o efeito fica desligado e o diagnóstico avisa.

</details>

## Configurações

Salvas em `~/.config/lurdens/settings.json` (gravação atômica; arquivo
corrompido ou valores inválidos são ignorados e os padrões são usados).

Arquivos locais do Lurdens:

| Caminho | Conteúdo |
|---|---|
| `~/.config/lurdens/settings.json` | configurações |
| `~/.config/autostart/lurdens.desktop` | só se “Iniciar com o KDE” estiver ligado |
| `~/.local/state/lurdens/history.json` | só se “Guardar histórico entre sessões” estiver ligado |
| `~/.local/state/lurdens/usage.json` | total de uso do dia (se o registro estiver ligado) |
| `~/.cache/lurdens/covers/` | capas baixadas para as notificações (até 120 arquivos) |

`./uninstall.sh --purge` apaga todos eles.

- **Aparência**: tema escuro (padrão), claro ou do sistema; modo compacto
  (mini player ≈ 420 × 184 para deixar num canto da tela).
- **Comportamento**: sempre no topo; abrir o Spotify junto; ícone na bandeja;
  fechar para a bandeja; iniciar minimizado na bandeja.
- **Sistema**: estado da conexão D-Bus/Spotify, recursos disponíveis, tipo de
  instalação do Spotify, sessão gráfica, versão, dicas de diagnóstico e botão
  *Copiar diagnóstico*.

## Integração com o KDE e limites do Wayland (Linux)

| Recurso | X11 | Wayland |
|---|---|---|
| Ícone e nome no menu/barra de tarefas | sim | sim (`app_id` = `lurdens`, casa com `lurdens.desktop`) |
| Lembrar tamanho da janela | sim | sim |
| Lembrar **posição** da janela | sim | não — o Wayland não deixa aplicativos posicionarem janelas; o KWin decide (use regras de janela do KDE se quiser fixar) |
| Sempre no topo | dica de janela do Qt | script do KWin carregado via D-Bus (`org.kde.KWin /Scripting`). Se falhar, a mensagem aparece nas configurações; alternativa manual: Alt+F3 › Mais ações › Manter acima |
| Bandeja do sistema | sim | sim (StatusNotifierItem do Plasma) |
| Escala 125 %/150 % | sim | sim (escala fracionária com `PassThrough`) |
| Atalhos globais | kglobalaccel (KDE) | kglobalaccel (KDE) — aplicativos não podem capturar o teclado diretamente no Wayland; sem o serviço, os atalhos ficam indisponíveis e a tela explica |
| Notificações | org.freedesktop.Notifications | idem |
| Iniciar com a sessão | XDG autostart | idem |

## Spotify: RPM × Flatpak

As duas versões publicam o mesmo serviço MPRIS
(`org.mpris.MediaPlayer2.spotify`); o Lurdens também aceita variantes com
sufixo (`…spotify.instanceNNNN`). Para *Abrir Spotify* ele procura, nessa
ordem: o binário `spotify` nativo, o Flatpak `com.spotify.Client`
(`flatpak run com.spotify.Client`) e o Snap. Nenhum arquivo do Spotify é
modificado.

Particularidades tratadas: a posição não é enviada pelo Spotify na troca de
faixa (o Lurdens a busca logo depois), URLs antigas de capa
`open.spotify.com/image/…` são convertidas para `i.scdn.co`, e a posição é
interpolada localmente enquanto toca, com ressincronização a cada 5 s — sem
consultas contínuas ao D-Bus.

## Diagnóstico

```bash
tools/diagnostico.sh             # sistema, PySide6, Spotify no D-Bus e autoteste
lurdens --debug                  # mensagens detalhadas no terminal
lurdens --selftest ~/capturas    # renderiza a interface fora da tela e salva PNGs
busctl --user list | grep mpris  # o Spotify aparece no D-Bus?
```

Problemas comuns:

- **“Spotify fechado” com o Spotify aberto** — feche e reabra o Spotify; confira
  com o `busctl` acima. No Flatpak, não remova a permissão de nome MPRIS.
- **Capa não aparece** — a capa vem de `i.scdn.co`; sem rede, fica a capa
  alternativa do Lurdens.
- **Volume/aleatório/repetição esmaecidos** — a versão do Spotify não expõe
  essas propriedades via MPRIS.
- **Nada acontece ao abrir pelo menu** — rode `lurdens --debug` num terminal.

O `--selftest` não abre janela: usa a plataforma *offscreen*, gera capturas
em vários tamanhos/temas (retrato, claro, título longo, sem recursos
opcionais, Spotify fechado, sem D-Bus, amplo, mini, mínimo, configurações,
sobre), confere a persistência das configurações e **falha se o QML emitir
qualquer aviso**. As faixas nessas capturas são marcadas como
“DEMONSTRAÇÃO” e existem só no autoteste.

Na 1.2 o autoteste também captura histórico, temporizador, configurações
completas e o easter egg (claro, escuro, amplo, pausado, depois da troca) e
verifica: arte carregada, ativação só com Ludens/BMTH tocando, modo discreto
ao pausar, fundo normal após trocar de faixa e histórico sem duplicatas.

## Testes automatizados

```bash
python3 -m unittest discover -s tests -v
```

A CI (GitHub Actions) roda os testes e o autoteste da interface no Linux,
no Windows e no macOS em cada PR; as capturas ficam como artefatos da
execução. O workflow **Executáveis** gera e testa os pacotes de Windows e
macOS e os anexa à release em cada tag `v*`.

- Backends (`tests/test_backends.py`, `test_smtc.py`, `test_applescript.py`):
  base de leitura periódica, SMTC com sessão simulada e AppleScript com o
  `osascript` simulado — rodam em qualquer sistema. `test_smtc_live.py`
  confere o PyWinRT real (só no Windows).
- Sistema (`tests/test_platform.py`): pastas, inicialização automática
  (registro do Windows simulado, LaunchAgent do macOS) e detecção do Spotify.

- Unidades: serialização D-Bus (ida e volta, alinhamento, big-endian),
  estado e interpolação da posição, URLs de capa, configurações (validação,
  arquivo corrompido), detecção RPM/Flatpak, script do KWin.
- Integração: sobe um `dbus-daemon` privado e um **Spotify simulado**
  (`tests/mock_spotify.py`, implementação independente com dbus-python) e
  verifica descoberta, metadados, tocar/pausar, próxima/anterior, busca,
  volume, aleatório, repetição, mudanças feitas fora do Lurdens, Spotify
  aberto depois/fechado/reiniciado, player sem recursos opcionais, nome com
  sufixo de instância e perda do barramento.
  Requer `python3-dbus` e `python3-gobject` (o teste é pulado se faltarem).
- 1.2 (`tests/test_features.py`): regras do easter egg (edições, variações,
  outros artistas, metadados incompletos, pausa/retomada), detector do
  histórico (sem duplicatas, reconexão, repetir faixa, anúncios), persistência
  opcional, temporizador (prazo, +5 min, reiniciar, suspensão), tempo de uso
  (sessões, virada do dia, desligado), autostart, e integração D-Bus com
  serviços simulados (`tests/mock_desktop.py`): notificações (substituição,
  capa, trocas rápidas, servidor ausente), atalhos globais (registro, conflito,
  tecla pressionada, troca feita no KDE, serviço ausente) e o temporizador
  pausando o Spotify simulado. Os mocks seguem a API publicada do KDE, mas
  **não** substituem o teste no Plasma real.

O mock também serve para ver a interface com dados sem o Spotify:
`python3 tests/mock_spotify.py --play` (feche o Spotify antes — o nome colide).

## Arquitetura

```
lurdens/
├── backends/         como cada sistema fala com o Spotify (1.3)
│   ├── base.py       contrato PlayerBackend (comandos + PlayerState por callback)
│   ├── polling.py    base de leitura periódica (Windows/macOS)
│   ├── smtc.py       Windows: controles de mídia do sistema (PyWinRT)
│   └── applescript.py macOS: dicionário AppleScript do Spotify (osascript)
├── paths.py          pastas de configuração/estado/cache por sistema (1.3)
├── dbus/wire.py      cliente D-Bus mínimo (socket Unix, auth EXTERNAL, thread leitora)
├── mpris.py          Linux: descoberta do Spotify, sinais, comandos — thread própria com fila
├── state.py          PlayerState imutável, interpolação, normalizações
├── settings.py       configurações JSON persistentes
├── launcher.py       detecção/abertura do Spotify (RPM, Flatpak, Snap, Windows, macOS)
├── tracks.py         detector de novas reproduções + histórico (1.2)
├── easter.py         reconhecimento de Ludens/BMTH (1.2)
├── timers.py         temporizador para dormir e tempo de uso (1.2)
├── notify.py         notificações do freedesktop (Linux) + cache de capas (1.2)
├── shortcuts.py      atalhos globais via kglobalaccel (1.2)
├── autostart.py      inicialização automática: XDG, registro do Windows, LaunchAgent (1.2/1.3)
├── changelog.py      conteúdo de "Novidades"
├── kwin.py           "sempre no topo" no Wayland via script do KWin
├── qt/controllers.py objetos expostos ao QML (player, app)
├── qt/app.py         janela, geometria, bandeja, instância única
├── qt/session.py     histórico, timers, notificações, atalhos e easter egg para o QML (1.2)
├── qt/selftest.py    autoteste offscreen
├── qml/              interface (Qt Quick) e componentes de nanquim
└── resources/        ícones e capa alternativa
packaging/lurdens.desktop.in
packaging/lurdens.spec   empacotamento PyInstaller (Windows/macOS)
.github/workflows/    CI (3 sistemas) e geração dos executáveis
tools/make_icons.py   gera SVG/PNGs do ícone a partir de uma geometria
tools/make_easter.py  gera a arte hachurada do easter egg a partir de Bring icon.png
tools/diagnostico.sh
tests/
```

A interface nunca espera o D-Bus: comandos são enviados de forma assíncrona,
e o estado chega por sinais em fila para a thread do Qt.

## Ícone

`lurdens/resources/icons/` contém `lurdens.svg` (principal), uma variante
simplificada para tamanhos pequenos, o emblema sem fundo e PNGs de 16 a 512 px
(≤ 32 px usam a variante simplificada, sem furos, com traços mais grossos).
O emblema fica sobre uma placa cor de papel com contorno e sombra de tinta,
para ser legível em painéis claros e escuros. Para ajustar a forma, edite a
geometria em `tools/make_icons.py` e rode `python3 tools/make_icons.py`
(precisa de Pillow só para gerar os PNGs).

---

Projeto independente, sem vínculo com o Spotify. Spotify é marca da Spotify AB.
