"""Histórico de versões exibido em "Novidades" (o primeiro item é a versão atual)."""

CHANGELOG = [
    {
        "version": "1.3.0",
        "date": "22/10/2026",
        "changes": [
            "Novo: o Lurdens funciona no Windows 10/11, pelos controles de mídia do sistema.",
            "Novo: o Lurdens funciona no macOS, pelo AppleScript do próprio Spotify.",
            "Novo: executáveis prontos para Windows e macOS na página de Releases.",
            "Novo: iniciar com o sistema, notificações e pastas de configuração em cada sistema.",
            "Corrigido: o autoteste não falha mais quando a arte do easter egg não está presente.",
            "No Linux nada muda: continua pelo MPRIS, com os mesmos recursos.",
        ],
    },
    {
        "version": "1.2.0",
        "date": "22/10/2026",
        "changes": [
            "Novo: histórico da sessão (Ctrl+Y) com capa, música, artista, álbum e horário; pode ser guardado entre sessões.",
            "Novo: temporizador para dormir (Ctrl+T) de 15/30/45/60 min ou personalizado; pausa o Spotify ao terminar.",
            "Novo: notificações do KDE ao trocar de faixa, com capa (sem repetir ao abrir o app ou ao reconectar).",
            "Novo: atalhos globais configuráveis pelo serviço de atalhos do KDE (funcionam em Wayland).",
            "Novo: iniciar com o KDE, direto na bandeja, sem abrir duas cópias.",
            "Novo: seção Tempo de uso nas configurações (sessão atual e total do dia, só local).",
            "Novo: bandeja mostra a música atual e tem o temporizador para dormir.",
            "Novo: tipografia JetBrains Mono (com alternativa automática se não estiver instalada).",
            "Novo: instalador guarda a versão anterior; volte com ./install.sh --rollback.",
            "Há também uma surpresa para quem ouve a música certa…",
        ],
    },
    {
        "version": "1.1.0",
        "date": "22/10/2026",
        "changes": [
            "Corrigido: o título da música ficava descentralizado por alguns segundos ao trocar de faixa.",
            "Novo: selo de versão na barra superior, que abre este histórico de mudanças.",
            "Novo: o selo aparece preenchido quando há uma versão que você ainda não viu.",
        ],
    },
    {
        "version": "1.0.0",
        "date": "21/10/2026",
        "changes": [
            "Primeira versão: janela compacta e vertical, capa, título, artista e álbum.",
            "Controles do Spotify via MPRIS: tocar/pausar, anterior/próxima, busca, volume, aleatório e repetição.",
            "Layouts amplo e mini, tema escuro/claro/sistema, bandeja do sistema e configurações persistentes.",
            "Ícone baseado no “lurdens icon”, instalador sem sudo e autoteste da interface.",
        ],
    },
]
