import os

from ios_deposit.cli import main


if __name__ == "__main__":
    main(base_dir=os.path.dirname(os.path.abspath(__file__)))
