"""Verificação do backend SMTC contra o PyWinRT real (só no Windows).

Confere que os nomes usados pelo backend existem na API projetada e que o
gerenciador de sessões responde. Não precisa do Spotify aberto: sem ele, a
leitura deve devolver None.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _winrt_available() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winrt.windows.media.control  # noqa: F401
    except ImportError:
        return False
    return True


@unittest.skipUnless(_winrt_available(), "só no Windows com o pacote winrt instalado")
class LiveSmtcTests(unittest.TestCase):
    def test_api_names(self):
        from winrt.windows.media import MediaPlaybackAutoRepeatMode
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as M
        from winrt.windows.storage.streams import Buffer, DataReader, InputStreamOptions
        self.assertTrue(hasattr(M, "request_async"))
        self.assertEqual(int(MediaPlaybackAutoRepeatMode(2)), 2)
        self.assertTrue(hasattr(InputStreamOptions, "READ_AHEAD"))
        self.assertTrue(hasattr(DataReader, "from_buffer"))
        self.assertEqual(int(Buffer(16).capacity), 16)

    def test_reads_without_spotify(self):
        from lurdens.backends.smtc import SmtcBackend
        backend = SmtcBackend(lambda s: None)
        try:
            backend._open()
        except Exception as exc:  # p. ex., Windows Server sem o serviço de mídia
            self.skipTest(f"gerenciador de sessões indisponível: {exc}")
        try:
            state = backend._read()
            if state is not None:        # alguém com Spotify aberto rodando os testes
                self.assertTrue(state.bus_name)
        finally:
            backend._close()


if __name__ == "__main__":
    unittest.main()
