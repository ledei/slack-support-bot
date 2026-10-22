from rag import near_best


def test_keeps_only_chunks_close_to_the_best_match():
    # Regression: with many docs, loosely related ones (~0.73) crowded out the right one (0.35).
    hits = [("challenges", 0.35), ("reward", 0.73), ("goal", 0.73)]
    assert near_best(hits, max_distance=0.75, margin=0.12) == ["challenges"]

    hits = [("blur 1", 0.41), ("blur 2", 0.49), ("gyroscope", 0.63)]
    assert near_best(hits, max_distance=0.75, margin=0.12) == ["blur 1", "blur 2"]


def test_nothing_close_enough_means_nothing():
    assert near_best([("stats", 0.77), ("pan", 0.80)], max_distance=0.75, margin=0.12) == []
    assert near_best([], max_distance=0.75, margin=0.12) == []
