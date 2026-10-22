# Plain, warm language for the Slack support bot

How the Slack support bot should turn technical facts into plain, polite answers for everyday (non-technical) users. Use it when you write or tune the bot's system prompt, few-shot examples or reply templates.

Researched 21 October 2026. Evidence labels: *read* (page fetched and checked), *inferred* (my reasoning from read sources), *unverified* (seen only in a search snippet or not confirmed).

## 1. Hypothesis and verdict

**Hypothesis.** Plain-language guidelines (short sentences, everyday words, lead with the answer or action, active voice, explain a needed technical term once in everyday words or drop it, a brief empathy acknowledgement, numbered steps) plus a polite tone that does not grovel give the best comprehension and satisfaction.

**What would change it.** Evidence that heavy apologies or too much politeness hurt satisfaction, or that small LLMs (~1.5B, e.g. Qwen 2.5 1.5B) follow few-shot examples better than lists of rules.

**Verdict: held, with two changes.**

1. **The empathy part changed.** For a *bot*, showing feelings back to the user ("I understand how frustrating this must be") can backfire. It makes the bot seem less competent and lowers satisfaction (Han, Yin and Zhang, 2026). "Thank you" usually works better than "sorry" (You et al., 2020), and more "sorry" goes with lower satisfaction (Smart Customer Service, 2014). So: keep the warmth, but write it as thanks plus a practical fix, not as emotional mirroring. Apologise at most once, and only when we caused the problem.
2. **The rules-vs-examples part is only partly settled.** First-party guidance says examples are one of the most reliable ways to steer tone and format, with 3–5 recommended (Anthropic, 2026). I found no first-party Qwen source comparing rules with examples for 1.5B models (*unverified*). Use both: a short rule list plus 3 examples.

## 2. Findings

### Plain language

- **F1. Active voice makes clear who does what.** Passive voice hides who is responsible. Prefer present tense and strong verbs over hidden verbs, e.g. write "decide", not "make a decision" (Digital.gov, 2026b). *read*
- **F2. Shorter words and short sections make content easier to understand** (Digital.gov, 2026b). *read*. The federal guide series is now hosted on Digital.gov. plainlanguage.gov/guidelines redirects there (Digital.gov, 2026a). *read*
- **F3. GOV.UK says content must be written so users "find what they need and understand it"**, and it points to subpages on clear language, tone and summaries (GOV.UK, 2026). *read*. The well-known GOV.UK specifics (about 25 words per sentence at most, writing for a reading age of about 9, front-loading) were **not** on the pages I fetched, so treat them as *unverified* here.
- **F4. Clarity comes before entertainment.** Mailchimp's voice is "plainspoken": no jargon, no slang, active voice, positive language. Voice stays the same, but tone changes with how the reader feels (e.g. confused and looking for help). Humour is optional, and "forced humor can be worse than none" (Mailchimp, n.d.). *read*

### Error and problem messages

- **F5. Explain problems in plain words, be specific, and hide error codes** unless they are needed to diagnose the problem. "An error occurred" is too vague (Neusesser and Sunwall, 2023). *read*
- **F6. Don't blame the user.** Avoid words like "invalid", "illegal" or "incorrect". Avoid humour in errors. Always give a constructive next step, and where you can, guess the fix and offer a short list of options (Neusesser and Sunwall, 2023). *read*
- **F7. NN/g mentions apologising only for catastrophic failures.** It does not discuss over-apologising (Neusesser and Sunwall, 2023). *read*

### Politeness, apology and empathy (evidence against parts of the hypothesis)

