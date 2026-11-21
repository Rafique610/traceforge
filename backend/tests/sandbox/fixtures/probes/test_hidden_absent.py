import os


def test_hidden_dir_not_mounted():
    assert not os.path.exists("/hidden")
