"""Launch the local official ok-script source with this project's environment."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNTIME = ROOT / "vendor" / "ok-script"


def prepare():
    if not (RUNTIME / "ok/__init__.py").is_file():
        raise SystemExit(f"找不到專案內的官方框架：{RUNTIME}")
    sys.path.insert(0, str(RUNTIME))
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)


if __name__ == "__main__":
    prepare()
    if "--check" in sys.argv:
        from starsavior.tasks import DailyTask, InspectTask
        from starsavior.case_task import CaseFilesTask, verify_case_assets
        verify_case_assets()
        from starsavior.config import config
        import cv2
        from opencc import OpenCC
        import ok
        if Path(ok.__file__).resolve() != (RUNTIME / "ok/__init__.py").resolve():
            raise SystemExit(f"載入了錯誤的框架：{ok.__file__}")
        print(f"OK: Python {sys.version.split()[0]}, framework={RUNTIME}")
        print(f"Executable: {sys.executable}; package: {ok.__file__}")
        print(f"Tasks: {DailyTask.__name__}, {InspectTask.__name__}, {CaseFilesTask.__name__}; OpenCV {cv2.__version__}")
    else:
        import logging
        from ok import OK
        from starsavior.config import config
        # The bundled framework logs every environment variable at startup.
        # Keep this project's logs focused on task diagnostics instead.
        class TaskLogFilter(logging.Filter):
            def filter(self, record):
                return not record.getMessage().startswith("ok:env ")
        logging.getLogger("ok").addFilter(TaskLogFilter())
        OK(config).start()
