import shutil

from pipeline import config


def test_creates_work_and_out_dirs_on_import():
    shutil.rmtree(config.WORK_DIR, ignore_errors=True)
    shutil.rmtree(config.OUT_DIR, ignore_errors=True)

    import importlib

    importlib.reload(config)

    assert config.WORK_DIR.is_dir()
    assert config.OUT_DIR.is_dir()
