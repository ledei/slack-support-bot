from main import slack_escape, to_slack


def test_slack_escape_neutralises_pings_mentions_and_links():
    out = slack_escape("Hi <!channel> <@U123> see <https://evil.example|Help page> & Settings > Account")
    assert "<" not in out and ">" not in out
    assert out == "Hi &lt;!channel&gt; &lt;@U123&gt; see &lt;https://evil.example|Help page&gt; &amp; Settings &gt; Account"


def test_to_slack_converts_bold_after_escaping():
    assert to_slack("1. Tap **Privacy** > **Export**") == "1. Tap *Privacy* &gt; *Export*"