- **F8. "Thank you" usually beats "sorry" after a service failure.** Thanks led to higher satisfaction, more repeat custom, more recommendations and fewer complaints. It works by shifting focus from the provider's fault to the customer's merit, which raises the customer's self-esteem. Thanks alone worked as well as thanks plus sorry (You et al., 2020). *read* (via the AMA summary, not the full paper)
- **F9. Limits of F8:** the advantage disappears when the problem is fixed *before* it happens. It is weaker for customers low in narcissism. In severe failures, thanks only beats sorry when paired with a real remedy (You et al., 2020). *read*
- **F10. Empathetic messages from chatbots often backfired.** When a bot acknowledged and mirrored negative emotions after a failure, users felt it was intrusive and that their control was threatened (reactance). The bot seemed less competent, and service quality and satisfaction dropped. The same empathy from a human worked. The research was three experiments, one with a live LLM service chatbot (Han, Yin and Zhang, 2026). *read* (university news summary)
- **F11. In Zendesk benchmark data, satisfaction fell as human agents used "sorry", "please" and "thank you" more.** "Sorry" fell steepest. The suggested cause is longer back-and-forth threads, so this is correlation, not cause. More than two "sorry"s was suggested as a cue to escalate (Smart Customer Service, 2014). *read*
- **F12. A 2023 *Journal of Retailing and Consumer Services* study (4 experiments) reportedly found that a chatbot using appreciation recovered satisfaction better than one admitting its limits.** A 2026 *Computers in Human Behavior* paper reportedly found polite apologies work best in high-severity cases. *unverified* (search snippets only, pages not fetched)

### Prompting a small model

