"""The Git helper must keep an unsuccessful run visible for investigation."""

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from add_commit_push_gui import AddCommitWindow


class TestCommitPushGui:
    def test_failed_push_window_stays_open(self, tmp_path: Path) -> None:
        application = QApplication.instance() or QApplication([])
        script = tmp_path / "fails.sh"
        script.write_text(
            '#!/bin/bash\nprintf "ERROR: remote diverged\\n"\nexit 1\n',
            encoding="utf-8",
        )
        window = AddCommitWindow(script)
        window.show()
        loop = QEventLoop()
        window._process.finished.connect(loop.quit)
        QTimer.singleShot(4000, loop.quit)
        loop.exec()
        application.processEvents()
        try:
            assert window._process.state() == window._process.ProcessState.NotRunning
            assert window._completed_exit_code == 1
            assert window.isVisible()
            assert window._stop_button.text() == "Close"
            assert window._stop_button.isEnabled()
            assert "ERROR: remote diverged" in window._output.toPlainText()
        finally:
            window.close()

    def test_graphical_confirmation_and_message_prompts(self, tmp_path: Path) -> None:
        application = QApplication.instance() or QApplication([])
        script = tmp_path / "prompts.sh"
        script.write_text(
            '#!/bin/bash\nprintf "Do you want to commit and push these changes? [y/N]: "\n'
            'IFS= read -r answer\n'
            'printf "Enter commit message: "\n'
            'IFS= read -r message\n'
            'printf "Saved choice: %s and message: %s\\n" "$answer" "$message"\n'
            'exit 0\n',
            encoding="utf-8",
        )
        window = AddCommitWindow(script)
        window.show()

        def wait_for(predicate) -> None:
            from time import monotonic

            until = monotonic() + 5.0
            while not predicate() and monotonic() < until:
                application.processEvents()
                import time
                time.sleep(0.01)
            assert predicate(), window._output.toPlainText()

        try:
            wait_for(lambda: window._awaiting == "confirm")
            window._submit_confirmation(True)
            wait_for(lambda: window._awaiting == "message")
            window._message_edit.setText("Daily changes")
            window._submit_message()
            wait_for(lambda: hasattr(window, "_completed_exit_code"))
            assert window._completed_exit_code == 0
            assert "Saved choice: y and message: Daily changes" in window._output.toPlainText()
        finally:
            window.close()
