"""Rebuild retrieval corpus from recent trace store entries."""
from core.retrieval.corpus import corpus


def main():
    c = corpus()
    c.rebuild()
    print(f"Built corpus with {len(c.query(1000))} entries")


if __name__ == '__main__':  # pragma: no cover
    main()