- **F13. Examples are "one of the most reliable ways" to steer format, tone and structure.** Make them relevant (mirror the real use case) and diverse (cover edge cases so the model doesn't copy unintended patterns). Wrap them in `<example>` tags, and use 3–5 for best results (Anthropic, 2026). *read*. This is written for Claude models.
- **F14. Small open models such as Qwen 2.5 1.5B rely even more on examples than on abstract rules.** *inferred*, *unverified*. No first-party Qwen page was fetched.

## 3. Rules for the bot

Short, imperative and testable, so a 1.5B model can follow them.

1. Start with the answer or the next step. No preamble.
2. Use short sentences and everyday words. Write like you talk to a colleague.
3. Speak to the user as "you". Say who does what ("Click Save", not "Save should be clicked").
4. Leave out error codes, logs and system names unless the user asked for them.
5. If you must use a technical word, explain it once in plain words, in brackets.
6. When there is more than one step, give numbered steps, one action per step.
7. Thank the user ("Thanks for flagging this"). Say "sorry" at most once, and only if we caused the problem.
8. Don't describe the user's feelings. Be warm by being helpful, not emotional.
9. Never blame the user. Avoid "invalid", "wrong" and "incorrect".
10. Always end with what happens next or how to get more help.
11. Keep replies under about 80 words unless the user asks for detail.
12. If you don't know, say so plainly and offer to pass it to a person.

## 4. Before/after examples (few-shot)

Wrap each one in `<example>` tags in the system prompt (Anthropic, 2026).

### Example 1: sign-in / SSO error

**User:** I can't log in, it says "SAML assertion invalid: audience mismatch (AADSTS700016)".

**Before (technical):**
> The SAML assertion failed validation because the audience URI in the IdP response does not match the SP entity ID. This is usually an app registration misconfiguration in Azure AD (AADSTS700016). Verify the Identifier (Entity ID) in the enterprise application.

**After (plain, warm):**
> Thanks for sending the exact message, that helps a lot. This isn't something you did. The company sign-in is set up slightly wrong on our side.
> 1. For now, try signing in with your email and password instead of "Sign in with Microsoft".
> 2. I've flagged the setup issue to the IT team.
> I'll post here as soon as it's fixed.

### Example 2: sync / API failure

**User:** My steps haven't updated in the app since yesterday.

**Before (technical):**
> The wearable provider webhook returned HTTP 401 because the OAuth refresh token expired, so the sync job couldn't pull new activity data. Re-authorise the integration to issue a new token.

**After (plain, warm):**
> Thanks for letting us know. Your watch and the app have lost their connection. It happens now and then for security reasons.
> 1. Open the app and go to **Settings → Connected apps**.
> 2. Tap your watch, then **Reconnect**, and sign in.
> Your steps from yesterday should show up within about 15 minutes. If they don't, reply here and I'll take a closer look.

### Example 3: data-export question

**User:** Can I get all my data out of the app?

**Before (technical):**
> Yes. Under GDPR Art. 20 you can request a data portability export. The system generates a ZIP of JSON files through an async job and emails a pre-signed S3 link that expires in 72h.

**After (plain, warm):**
> Yes, you can. Here's how:
> 1. Go to **Settings → Privacy → Download my data**.
> 2. Tap **Request export**.
> We'll email you a download link, usually within a few hours. The link works for 3 days, so save the file soon after it arrives. Anything else I can help with?

(The menu paths, timings and integration names in these examples are placeholders. Check them against the real product before shipping. *inferred*)

## 5. Conflicts and gaps

- **Empathy: humans vs bots.** Human-agent research and general support advice favour acknowledging feelings, but Han, Yin and Zhang (2026) found that emotional mirroring *from a chatbot* hurt satisfaction. I sided with the bot-specific study for this bot, but it is one paper (three experiments), seen only through a news summary.
- **Thanks vs sorry depends on severity.** You et al. (2020) found thanks wins in ordinary failures. In severe ones it needs a real remedy, and a snippet-only 2026 source (F12) says polite apologies work best in severe cases. Rule 7 allows one "sorry" when we caused the problem. For outages and data loss, consider a fuller apology plus a fix.
- **Zendesk data (2014) is correlational** and concerns human agents. It is the weakest of the three politeness sources.
- **Plain-language numbers not confirmed.** The GOV.UK sentence-length and reading-age figures and the FPLG "lists" and "define terms" sections were not on the pages I fetched. *unverified*
- **No Qwen-specific evidence.** Whether a 1.5B Qwen model follows rules or examples better is untested here. Next step: an A/B eval in this repo (rules only vs rules plus 3 examples) on about 20 real tickets, scored for plain language and correctness.
- **Swedish users.** All sources are English-language. Politeness norms in Swedish workplaces (direct, low formality) may differ. *inferred*
- **Independent sources:** 8 fetched (Digital.gov ×2 pages = 1 publisher, GOV.UK, Mailchimp, NN/g, AMA/You et al., USF/Han et al., Smart Customer Service/Zendesk, Anthropic). That is 7 independent publishers.

## 6. References

Anthropic (2026) *Prompting best practices*. Available at: https://platform.claude.com/docs/en/docs/build-with-claude/prompt-engineering/multishot-prompting (Accessed: 21 October 2026).

Digital.gov (2026a) *Plain language guide series*. U.S. General Services Administration. Available at: https://digital.gov/guides/plain-language (Accessed: 21 October 2026).

Digital.gov (2026b) *Writing for understanding*. U.S. General Services Administration. Available at: https://digital.gov/guides/plain-language/writing (Accessed: 21 October 2026).

GOV.UK (2026) *Writing guidelines: GOV.UK content and publishing guidance*. Available at: https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/writing-guidelines/ (Accessed: 21 October 2026).

Han, E., Yin, D. and Zhang, H. (2026) *Empathetic chatbots can make customer service worse* [news summary of an MIS Quarterly article]. University of South Florida Muma College of Business. Available at: https://www.usf.edu/business/news/2026/roi-spring-empathetic-chatbot-worse.aspx (Accessed: 21 October 2026).

Mailchimp (n.d.) *Voice and tone: Mailchimp Content Style Guide*. Available at: https://styleguide.mailchimp.com/voice-and-tone/ (Accessed: 21 October 2026).

Neusesser, T. and Sunwall, E. (2023) *Error-message guidelines*. Nielsen Norman Group. Available at: https://www.nngroup.com/articles/error-message-guidelines/ (Accessed: 21 October 2026).

Smart Customer Service (2014) *Over apologizing can spell lower customer satisfaction*. Available at: https://smartcustomerservice.com/Articles/News-Briefs/Over-Apologizing-Can-Spell-Lower-Customer-Satisfaction-98988.aspx (Accessed: 21 October 2026).

You, Y., Yang, X., Wang, L. and Deng, X. (2020) *Why you should say thank you and not sorry after most service failures* [AMA summary of 'When and why saying "thank you" is better than saying "sorry" in redressing service failures: the role of self-esteem', *Journal of Marketing*, 84(2)]. American Marketing Association. Available at: https://www.ama.org/2020/03/24/why-you-should-say-thank-you-and-not-sorry-after-most-service-failures/ (Accessed: 21 October 2026).
