from rag import clean_draft, is_swedish, near_best


def test_keeps_only_chunks_close_to_the_best_match():
    # Regression: with many docs, loosely related ones (~0.73) crowded out the right one (0.35).
    hits = [("challenges", 0.35), ("reward", 0.73), ("goal", 0.73)]
    assert near_best(hits, max_distance=0.75, margin=0.12) == ["challenges"]

    hits = [("blur 1", 0.41), ("blur 2", 0.49), ("gyroscope", 0.63)]
    assert near_best(hits, max_distance=0.75, margin=0.12) == ["blur 1", "blur 2"]


def test_nothing_close_enough_means_nothing():
    assert near_best([("stats", 0.77), ("pan", 0.80)], max_distance=0.75, margin=0.12) == []
    assert near_best([], max_distance=0.75, margin=0.12) == []


def test_clean_draft_drops_copied_labels_and_rewrite_openers():
    assert clean_draft("Answer: Use `make api`.") == "Use `make api`."
    assert clean_draft("Sure, here’s the revised answer:\n\n1. Run `make db-up`.") == "1. Run `make db-up`."
    assert clean_draft("Here's a revised version: Done.") == "Done."
    assert clean_draft("The answer is in `goal-history.md`.") == "The answer is in `goal-history.md`."


def test_is_swedish():
    assert is_swedish("kan användare gå med efter startdatum?")
    assert is_swedish("hur fungerar mål historiken")
    assert is_swedish("snackar du dansk")
    assert not is_swedish("can users join after the start date?")
    assert not is_swedish("how does the goal history work")
