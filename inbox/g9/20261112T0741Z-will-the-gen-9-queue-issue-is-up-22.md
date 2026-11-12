The Gen 9 queue issue is up (#22); module reviews now go to the peer lead

will, 12 Nov 07:41 UTC.

**The phone view.** https://github.com/maxschireson/Single-Dummy-Bridge/issues/22, "Gen 9 queue": decisions for Max first, then reviews waiting by reviewer (with how long), blocked, in progress by holder, resolved today, the next checkpoint from ROSTER.md. 19 lines today. `workq` rewrites it after any change, at most every 10 minutes, in sessions that have `gh` (you and me), and `workq issue` forces it.
- **Pinning:** I found no REST endpoint that pins an issue (REST pins comments; issues are pinned through GraphQL or the sidebar, which we cannot reach), so it is not pinned. Max, or anyone with write access in a browser, can click "Pin issue" in its right sidebar once.
- **Notifications:** sessions act with Max's GitHub credentials, so the issue shows him as its author, and creating it may have notified him once. Body rewrites should not notify (the commonly cited behaviour; I have not seen GitHub's documentation say so).
- **Decisions:** `workq decision "title" --body ...` (you only) opens an issue labelled `decision`, assigned to Max, and it goes to the top of #22. Any comment on an open decision issue that workq did not write is copied into your inbox as a message from `max`, once. `workq decision --close N --note ...` closes it.

**Module reviews.** In since `d05c916`: `submit` sends a `module` task to its owner's peer lead (bill-sam, dave-will), anything else to you; a `reviewer:` header overrides; `resolve` accepts that reviewer or you; README section "Tasks" says so. The rule is worked out from `kind` and `owner` at submit time, so no task file needed editing. `set ID reviewer=<name>` is there for exceptions. Only two submissions were waiting when it went in, E9-9 and G9-S6, and neither is a module, so both stay with you.

**Also since 07:10:** G9-W6 submitted (base swap script). A trial on a stand-in Gen 8 base replays cleanly, but bill's card tests fail 5 of 18 on Gen 8's later rule bidder r2; bill is told. `workq brief ID` and `workq check --ready ID` are in. Next: dave's W3 follow-up (manifest outputs, pytest-style files), then the experiment result check at submit and value-for-effort ordering from the note.
