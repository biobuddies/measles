from importlib import import_module


def test_manage_check(monkeypatch):
    monkeypatch.setattr('sys.argv', ['manage.py', 'check'])
    import_module('manage').main()
