
# Biotope conference submission + experiment scope (Sebastian 1:1)

## Participants
- **Sebastian Lobentanzer** — PI; author of BioCypher and Biotope; set the paper's message and the experiment requirements.
- **Vladislav Samoilov (Vlad)** — brought the agenda; owns the experiments and the submission logistics.

## Topic 1 — What to submit to the conference (deadline next Monday)

**The constraint.** Vlad: the paper submission deadline for the SWAT`[sic? SWAT4LS]` for Life Sciences conference is **next Monday**, and he is unsure a submittable paper can be made from what exists.

**Sebastian on submission formats:**
- A **full paper** is "probably not very feasible".
- There are "different extents of contribution". The **demo** is "the least effort" (the call for papers offers poster + demonstration, a two-pager).
- A **five-pager** (short paper) "could be feasible": "We have a lot from the NFDI preparation already, so we can fill the five pages. I don't know if it will be the most stellar writing, but if it's just about going to SWAT and presenting to people what we do, I think it's feasible."
- He also said he doesn't know what a short paper gives them "if we are just submitting it to a regular journal anyways", and that the **extended abstract for NFDI for Life Sciences was already accepted**, "so we already have a conference".

**Sebastian on the venue's weight:**
- "SWAT isn't that prestigious." Neither SWAT nor NFDI for Life Sciences is "something like an A\*[sic? A-star] conference"; "accepted for a talk at NeurIPS, that's a completely different dimension of conference acceptance."
- Therefore: "it will not even matter if it's a long paper, short paper, or a workshop slash demonstration."
- The reason to go: "SWAT is essentially a big part of our audience. And it would be nice to represent there."

**Talk selection — unresolved.** Neither knew how talks are selected. Facts established:
- Vlad: the website has only two pages, "hello" and "call for papers"; the FAQ says "more information coming soon".
- Sebastian: a **demonstration is in the poster session, not a plenary**. He assumes the two-pager "will probably not be a frontal like plenary presentation, but you know I might be wrong."
- Sebastian: these conferences "often are very, very badly organized. It's just historical."
- Sebastian described the usual mechanism: a **call for abstracts**, from which organizers "puzzle together the talk program".
- The abstract deadline **was yesterday** (2026-09-07). Vlad read it as **optional but "very appreciated"**. Sebastian: "this abstract is optional… but it's an abstract for the thing that you're going to submit, so you still need to submit the five-pager or something", and he "would assume that this is tied to the talks."

**Agreed scope:** Vlad writes an email to the organizers asking about talks; the submission target is either a **five-page short paper** or a **two-page demonstration + poster**. Vlad also stated a **full preprint deadline of ~end of September** "for our reasons"; Sebastian: "yeah, yeah, fine."

## Topic 2 — The message of the paper / talk

**Reception of the earlier NFDI submission (Sebastian):** it "was very well received"; "many people were kind of taken aback because… people are very traditional, particularly in ontology, and this was something new. They didn't know that it was even a thing, even possible." He said people responded to the title as well — framed around **keeping semantic authority accessible to us**.

**The main paradigm shift = the experiment.** Sebastian pointed to two slides (~19–20 of an existing deck) with an animation: one showing "what previously was necessary for a knowledge graph" (**a team of experts**), replaced in the next by **a scientific question**.
- This is "only possible because we have what we show in the experiment": "not perfect, but adequate, or like on eye level performance of this very long and time consuming expert build."
- **The baseline is their own previous work** — "our previous knowledge representation system, which we say is like one of the cutting edge systems for people to use" (published 2023).
- The Biotope-guided agent "does it in **75 minutes** and costs you a fraction."
- Stated hypothesis: "the messages that they are kind of equivalent, like give or take, plus minus… Not completely equivalent, but that doesn't really matter. That's our hypothesis."
- The claimed consequence: iterative work becomes possible — "you can think about something on a day, you let it run overnight, you come back and you do it again, like four or five times, and then you have five different graphs… which can cover much more area than this one expert build graph by 5 people over a year."
- "So that would be the main pivot of the paper."

**Second hypothesis in the paper (Sebastian):** people in knowledge representation "are often guided by the structure of the original data." He said **both keynotes** [at the earlier event] echoed this: "data to graph, often you don't get a graph that actually does what you want."
- Biotope's stated advantage: "it grills you on your purpose. Like it spends a lot of time in the beginning to figure out what your purpose is."
- This existed in **BioCypher** but "was purely manual human stuff": Sebastian or someone who knows it well would sit down with the user "in like a one-to-one walk", tease the requirements out, define the schema, then do the ETL.
- BioCypher's other component was **eliminating redundancy via reusable adapters**; "now basically the reusable adapters are being replaced by the ability of LLMs to just write the adapters de novo based on your semantic authority."

