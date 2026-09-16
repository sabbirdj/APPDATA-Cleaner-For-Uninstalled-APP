import unittest
from PyQt6.QtWidgets import QApplication
import sys
from backend.scanner_engine import ScannerEngine, AppDataItem
from ui_fluent.scanner_interface import ScannerInterface

app = QApplication.instance() or QApplication(sys.argv)

class TestUIWindowsExclusion(unittest.TestCase):
    def setUp(self):
        self.scanner = ScannerEngine()
        self.ui = ScannerInterface(self.scanner)

    def tearDown(self):
        self.ui.deleteLater()

    def test_default_state(self):
        self.assertTrue(hasattr(self.ui, 'chk_exclude_windows'))
        self.assertTrue(self.ui.chk_exclude_windows.isChecked())

    def test_windows_exclusion_filtering(self):
        discord_item = AppDataItem(name='Discord', path=r'C:\test\discord', root_type='Roaming')
        discord_item.status = 'ORPHANED'
        discord_item.size = 5000

        win_item = AppDataItem(name='WindowsHolographicDevices', path=r'C:\test\win', root_type='ProgramData')
        win_item.status = 'PROTECTED'
        win_item.size = 9000

        self.ui.items = [discord_item, win_item]
        self.ui.item_paths = {discord_item.path, win_item.path}
        self.ui._update_metrics()
        self.ui._set_filter('ALL')

        # With chk_exclude_windows checked: win_item should be excluded!
        self.assertEqual(len(self.ui.filtered_items), 1)
        self.assertEqual(self.ui.filtered_items[0].name, 'Discord')
        self.assertEqual(self.ui.table.rowCount(), 1)
        self.assertEqual(self.ui.card_total.value_label.text(), '1')

        # When toggling off:
        self.ui.chk_exclude_windows.setChecked(False)
        self.assertEqual(len(self.ui.filtered_items), 2)
        self.assertEqual(self.ui.table.rowCount(), 2)
        self.assertEqual(self.ui.card_total.value_label.text(), '2')

        # When toggling back on:
        self.ui.chk_exclude_windows.setChecked(True)
        self.assertEqual(len(self.ui.filtered_items), 1)
        self.assertEqual(self.ui.filtered_items[0].name, 'Discord')
        self.assertEqual(self.ui.table.rowCount(), 1)
        self.assertEqual(self.ui.card_total.value_label.text(), '1')

if __name__ == '__main__':
    unittest.main()
