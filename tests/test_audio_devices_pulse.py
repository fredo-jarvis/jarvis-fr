"""Noms de périphériques PulseAudio/PipeWire : pas de source « .monitor » prise pour un micro ou une sortie."""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import audio_devices  # noqa: E402

SINK = "alsa_output.usb-GN_Audio_A_S_Jabra_EVOLVE_30_II_0003C29DD14A09-00.analog-stereo"


def _dev(name, entrees, sorties):
    return {"name": name, "max_input_channels": entrees, "max_output_channels": sorties, "hostapi": 0}


class NomsPulse(unittest.TestCase):
    def test_le_nom_d_une_sortie_ne_devient_pas_celui_de_sa_source_monitor(self):
        devices = [_dev(SINK, 0, 2), _dev(SINK + ".monitor", 2, 0)]
        with mock.patch("platform.system", return_value="Linux"):
            self.assertEqual(audio_devices._display_name(SINK, devices), SINK)

    def test_windows_garde_la_reparation_des_noms_tronques_par_mme(self):
        long_nom = "Realtek HD Audio 2nd output (Realtek(R) Audio)"
        devices = [_dev(long_nom[:31], 0, 2), _dev(long_nom, 0, 2)]
        with mock.patch("platform.system", return_value="Windows"):
            self.assertEqual(audio_devices._display_name(long_nom[:31], devices), long_nom)

    def test_les_sources_monitor_ne_sont_pas_proposees_comme_micro(self):
        devices = [_dev(SINK, 0, 2), _dev(SINK + ".monitor", 2, 0), _dev("alsa_input.usb-Jabra.mono", 1, 0)]
        fake_sd = mock.Mock(query_devices=lambda: devices, query_hostapis=lambda: [{"name": "PulseAudio"}])
        with mock.patch.dict(sys.modules, {"sounddevice": fake_sd}), \
                mock.patch("platform.system", return_value="Linux"), \
                mock.patch.object(audio_devices, "_usable", return_value=True), \
                mock.patch.object(audio_devices, "_transport_works", return_value=True):
            resultat = audio_devices._query()
        self.assertEqual(resultat["input"], ["alsa_input.usb-Jabra.mono"])
        self.assertEqual(resultat["output"], [SINK])


if __name__ == "__main__":
    unittest.main()
