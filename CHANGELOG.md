# Histórico de versões

O mesmo conteúdo aparece no app em **Novidades** (clique no selo de versão na barra superior).
Fonte: `lurdens/changelog.py`.

## 1.3.0 — 22/10/2026
- Novo: suporte ao **Windows 10/11** pelos controles de mídia do sistema (SMTC, via PyWinRT).
- Novo: suporte ao **macOS** pelo dicionário AppleScript do Spotify (osascript).
- Novo: executáveis para Windows x64 e macOS (Apple Silicon) gerados pelo PyInstaller e anexados às releases.
- Novo: backends de reprodução por sistema (`lurdens/backends/`) com uma base comum de leitura periódica.
- Novo: pastas de configuração, estado e cache por sistema (`lurdens/paths.py`).
- Novo: iniciar com o sistema no Windows (registro) e no macOS (LaunchAgent).
- Novo: notificações pela bandeja no Windows e no macOS; textos da interface conforme o sistema.
- Novo: CI no GitHub Actions com testes e autoteste da interface no Linux, Windows e macOS.
- Corrigido: instância única no Windows (`os.getuid` não existe lá).
- Corrigido: o autoteste não falha quando a arte do easter egg está ausente.
- Linux: sem mudanças de comportamento.

## 1.2.0 — 22/10/2026
- Novo: histórico da sessão (Ctrl+Y) com capa, música, artista, álbum e horário; persistência opcional.
- Novo: temporizador para dormir (Ctrl+T): 15/30/45/60 min ou personalizado; envia Pause ao Spotify.
- Novo: notificações do KDE ao trocar de faixa, com capa, sem duplicatas.
- Novo: atalhos globais configuráveis via kglobalaccel (Wayland e X11).
- Novo: iniciar com o KDE (autostart XDG), direto na bandeja, instância única.
- Novo: Tempo de uso nas configurações (sessão e total do dia, local).
- Novo: bandeja com a música atual e o temporizador.
- Novo: tipografia JetBrains Mono com alternativas automáticas.
- Novo: `./install.sh --rollback` volta para a versão anterior.
- Novo: easter egg (veja o README, seção com spoiler).
- Corrigido: o lançador não carrega mais o código-fonte da pasta atual por engano.

## 1.1.0 — 22/10/2026
- Corrigido: o título da música ficava descentralizado por alguns segundos ao trocar de faixa.
- Novo: selo de versão na barra superior, que abre o histórico de mudanças.
- Novo: o selo aparece preenchido quando há uma versão que você ainda não viu.

## 1.0.0 — 21/10/2026
- Primeira versão: janela compacta e vertical, capa, título, artista e álbum.
- Controles do Spotify via MPRIS: tocar/pausar, anterior/próxima, busca, volume, aleatório e repetição.
- Layouts amplo e mini, tema escuro/claro/sistema, bandeja do sistema e configurações persistentes.
- Ícone baseado no “lurdens icon”, instalador sem sudo e autoteste da interface.
