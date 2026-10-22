import main
from main import remember, slack_escape, to_slack


def test_slack_escape_neutralises_pings_mentions_and_links():
    out = slack_escape("Hi <!channel> <@U123> see <https://evil.example|Help page> & Settings > Account")
    assert "<" not in out and ">" not in out
    assert out == "Hi &lt;!channel&gt; &lt;@U123&gt; see &lt;https://evil.example|Help page&gt; &amp; Settings &gt; Account"


def test_to_slack_converts_bold_after_escaping():
    assert to_slack("1. Tap **Privacy** > **Export**") == "1. Tap *Privacy* &gt; *Export*"


def test_remember_keeps_recent_turns_and_threads():
    main.THREADS.clear()
    for i in range(6):
        remember("t1", f"q{i}", f"a{i}", max_turns=4)
    assert main.THREADS["t1"] == [("q2", "a2"), ("q3", "a3"), ("q4", "a4"), ("q5", "a5")]
    remember("t2", "q", "a", max_threads=2)
    remember("t3", "q", "a", max_threads=2)
    assert list(main.THREADS) == ["t2", "t3"]  # oldest thread dropped
