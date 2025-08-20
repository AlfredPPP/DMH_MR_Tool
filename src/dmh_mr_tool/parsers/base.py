# src/dmh_mr_tool/parsers/base.py
from core.logging import log_execution


class Foo:
    def __init__(self):
        print(1)

    @log_execution()
    def add(self, x, y):
        return x + y