**What is *not* the message (Sebastian):** the methodology — "the Git process, the logs, the checksums… deterministic build, maybe Paul's type checking thing."
- "For me, that's a very minor detail. It's just how we technically make it work. And we could make it work in very different ways" (e.g. a regular BioCypher build plus a type-checking step afterwards).
- Paul's version is "just convenient… because it can get like build time type checking… But that's not the main message of the paper. Just one of the things that we leverage to make it work in practice, but it's not a scientific thing."
- "Science is showing something works and engineering is making it work well. We do a lot of engineering, but I think for a scientific paper, people are much more interested in this paradigm shift."
- He compared the framing to "corporate messaging".

**Vlad's restatement, confirmed by Sebastian:** before, you needed a big team of experts building very general-purpose massive graphs requiring a lot of money and maintenance; now, thanks to agents, you can build purpose-specific graphs.

## Topic 3 — The experiments

**Both agreed the current experiment is insufficient.** Vlad: "what I think is still not good enough is the experiment that we show. It's a bit too small." Sebastian: "Yes. That's absolutely my point."

**The named weakness: only 13 competency questions (CQs).**
- Sebastian: "The worst thing that we have is… there's only 13 competency questions."
- Category split: **retrieval** questions are "already very good, like saturated kind of"; the **multi-hop / synthesis** questions are "not very good in both" systems.
- "More competency questions is what I would ask for first before I ask anything else as a reviewer, because we claim that we have these two systems at about eye level, and what the experiments need to show is that this is actually the case. So you cannot get away with thin competency question[s] in the experiment."
- Not maximal: "Not very extensive, just enough to say, yeah, it seems like they might be on eye level."
- What must be shown: **Biotope is much faster** ("that's a no-brainer") and that building the same thing **without** Biotope — "web search and these typical tools" — "is not going to hold up to the competency questions." "We don't even need to show that Biotope is much better."
- Sebastian: "it's really nice that our own baseline is our own work, but just the manual work of the thing that we published in 2023. It's a good continuation."

