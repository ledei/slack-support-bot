from rag import clean_draft, is_swedish, near_best, quoted_before, repeats


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


def test_repeats_spots_an_earlier_answer_again():
    # From Slack: "is there any more i should know off?" got the first answer back.
    first = 'Can people join a company challenge after its start date? Yes, according to the docs, "Yes, until the challenge stops. The start date does not close enrollment."'
    history = [("can users join after the start date?", first)]
    assert repeats('Yes, according to the docs, "Yes, until the challenge stops. The start date does not close enrollment."', history)
    assert not repeats("Also: offers launched before late registration existed keep it switched off.", history)
    assert not repeats(first, [])


def test_quoted_before_finds_chunks_the_thread_already_used():
    faq = "Can people join a company challenge after its start date?\n\nYes, until the challenge stops. The start date does not close enrollment."
    adr = "Newly eligible memberships receive a pending `ContestUser` until the contest stop time."
    history = [("can users join?", 'Yes, according to the docs, "Yes, until the challenge stops. The start date does not close enrollment."')]
    assert quoted_before(faq, history)
    assert not quoted_before(adr, history)
