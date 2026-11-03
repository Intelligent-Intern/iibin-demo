import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from backend import store,inference
class English(unittest.TestCase):
    def test_machine_commands_use_english_and_keep_interlocks_as_separate_actions(self):
        commands={'open the safety guard':'machine_guard_open','close the guard and start the test':'machine_close_start','I have inserted the valve':'machine_insert','start the test':'machine_start','pause the test':'machine_pause','abort the test':'machine_abort','how many tests failed?':'protocol_summary','do not start the test':'fallback'}
        for phrase,expected in commands.items():self.assertEqual(inference.machine_command(phrase),expected,phrase)
        self.assertIsNone(inference.machine_command('How do I start the test?'))
    def test_owned_faq_seeds_are_updated_to_english(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(store,'VAR',Path(folder)):
            store.init()
            with store.db() as c:c.execute("UPDATE faq SET question='Wie starte ich?' WHERE id='faq_start'")
            store.init()
            with store.db() as c:
                self.assertEqual(c.execute("SELECT question FROM faq WHERE id='faq_start'").fetchone()[0],'How do I start the test?')
                self.assertEqual(c.execute("SELECT value FROM setting WHERE key='active_voice'").fetchone()[0],'lessac')
if __name__=='__main__':unittest.main()
