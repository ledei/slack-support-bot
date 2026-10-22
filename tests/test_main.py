import main
from main import slack_escape, to_slack


def test_slack_escape_neutralises_pings_mentions_and_links():
    out = slack_escape("Hi <!channel> <@U123> see <https://evil.example|Help page> & Settings > Account")
    assert "<" not in out and ">" not in out
    assert out == "Hi &lt;!channel&gt; &lt;@U123&gt; see &lt;https://evil.example|Help page&gt; &amp; Settings &gt; Account"


def test_to_slack_converts_bold_after_escaping():
    assert to_slack("1. Tap **Privacy** > **Export**") == "1. Tap *Privacy* &gt; *Export*"


def test_thread_history_pairs_questions_with_bot_answers():
    msgs = [
        {"ts": "1.0", "user": "U1", "text": "<@BOT> can users join after the start date?"},
        {"ts": "2.0", "user": "BOT", "bot_id": "B1", "text": "Yes, until the challenge stops. Use `a &lt; b`."},
        {"ts": "3.0", "user": "U2", "text": "lol nice"},
        {"ts": "4.0", "user": "U1", "text": "are you sure?"},
    ]
    history, bot_last = main.thread_history(msgs, "BOT", current_ts="4.0")
    assert history == [("can users join after the start date?", "Yes, until the challenge stops. Use `a < b`.")]
    assert bot_last is False  # U2 spoke after the bot, so "are you sure?" needs an @mention

    history, bot_last = main.thread_history(msgs[:2] + [msgs[3]], "BOT", current_ts="4.0")
    assert bot_last is True  # direct follow-up to the bot: answer without @mention
    assert main.thread_history([msgs[0]], "BOT", current_ts="1.0") == ([], False)  # thread starter itself
