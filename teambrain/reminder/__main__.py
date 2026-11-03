"""`python3 -m teambrain.reminder ...` 로 실행되는 입구."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