**The InTraC dataset (Rupshali's graph).**
- Vlad: the dataset is "super tiny" — the **agent baseline on raw data answered all competency questions without the graph** ("it was not failing"; he did not recall the exact score). He said he does not think this is a competency-question problem.
- Sebastian: "Well, it could be… These multi-hop questions, the things that people actually asked, these are still extremely hard." And if size is the concern, "then we just use the open targets graph. That thing is huge."
- Sebastian also asked for "maybe a couple more competency questions, especially mutli-hop ones, even for Rupshali['s] case".

**Multiple graphs / axes of variation (Sebastian).**
- Target: "the same experiment that we do on, I don't know, three or four different graphs, in addition to the one that Rupshali has built."
- Rationale: "it's probably better to have a couple of graphs that cover different axes of variation so that you can in the paper then describe, okay, you might think maybe size is a factor. So we compare a small, a medium, and a large graph as well."
- On domain: "the variance between the different knowledge graphs would be more impressive than just adding a ton of competency questions to the same sort of like just drug discovery or just molecular stuff. We need to have something that is a bit out of that spectrum."
- Why external partners are needed: "Biotope needs to get the people to reveal what they care about semantically. So we need people with actual use cases" — someone who "knows what they're doing and who also can give us the competency questions."
- Example named: **"E1"**`[sic?]` and their **crop knowledge graphs** / "net miner"`[sic?]` infrastructure — "about the same age or even older than BioCypher, but it's just in a different area. Also semantically." Their input would be someone who knows those graphs intimately and can formulate the CQs; Biotope would grill them on purpose and build something, "and then the real value is in the competency questions."
- Sebastian said he has probably collected more candidate graphs — "it's too many by now. So I made a point of collecting all of them, so I need to go back to these records."

**Extending with external data — criterion set by Sebastian:** "Only if the competency questions are good… that is the main thing that the reviewer will look at if we say, yeah, we base our assumption on 13 questions. They will just say, yeah, that's not enough. So if we can find external data sets with competency questions, that's good. If it's just data set without competency questions, then I don't think it's going to matter too much."
- Asked whether he knows a candidate (raw data + KG + CQs), Sebastian said no and recommended **deep research**: "I don't trust myself knowing everything… You constantly come across new things that you just have never heard of." Vlad said he would find them.

**Open Targets as the next graph.**
- Sebastian: "Yes, that is all open. That is all open."
- The **Open Targets adapter** Sebastian originally built is "plain BioCypher" and was "basically Paul's starting point"; Paul later "modernized [it] a little bit with this Jinja templating of his". It is **already openly licensed** (Apache 2, in the BioCypher organization) "so we can already leverage this and I already did in Biotope."
- **Paul's newer solution must not be used**: "it's not open and it's not licensed and we cannot just use it." Vlad: "I don't need to really use it. There are like 2 1/2 valuable ideas in there."
- Sebastian on Paul's work: "I think he spent way too much time on over-engineering the processing. It was already solved when I hired him. So it was already solved before I wrote the proposal." And on Julia: "one of the things that I noticed in this project is that Julia manages to have people work on the wrong thing for two years and then publish something that I thought about two years ago. That's really infuriating, but you know, it is how it is."
- **The "Karenina" preprint** contains "a big set of competency questions, including answers" used for benchmarking "this MCP stuff" — Sebastian estimated **more than 100** — shared in the repository, Apache 2, in the BioCypher organization. He said starting from a set of CQs "was one of the first things that we did when the Open Targets project started", and "we have experts given answers to these." Vlad: "I already know that."
- **Raw data**: freely downloadable from the Open Targets download section as "Pocket"`[sic? Parquet]` files. Asked whether it is raw or pre-processed, Sebastian: "it's already pre-processed via open targets" — "it's like a relational database with… many tables", **55 different datasets / 55 different tables** to select from; he said the semantic-abstraction step "is really good in this case" for that reason.
- **Croissant**: the Open Targets dataset was already used in the Croissant Baker paper — "from the pocket files, we can auto-generate the Croissant files", and Open Targets also has a **manually written Croissant file** used as the comparison in Croissant Baker. Sebastian: "I would just put these pieces together." He noted he wrote the original of this in **2023**.
- Sebastian's prediction: "if you have 55 data sets, each one in its own SQL table, essentially, you can come up with a couple of competency questions that require three or four joins, and then a graph will win, I have no doubt." Vlad: "We'll see, I guess that's why we run the experiments, right?" Sebastian: "Of course, of course. But it's just a question of how you define the competency questions."
- **Engineering/size concern raised by Vlad** (that Open Targets would be a build pain because of its size). Sebastian: "the OpenTargets graph… runs on my laptop. It's not like if you use Neo4j… a billion nodes is not a problem for Neo4j. So I don't think that's a huge issue." Build tooling "is a little bit less streamlined" (Paul worked mainly on the build), "but that doesn't really matter if you have the actual graph."
- **Paul has an existing artifact**: a **Neo4j dump** of one of his builds, shared with the **Open Targets Consortium**; Sebastian said Vlad can ask him for it. Vlad said he needs the raw data, not just the graph.
- **CQ selection method (agreed):** select a subset rather than all >100 — "select some that are good, like that are kind of close to each other. So you don't build the whole graph… that's one of the points in Biotope that you would build a subsection based on what you actually want to do." Vlad proposed grouping them by topic; Sebastian: "Yes, exactly. That's what I would have suggested. And then select for one topic, simple, medium, and hard questions." He expects the Karenina set to contain both simple retrievable questions and harder reasoning ones.

**Priority question asked and answered.** Vlad asked whether to squeeze in the Open Targets experiment this week or focus on extending the InTraC experiment by Monday's submission. Sebastian: for the five-pager, "having more competency questions would be [the priority]… But we get more competency questions, both from adding ones to InTraC and from adding open targets, which has already known competency questions."

## Stated next steps
- **Vlad — email the conference organizers** (done) asking how talks are selected / whether a paper is required, and about the (passed, optional) abstract.
- **Vlad — submission target**: five-page short paper, or two-page demonstration + poster; deadline next Monday.
- **Vlad — extend the competency-question set for InTraC**, without extending the InTraC dataset itself; keep it as the small-graph example.
- **Vlad — run Biotope on the Open Targets dataset**, using competency questions selected from the "Karenina" preprint, grouped by topic, with simple/medium/hard questions within one topic.
- **Vlad — deep research** for external datasets/graphs that come with good competency questions, preferring a domain outside drug discovery / molecular biology.
- **Sebastian — go back through his collected records** of candidate knowledge graphs for one from a sufficiently different domain.
- Vlad stated an internal **full-preprint target of end of September**.
- Vlad to keep Sebastian updated; both said they would talk again later the same day.

