# Changelog

## [1.0.0](https://github.com/biocypher/biotope/compare/biotope-v0.10.0...biotope-v1.0.0) (2026-11-06)


### ⚠ BREAKING CHANGES

* remove the contract store and the extraction run state
* __field_refs__, the 0.9 root header and record-set comment, version 1 run reports and the sc:FileObject check are removed.
* annotate set --table refuses the readable form of a table ID.
* refuse overlapping datasets and name what add and extract leave out
* let projects write their extractors and list their extractions
* let project.yaml hold one purpose text
* remove the requirement binding and its check
* stop writing config keys nothing reads
* let the agent set project metadata with options
* remove annotation validation
* biotope mv no longer moves data to another filesystem.
* key a records file's extraction state by its whole name
* read project.yaml only from .biotope
* drop add --force, which did what --rebake does
* name each manifest after its data's whole path
* one annotation file per dataset holds what people write about it
* biotope mv carries a moved file's IDs into its source packages
* give files and tables IDs from their paths in the dataset
* biotope writes only in its own places and never to git
* a source revision covers structure only
* retire Pipeline.dependencies; run.json records declared distributions
* graph check enforces the topology layout

### Features

* a source revision covers structure only ([b7a398b](https://github.com/biocypher/biotope/commit/b7a398bbec8aaff81748edc4a2b2f74f0fbe2d2c))
* biotope mv carries a moved file's IDs into its source packages ([396bbc4](https://github.com/biocypher/biotope/commit/396bbc4786c9680aef9b7d6a49693981fbeaa471))
* biotope writes only in its own places and never to git ([79150fb](https://github.com/biocypher/biotope/commit/79150fb15c3af27b498ea376c9d415c1efc931d4))
* extract records from local documents under a reviewed schema ([2c0cd49](https://github.com/biocypher/biotope/commit/2c0cd49e3be71cbe0aaa13cc74a4c059d6cf0265))
* give files and tables IDs from their paths in the dataset ([a358711](https://github.com/biocypher/biotope/commit/a3587116a46a9ad7c5ba32dfd80094b3a706a66b))
* graph check enforces the topology layout ([21a35ad](https://github.com/biocypher/biotope/commit/21a35ad56bb2d6c38beb395c7b7278c5d9ca359a))
* graph check reports topology properties the export reserves ([fa18e5b](https://github.com/biocypher/biotope/commit/fa18e5b4c8b2b076bdb2c78e036660376b4f174e))
* **graph:** export the graph as one SQLite database ([e828f79](https://github.com/biocypher/biotope/commit/e828f793005f2fe04241a726cd51c02eb7ead0a5))
* **graph:** export the graph as one SQLite database ([b5947bb](https://github.com/biocypher/biotope/commit/b5947bb5bb8af3066eed80dd4190ee79b88b1b5d))
* let project.yaml hold one purpose text ([9dea646](https://github.com/biocypher/biotope/commit/9dea646b30ac1b7e4e639a1737bb142acef40c17))
* let projects write their extractors and list their extractions ([fc9998e](https://github.com/biocypher/biotope/commit/fc9998eff2d2bd2371f98c0a6247ef096fbbc0a8))
* let the agent set project metadata with options ([06bdc73](https://github.com/biocypher/biotope/commit/06bdc73694ea625258b5d8c6687d2ec2c131a496))
* make extraction reviewable and recoverable after the AC-12 trial ([be70e89](https://github.com/biocypher/biotope/commit/be70e891f6a8004a0fd6120daaf1f0cfc00c816d))
* name the datasets and table IDs a refusal means, and drop redone ([bdc4952](https://github.com/biocypher/biotope/commit/bdc49524b9ddbead82bfe421acdcf3b83a352429))
* one annotation file per dataset holds what people write about it ([7c5d008](https://github.com/biocypher/biotope/commit/7c5d00878724e751a8b76a043e072c0632369d43))
* queue, mark and map inspect read descriptions with their annotation files ([bce8fc2](https://github.com/biocypher/biotope/commit/bce8fc218e99b57622d8db83d97cb1414113cf05))
* refuse overlapping datasets and name what add and extract leave out ([c2aa740](https://github.com/biocypher/biotope/commit/c2aa740f3cd030deb593aef62dda6dab09d019c6))
* remove annotation validation ([6957b75](https://github.com/biocypher/biotope/commit/6957b7524dc367a734306d2611871d0590777eb0))
* remove the requirement binding and its check ([5d8be47](https://github.com/biocypher/biotope/commit/5d8be478f2fc3cce575aab5c480c41be9f20308d))
* retire Pipeline.dependencies; run.json records declared distributions ([1dab7d5](https://github.com/biocypher/biotope/commit/1dab7d5685180c81d404432b8bd048eca697ff10))
* scaffold an extraction template marked as a placeholder ([1cabbf7](https://github.com/biocypher/biotope/commit/1cabbf7ece19e5c6957e90806b2b77b71691df6c))


### Bug Fixes

* a table read from a file set gets a loader that reads no single path ([f7c7e2a](https://github.com/biocypher/biotope/commit/f7c7e2a5f73fd5c1a40288af463cf80c9d084f83))
* accept a table's ID without percent-encoding in annotate set --table ([5515399](https://github.com/biocypher/biotope/commit/551539911026853f1a37dab71f8579cf37521fa0))
* an annotation file keeps its quotes, line width and indentation when biotope writes into it ([b351cbd](https://github.com/biocypher/biotope/commit/b351cbdb4e54c1184a255f97cd68f3fe22980065))
* annotate names a new file by its path, not its content hash ([e0a9d87](https://github.com/biocypher/biotope/commit/e0a9d877b0e7d17d9c40d34ec1f5ad7405453b03))
* answer the architect and Codex reviews of extraction ([709872c](https://github.com/biocypher/biotope/commit/709872ca3df2d536f21f9e5773e6b379bfd30dcb))
* apply an annotation that names a column with a number ([565f2a9](https://github.com/biocypher/biotope/commit/565f2a97686cdfe41027f7f2760a0d58f68344e3))
* check a move's new IDs for collisions before mv moves anything ([20dbae1](https://github.com/biocypher/biotope/commit/20dbae1ab663d4dfc21b074e77c9723ce8cce727))
* check the annotation file before add takes over a description, and undo a failed takeover ([11ddee4](https://github.com/biocypher/biotope/commit/11ddee4582dabea5fcb0ad13d72b08ac94bffb30))
* close the second AC-12 run's extraction faults and extract in parallel ([8748423](https://github.com/biocypher/biotope/commit/8748423734315fb00cc36900d305413c86eaa3b7))
* commit extraction output only when a run completes, and realign evidence after a conversion change ([4e55b76](https://github.com/biocypher/biotope/commit/4e55b76e0ea2508fad64a0a8ffefcaf9ccca95ef))
* create the description's folder when add takes over a moved file's description ([65b5645](https://github.com/biocypher/biotope/commit/65b56457a419f2a3d461fec4b9f263519c896af4))
* describe an empty JSON object as a file, not a table without columns ([687f7dd](https://github.com/biocypher/biotope/commit/687f7dd9d27f486704ae3ea5221dc31560ad58a7))
* describe an extractor setting only when all stored records agree on its type ([0bf1b32](https://github.com/biocypher/biotope/commit/0bf1b32f570cf94d03029c923bda5ac603eeeda3))
* fail the check after a single file moves outside biotope under its own name ([e9c3131](https://github.com/biocypher/biotope/commit/e9c31315a0dca3f947e2feac5abd2d136696b14b))
* find the modules of distributions without top_level.txt on Python 3.10 ([f93b7a5](https://github.com/biocypher/biotope/commit/f93b7a54bbbe57b9e1ae0d3f9fb0a1913d98241b))
* flag records answered from memory and runs on an untried schema ([8ee4f3e](https://github.com/biocypher/biotope/commit/8ee4f3ef7c30db16265d917dc21d2a93200f13e3))
* flag running-head evidence and store each document as it finishes ([942ce76](https://github.com/biocypher/biotope/commit/942ce7675a860f49d148f8aa92e9e5c4a4fc9618))
* generate a renamed description into the root that already holds it ([aa64128](https://github.com/biocypher/biotope/commit/aa64128ce931951997a9a0a2a8d3d8cde2b2f078))
* **graph:** fit SQLite export to node columns and case-insensitive names ([6e9956a](https://github.com/biocypher/biotope/commit/6e9956ada4f0048e254e18bfd18aa72b4f9852fd))
* ignore the folders a graph build stages in ([11d4f3e](https://github.com/biocypher/biotope/commit/11d4f3e5344aed044336db464d5b9ee1e673d10b))
* ignore the metagraph page and staging folders in the example graph ([f11250b](https://github.com/biocypher/biotope/commit/f11250b21d1ecb4146d3d06e001dab7c100ef7d8))
* keep a moved file's checksum, date and size in its description ([a719c3f](https://github.com/biocypher/biotope/commit/a719c3fcef6b7b727d62707f6e392790f8bfbe04))
* keep a single file's move history through the next rebake ([674d0ac](https://github.com/biocypher/biotope/commit/674d0ac4680d68fb06c759b5dc2c57b2877f7e64))
* keep a single file's original path through every takeover ([dcee070](https://github.com/biocypher/biotope/commit/dcee07077eb2d43e8e1f1d71336a766ecff09d5e))
* keep a workbook's sheet name when mv renames the workbook ([9211090](https://github.com/biocypher/biotope/commit/9211090e181534267d5a489d7ae0cafd44260432))
* keep every earlier ID of a file moved outside biotope again ([332a8cd](https://github.com/biocypher/biotope/commit/332a8cd66cf9296f4696a969a83be57592a85115))
* keep extracted records out of a folder dataset that holds them ([31c771b](https://github.com/biocypher/biotope/commit/31c771b1e15ccd439b4d40c714ba79f1bfb9dff9))
* keep the lineage and status people give through a rebake ([517b3f5](https://github.com/biocypher/biotope/commit/517b3f5e24f41fd5121796e605d6a4902b7d4ec1))
* keep the name of a table inside a file when the file gains a second table ([f872412](https://github.com/biocypher/biotope/commit/f872412f77bf0a606e93551b7b6e137d64a8825d))
* key a records file's extraction state by its whole name ([fd872b1](https://github.com/biocypher/biotope/commit/fd872b111d712a28a5dc4646b0e72563aa011bb8))
* leave out exactly the copies and records a bake skips ([6ec9231](https://github.com/biocypher/biotope/commit/6ec9231693d7ad3ccf126b5714d73f76dcdc1b03))
* let mv move a package's revision only when it was current before the move ([cb1ac48](https://github.com/biocypher/biotope/commit/cb1ac485d9f6d3c32e2c3de6cf2c3cc80728f4a3))
* let mv put extraction records into a folder dataset's folder ([17c82ec](https://github.com/biocypher/biotope/commit/17c82eccdea6f17db4cbd58508f2be9a0cf95361))
* let the annotation file rename one of two file sets that share a name ([f5adec4](https://github.com/biocypher/biotope/commit/f5adec4f07bd8236806ddd5b54b482e2b35f1550))
* load extracted records through generated sources ([bc4a62a](https://github.com/biocypher/biotope/commit/bc4a62af21bcb68c1209e6b26d928250e3f75019))
* load extracted records through generated sources ([382670c](https://github.com/biocypher/biotope/commit/382670cfce0804c3a7f8a14233aeebaa0d4a85f8)), closes [#59](https://github.com/biocypher/biotope/issues/59)
* make extraction fail loudly on empty patterns and leftover state ([71b3be2](https://github.com/biocypher/biotope/commit/71b3be2259a26f861a8802f2a6b6cbfb26beaf04))
* make mv's advice for a move into another dataset keep the data ([61a2c7c](https://github.com/biocypher/biotope/commit/61a2c7cb7f2306f124a06b2dad9b0eb6a5ee678c))
* move the data last in mv, so a failed mv never loses the file it would replace ([0ba31a7](https://github.com/biocypher/biotope/commit/0ba31a7b232b2b1b8a075103d9fcd9c554afea47))
* mv writes a description as UTF-8 and the ID check skips entries without one ([b4730e4](https://github.com/biocypher/biotope/commit/b4730e459bf4fdeebd9fc803a0884d8e0f35a1f4))
* name a package for deletion only while its loader is a placeholder ([68d4ca3](https://github.com/biocypher/biotope/commit/68d4ca3a25e8739ba1916c5c218bbe7db42c19c8))
* name a records file as the topology layout names the class ([626166b](https://github.com/biocypher/biotope/commit/626166b97aec43e8eb99e85f98a33116dc951fae))
* name each manifest after its data's whole path ([a784bd9](https://github.com/biocypher/biotope/commit/a784bd94d20f0342db545fa270305cd548f86758))
* name graph check in the next steps mv prints ([2dfdfa5](https://github.com/biocypher/biotope/commit/2dfdfa55363287db852ed559133d4fa95761d87d))
* name packages and record classes after the decoded path ([eb3cff9](https://github.com/biocypher/biotope/commit/eb3cff9752c1784dba57407b9ffb935585b85825))
* name the old and new ID after a single file moves outside biotope ([fbefc42](https://github.com/biocypher/biotope/commit/fbefc42cd4e7d92af6197ea8e056ce808ccf9737))
* name the package to delete when a file moved outside biotope ([fa7ffa9](https://github.com/biocypher/biotope/commit/fa7ffa99fbc5de39fbc9d38e157daded1a639d80))
* never leave a described file out of a rebake as an identical copy ([603f3f5](https://github.com/biocypher/biotope/commit/603f3f58509298e2564b1de2333af3770f47ad7f))
* plan every move, file or folder, before mv touches the data ([d26908c](https://github.com/biocypher/biotope/commit/d26908c4e26694ad94004248ef6b33fd40028efe))
* prepare every change of a move before mv touches the data ([bef0238](https://github.com/biocypher/biotope/commit/bef0238fb4849133fc789a04d96848503d917d55))
* put every file and folder back when mv fails ([c490626](https://github.com/biocypher/biotope/commit/c4906265c2fab93d38f30af9fc9003fcaadaee8a))
* read a folder dataset's contentUrls from its folder in mv ([6bad761](https://github.com/biocypher/biotope/commit/6bad7611bc968713c21a6c940d70da6d3332afcb))
* read annotation dates as written and write mark's description atomically ([bbbe93b](https://github.com/biocypher/biotope/commit/bbbe93b3ee4797ad250a2797551518172c202191))
* read project.yaml only from .biotope ([bb2b626](https://github.com/biocypher/biotope/commit/bb2b626e4a9936b609b7efaf6e84264b41c3eb3b))
* record where the packages last declared a single file's path ([633d147](https://github.com/biocypher/biotope/commit/633d147d20d55481dd2977df04d6473a923f89bd))
* refuse a move to a path that differs only in case from an identical copy ([8c8951f](https://github.com/biocypher/biotope/commit/8c8951f99cf834035b1b287cb11d7f06708926f1))
* refuse an mv --force onto a file another description holds ([79e1fae](https://github.com/biocypher/biotope/commit/79e1fae9bed950f3b6f5ba6f8c015678a9ba8710))
* refuse an mv whose destination already has an annotation file ([09155e9](https://github.com/biocypher/biotope/commit/09155e92312f1f535618ec9201175fc5b67fe0f2))
* refuse mv of a dataset into the folder of another dataset ([cd0d4a0](https://github.com/biocypher/biotope/commit/cd0d4a09417b87bb9d73a039f9168a2af9e66532))
* refuse mv of a file whose move outside biotope is unresolved ([ea4d433](https://github.com/biocypher/biotope/commit/ea4d433659ec57bf07f2b2a10b9b6e6640c0ef6f))
* reject paths that differ only in case before leaving out identical copies ([81ec187](https://github.com/biocypher/biotope/commit/81ec187a2d50360c37b260197e69bc361decf162))
* rename a table on mv only when the bake named it after its file ([c27dc5d](https://github.com/biocypher/biotope/commit/c27dc5d28eb0dea7dcf9cc33d7f4df8bc740985a))
* rename moved data without copying it ([b34cdaf](https://github.com/biocypher/biotope/commit/b34cdaf8952614490a750ed60fdd0deb7b36e010))
* source generate makes no separate source from a sameAs copy ([174e0d0](https://github.com/biocypher/biotope/commit/174e0d029f75645e6c504caaf4b622ae951e173d))
* stop writing config keys nothing reads ([c81ebc2](https://github.com/biocypher/biotope/commit/c81ebc28a02e6b8a748555c1356dea4b947abb2c))
* take packages_distributions from importlib-metadata below Python 3.12 ([25b1c21](https://github.com/biocypher/biotope/commit/25b1c211624219c8af6f5ef91b274284d7fea1e9))
* warn once about each ignored file a command writes ([cbe88f2](https://github.com/biocypher/biotope/commit/cbe88f2077e8854f7780101603aec0409f084961))
* warn when a refresh rewrites a description that git ignores ([c8def90](https://github.com/biocypher/biotope/commit/c8def9086536d32f39c45b173c7c8dd69dfc623d))
* write every description through write_description ([ab7cf16](https://github.com/biocypher/biotope/commit/ab7cf16584217773b0edd5fba609fba5c7cc9671))
* write graph check's Pyright configuration outside the project ([7ee04a3](https://github.com/biocypher/biotope/commit/7ee04a3f66b534d2e87fad529d261bb4db133758))


### Documentation

* add system_docs for agents that develop Biotope ([c903d36](https://github.com/biocypher/biotope/commit/c903d365882833deeaacb24d6312897ae870cb3b))
* add the agent guide, the spec format and the B1 extraction spec ([aa4e3ef](https://github.com/biocypher/biotope/commit/aa4e3efc6f5291403b9722ed7236fb8d7eaab63f))
* add the B2 and B3 specs ([26a798d](https://github.com/biocypher/biotope/commit/26a798d7affb7b53caae186e2ec47bbf98eedce6))
* add the B2 spec (project layout, annotation file, stable IDs) ([911b21a](https://github.com/biocypher/biotope/commit/911b21aa9a76873eacef3be4795246c4f2f1ad2d))
* add the roadmap for data products ([05c5c0f](https://github.com/biocypher/biotope/commit/05c5c0fee72ee2c5978e7f6cf92d6b7b26d23f60))
* agree the purpose's questions before modelling ([a8491bf](https://github.com/biocypher/biotope/commit/a8491bfb16c92d09987ed53c6171907d762f9943))
* answer the first review of the B2 and B3 specs ([4c5f9a4](https://github.com/biocypher/biotope/commit/4c5f9a409cd7b06ae968afc4825984277038e6f6))
* answer the second review of the B2 and B3 specs ([a68c75a](https://github.com/biocypher/biotope/commit/a68c75a9d3d61e4389469be41b9d03762d43969b))
* delete the B2 spec before merge ([d132397](https://github.com/biocypher/biotope/commit/d1323971d759a37e56e037bd9aefd83002a7509f))
* delete the withdrawn B2 and B3 specs and their research note ([ef91645](https://github.com/biocypher/biotope/commit/ef9164521f1f2b81e6bb9965a9e28e9de4d5894d))
* describe the graph workspace rules on the project layout page ([a2be17f](https://github.com/biocypher/biotope/commit/a2be17f0594b76102353cf977c4ea5937439b9b9))
* document extraction and route documents through it in the skill ([6455f37](https://github.com/biocypher/biotope/commit/6455f375c17230d6d2740e2c1095843d9f4dac0b))
* document where projects write, the annotation file, stable IDs and the refresh ([3219cae](https://github.com/biocypher/biotope/commit/3219caee81e6fea0035bad5a23b2f9d3715a8f36))
* drop deleted pages from the navigation ([714854c](https://github.com/biocypher/biotope/commit/714854ccd37585a8dd0b4d5526e739c3e87e761a))
* give extract run every dataset the schema reads in the refresh ([a292b45](https://github.com/biocypher/biotope/commit/a292b453baae2fe1e7ca05143e3b636a232e4dab))
* have the agent ground schemas in questions and check try output ([2764489](https://github.com/biocypher/biotope/commit/2764489384780f9103e75b1e0853af82a543e9dc))
* limit B1's interfaces to its seams and answer the second review ([6cf4461](https://github.com/biocypher/biotope/commit/6cf4461f5c1d1f0f52a9323983da2b1410894367))
* list mv's refusals of unresolved moves and moves into another dataset ([0885429](https://github.com/biocypher/biotope/commit/08854294185a9bf6c3fc2adb76389bae47ca9909))
* make decisions an input dataset and reuse Croissant hashes for releases ([57e2f62](https://github.com/biocypher/biotope/commit/57e2f6296b32d1f7a7006715819d10d7ab9b324a))
* make natural keys aliases in registered kinds in roadmap decision 10 ([ca1279b](https://github.com/biocypher/biotope/commit/ca1279ba561785ab6a507c5afb626e3e80cd2dc1))
* make the B1 spec buildable after the first review ([4881f39](https://github.com/biocypher/biotope/commit/4881f3960eb793c082003d25c26457ad78f7c4d2))
* make the extraction skill re-check schema changes and redo wrong documents ([46d318e](https://github.com/biocypher/biotope/commit/46d318e9f9429ec31465c2c41f1e94c0fecca784))
* move the extraction contract and the install route into the skill ([eab872c](https://github.com/biocypher/biotope/commit/eab872c2b80b12d2c149cd86d84e81f47519a0a0))
* name a source root with --package when two datasets share a last name ([66a2737](https://github.com/biocypher/biotope/commit/66a273770425d51b3dfb5a8007555c530025d634))
* name REACH, the ELIXIR Atlas and InTRAC in AGENTS.md as [#53](https://github.com/biocypher/biotope/issues/53) does ([2fec510](https://github.com/biocypher/biotope/commit/2fec510f98a61d04e9cc8ac05847d77fc6d65989))
* name the unanchored data/ rule in the .gitignore advice ([a7b699a](https://github.com/biocypher/biotope/commit/a7b699afa779dd338d542e536f4b8b191db36660))
* narrow mv's refusal of moves into another dataset to what its bake describes ([cbeef44](https://github.com/biocypher/biotope/commit/cbeef442cced7b2d024c3ab6fb2b8572a933cf26))
* open every spec with its gap and what biotope already does ([0e868ec](https://github.com/biocypher/biotope/commit/0e868ec37937645698c89fc6c62d7dc86b604cb6))
* point agents to [#53](https://github.com/biocypher/biotope/issues/53) as the source of truth for new work ([e5c37f7](https://github.com/biocypher/biotope/commit/e5c37f7dde47bd937e2e5914b2d63eea89a190f1))
* read stable IDs back from where they are stored ([d5787d5](https://github.com/biocypher/biotope/commit/d5787d583f3b841776ce4b879f0538be288367aa))
* record B1 research on extraction tools and models ([a321239](https://github.com/biocypher/biotope/commit/a321239103bbbf03b5ede51f4ef53995b56c1956))
* remove the development ideas page ([ed4cd1a](https://github.com/biocypher/biotope/commit/ed4cd1a4afbd29b4f1eee7c4a3eb6eb0fe5aef49))
* research what B2 and B3 can reuse ([6aa976c](https://github.com/biocypher/biotope/commit/6aa976c8b5a3112ab9418fa485732be5b4f82f57))
* rewrite the B1 spec around goals, scope and interfaces ([ff193e6](https://github.com/biocypher/biotope/commit/ff193e63a666c279ce3a25ade32d631b8e0ed22d))
* rewrite the public docs for using Biotope through an agent ([8dbdfc0](https://github.com/biocypher/biotope/commit/8dbdfc0348519d1ebecbdb4598f7c28c0f46bae6))
* roadmap from the north star in [#53](https://github.com/biocypher/biotope/issues/53), retire the 22 October plan ([05aa413](https://github.com/biocypher/biotope/commit/05aa413c84688206bf5976ea0ffe07cb3d39d146))
* run extract run in the refresh and after mv of documents ([c89f952](https://github.com/biocypher/biotope/commit/c89f9520423a513a4172778c7fdfe6d2ce9747d1))
* run extract run in the scaffold's refresh recipe ([4b67e41](https://github.com/biocypher/biotope/commit/4b67e41515a22e4bdead56295bb1e2e22d4cca56))
* say a build writes CSV, Parquet or SQLite ([fd2ef9c](https://github.com/biocypher/biotope/commit/fd2ef9cd2e5c6afac20912d60f63987033a8af2b))
* say generation skips a document once an extraction has read it ([6ee813a](https://github.com/biocypher/biotope/commit/6ee813a1cb4f73ef6b5d562ce809dfc85117cc9a))
* say that a file whose table has no columns is a file ([f551464](https://github.com/biocypher/biotope/commit/f551464a8cf9ad847b0faea4963c0cf3b75e1b03))
* say that a move outside biotope only warns for an excluded source ([73100e8](https://github.com/biocypher/biotope/commit/73100e8d1d7c3fb73bdadb7ee42cd98dbec1ab78))
* say what mv refuses to do ([6caa4d5](https://github.com/biocypher/biotope/commit/6caa4d5b0c2a330576b40580cc289408ab1017cd))
* settle leaves, record IDs and curated manifests in the B1 spec ([cf3f0e3](https://github.com/biocypher/biotope/commit/cf3f0e33caeb490355cbda9a0d84bb44bccf10d4))
* stable IDs come back from where they are stored, and B3 closes ([27b3b06](https://github.com/biocypher/biotope/commit/27b3b06191dda713d009630b09055cf14f757931))
* state the spec rule and delete the B1 spec ([61d5142](https://github.com/biocypher/biotope/commit/61d51425e9e639eb6625cb7abf4a4953d1e8179c))
* teach the skill and the scaffold the annotation file, the topology layout and the refresh ([32fdaa2](https://github.com/biocypher/biotope/commit/32fdaa204aa2c3a16298d0c49f73eee4a9bbddb5))
* write mappings in named modules ([fac6ebb](https://github.com/biocypher/biotope/commit/fac6ebb27c4c84925d65602a99bcaad9035c1a29))
* write the roadmap from scratch from the north star in [#53](https://github.com/biocypher/biotope/issues/53) ([99e4977](https://github.com/biocypher/biotope/commit/99e497762391381f0735f759a17d55cac95cdbd9))


### Build System

* require croissant-baker 0.8.1 ([acd67cf](https://github.com/biocypher/biotope/commit/acd67cfcb9040ded78b1bd5257b21f4d66bdfb2c))
* take packages_distributions from importlib-metadata on Python 3.10 ([ff59ff4](https://github.com/biocypher/biotope/commit/ff59ff45a888f541f2c5b54dbcebba3a11808835))
* type-check the extraction package strictly ([9cf6c5f](https://github.com/biocypher/biotope/commit/9cf6c5fe010edc8412f44a4c5667e756079f5906))


### Refactoring

* delete DatasetStats and summarize_metadata ([dd68cdd](https://github.com/biocypher/biotope/commit/dd68cdd6b4197a119dd7dbe1289aeadce16c7807))
* delete update_manifest_status, which nothing calls ([be49aaa](https://github.com/biocypher/biotope/commit/be49aaa46401f7f5619a3ae129317973d09f5d11))
* drop add --force, which did what --rebake does ([6e292bd](https://github.com/biocypher/biotope/commit/6e292bd49618d9d84ac5b1cca99f5bd62472bb5c))
* drop the overrides that a folder bake never receives ([188b268](https://github.com/biocypher/biotope/commit/188b268d662c6adc52c0e9f59608b4a1b40693f0))
* drop the unbuilt settings layers from the project model ([2d09947](https://github.com/biocypher/biotope/commit/2d09947c009ec3edb16d10e3bfc945c9531358ed))
* keep one helper for the files a table reads ([7a371b8](https://github.com/biocypher/biotope/commit/7a371b80e480efaf02007cb5cc9c5b6313d12fcb))
* keep the reserved property names in the topology module ([cd2707a](https://github.com/biocypher/biotope/commit/cd2707a90f0e489ba503d0d546fc76d5f20d7f57))
* leave the scaffold's extraction package empty ([ca94ba8](https://github.com/biocypher/biotope/commit/ca94ba8afe5337b4adac5fd346e14ce8869d7195))
* name the description reader for the write it makes ([94d290e](https://github.com/biocypher/biotope/commit/94d290ec047342829adac3d9da73515ba2f08220))
* name the reserved property check's set intersection ([84046f6](https://github.com/biocypher/biotope/commit/84046f6b405cf23348b6a47d0b86540020b9eaa4))
* remove support for files written by Biotope 0.9 and 0.10 ([b331494](https://github.com/biocypher/biotope/commit/b3314943f60b020e0e85eee4b8ba474153f60774))
* remove the contract store and the extraction run state ([1e70dbd](https://github.com/biocypher/biotope/commit/1e70dbdda44e11bad947054a321a76f893582a43))
* type the extract command's helpers ([35aabf6](https://github.com/biocypher/biotope/commit/35aabf69674eb0efcc63b5f730914c71a06a5701))


### Miscellaneous

* release 1.0.0 ([14235dc](https://github.com/biocypher/biotope/commit/14235dc477c92b70bece69926bf5e48a2428017c))

## [0.10.0](https://github.com/biocypher/biotope/compare/biotope-v0.9.1...biotope-v0.10.0) (2026-09-28)


### ⚠ BREAKING CHANGES

* **graph:** project validation callbacks and per-capability states are gone, so builds no longer verify scientific expectations; structural checks are not equivalent, and review-time independent reads replace them. interpretation no longer travels inside the graph; concept and property descriptions in schema_config.yaml, run.json policies and scope, and graph/ASSUMPTIONS.md replace the query context, so graph/build/ must travel with the graph. `biotope graph quality` prints its results instead of writing graph/reports/quality.json; `biotope graph metagraph` writes graph/metagraph.html by default. schemas are never re-rendered. Generated and 0.9 schemas no longer follow manifest changes; each change surfaces as source.drift for review. Authored types are not compared with Croissant dataType or nullability. new scaffolds bind fields through @ids scoped under their RecordSet; other ids produce source.unscoped_field, while an existing `__field_refs__` mapping still binds them. a new package's name depends on the directories that already exist, so it can differ from a from-scratch generation. removed keywords such as SourceContract(generated=) and Pipeline(query_context=) fail with ordinary TypeErrors; run.json and definition reports are schema_version 2 (replacement and --report accept 1 and 2). See docs/migration.md for the 0.9 migration steps.
* **graph:** builds no longer write topology.json, ontology.ttl, query_context.json, provenance.jsonl or BiotopeQueryContext rows. Provenance is reached through each object's biotope_provenance_id in provenance.json. `biotope graph build` defaults to `<graph>/build` and replaces the previous generated build instead of requiring a new --out directory; --out still chooses another location. Export is headless and labels drop the namespace (for example Gene rather than CvdGene), so Entity is no longer reserved.

### Features

* **graph:** generate complete source inventories and check drift, retire validation and query context ([957b2ce](https://github.com/biocypher/biotope/commit/957b2ce2fda2174bf5c91b0a54b46e6dd3c1ae38))
* **graph:** integrate authored source contracts, staged builds and a provenance catalog ([4686916](https://github.com/biocypher/biotope/commit/468691669127d343f0fbb008afd76d388b966e90))


### Bug Fixes

* **add:** register byte-identical files once ([90a2838](https://github.com/biocypher/biotope/commit/90a283896c1f02a7ae59dae03c7fe53d3f313e1f))
* **add:** register byte-identical files that Baker parses once ([160e2ae](https://github.com/biocypher/biotope/commit/160e2ae9bf463ec690ec55537a4ce4eb2128f6f5))
* **add:** skip byte-identical copies before Baker parses them ([287bef0](https://github.com/biocypher/biotope/commit/287bef05d4ddc43d4bf2e3b7d791012b5ba16cf3))
* **graph:** check exported objects in a write that no build context checked ([924c06c](https://github.com/biocypher/biotope/commit/924c06c24657c3688b1be9ef03695b5b39fccf7d))
* **graph:** end a failed run with its error and log phases without a terminal ([845a229](https://github.com/biocypher/biotope/commit/845a229d4960a9b51c48b4ad3e1e8eb2606bb8df))
* **graph:** end a failed run with its finding code and log one line per phase ([907792e](https://github.com/biocypher/biotope/commit/907792e4428f80a894f8e14e9b32c20fe5649b7a))
* **graph:** keep descriptions of node properties named source or target ([bea90ae](https://github.com/biocypher/biotope/commit/bea90ae04e874b748c07268bd2e00a999ab8e37b))
* **graph:** record the libraries graph code imports and warn when they are undeclared ([789da09](https://github.com/biocypher/biotope/commit/789da09d77a9d0f4ea7d868426b2282c85f4449b))
* **graph:** refuse unexportable values when a mapping emits them ([7b4bdf1](https://github.com/biocypher/biotope/commit/7b4bdf19ab3f708e6dc48358b0fbf89043a452a5))
* **graph:** size the Neo4j read buffer to the export's longest line ([c2f6757](https://github.com/biocypher/biotope/commit/c2f6757e71616d63ddea615aec48ae5bd20f9bd9))
* **graph:** state the oversized-value threshold in characters and document the read buffer ([e2b5e82](https://github.com/biocypher/biotope/commit/e2b5e8210a7854931c82abddf9103346c2f74a1c))


### Performance Improvements

* **graph:** validate each value once per step and drop repeated work ([1fc51b7](https://github.com/biocypher/biotope/commit/1fc51b7a055acdc604d5bc16eb1b2f2bd609e910))


### Documentation

* document the 0.10 graph project shape and how to migrate to it ([31ee718](https://github.com/biocypher/biotope/commit/31ee7180422fca8e6d2becbfc84f4ab8e8376887))
* **skills:** describe structured files Baker cannot parse as record sets ([d70ae3d](https://github.com/biocypher/biotope/commit/d70ae3ddcc095f5113b7ffdb2dbb7d5a0935a33a))
* **skills:** install reader libraries from graph/pyproject.toml ([683efbb](https://github.com/biocypher/biotope/commit/683efbb1a2fc75d5ee812d898094521966f91aac))
* **skills:** rework biotope-croissant around the generated source inventory ([a1d8c92](https://github.com/biocypher/biotope/commit/a1d8c92d46f7fb56da1735b6da521c359a52a2a0))
* **skills:** say that aliases and missing-value tokens are declarations only ([5a7ffce](https://github.com/biocypher/biotope/commit/5a7ffcee319c71a04ddfd7513bee0ad36698fa58))


### Build System

* **release:** release breaking changes before 1.0 as a minor version and describe the package ([df3fa17](https://github.com/biocypher/biotope/commit/df3fa1733e86a8c4dd2ad903f198ed93e3cfdacd))


### Refactoring

* **graph:** raise value problems in one helper and share the item loop ([3c4e7dc](https://github.com/biocypher/biotope/commit/3c4e7dc375f2beff125df2e96b354f15703cd5f2))

## [0.9.1](https://github.com/biocypher/biotope/compare/biotope-v0.9.0...biotope-v0.9.1) (2026-09-15)


### Bug Fixes

* correct validation examples and documentation publishing ([b355807](https://github.com/biocypher/biotope/commit/b355807d75525e0a2c3ebfdb680c83e3a925d7bf))


### Documentation

* prepare Biotope documentation for the public release ([aa38846](https://github.com/biocypher/biotope/commit/aa3884629a0642d8709a8935ef564ea7eac301b1))
* prepare documentation for the public release ([17dd52d](https://github.com/biocypher/biotope/commit/17dd52db8b4c439f98a3802a4c4dbb186522e7ff))

## [0.9.0](https://github.com/biocypher/biotope/compare/biotope-v0.8.0...biotope-v0.9.0) (2026-09-15)


### Features

* add typed Python graph pipelines and update croissant-baker ([7c0b564](https://github.com/biocypher/biotope/commit/7c0b5646b4a94dc9a79b8ae083f27cf7b3493fbe))
* show bake progress, stream the baker's warnings, keep every checksum ([0360e5f](https://github.com/biocypher/biotope/commit/0360e5fa26af00843c2f0299ec321ffb782189d4))


### Bug Fixes

* **ci:** install published baker and honor Python matrix ([c758287](https://github.com/biocypher/biotope/commit/c75828733b7fc6e5a7e47d8f85218fa5f4fe292e))
* work with croissant-baker's compression-decoupling refactor ([73975fd](https://github.com/biocypher/biotope/commit/73975fd3b8e41ca4237463378a8fe443019b4ef2))


### Documentation

* finalize typed graph engine specification ([7a3614a](https://github.com/biocypher/biotope/commit/7a3614ac15b07fbaf5b82939dbd8723da84569c5))
* note the claims() refusal channel as deferred ([9465817](https://github.com/biocypher/biotope/commit/94658175a519362ef437c1db96783320e83cd0be))

## [0.8.0](https://github.com/biocypher/biotope/compare/biotope-v0.7.1...biotope-v0.8.0) (2026-06-29)


### Features

* decouple biotope runtime from biochatter and biocypher ([1a100f8](https://github.com/biocypher/biotope/commit/1a100f8e4c2a2a34d61349b0e3c0de2138b6dde3))
* decouple biotope runtime from biochatter and biocypherinitial commit ([11eb5f0](https://github.com/biocypher/biotope/commit/11eb5f06f54974b74638a99aa390a20d86ba72de))

## [0.7.1](https://github.com/biocypher/biotope/compare/biotope-v0.7.0...biotope-v0.7.1) (2026-05-28)


### Documentation

* **landing:** align commands surface and link tutorial as canonical onboarding ([#28](https://github.com/biocypher/biotope/issues/28)) ([2862055](https://github.com/biocypher/biotope/commit/2862055c7d5f6a3cdd635fcc76df88696d3c2de7))
* **tutorial:** admonition fixes + terminal-styled console blocks ([#30](https://github.com/biocypher/biotope/issues/30)) ([5e864b4](https://github.com/biocypher/biotope/commit/5e864b49555c8f74200ba371080971216fb0e24c))

## [0.7.0](https://github.com/biocypher/biotope/compare/biotope-v0.6.1...biotope-v0.7.0) (2026-05-25)


### Features

* **API:** Croissant-driven KG workflow + agent-supported knowledge ingestion ([#23](https://github.com/biocypher/biotope/issues/23)) ([57f1872](https://github.com/biocypher/biotope/commit/57f18728b71383712f9415c99f7d07cdeb81dd5e))

## [0.6.1](https://github.com/biocypher/biotope/compare/biotope-v0.6.0...biotope-v0.6.1) (2026-05-25)


### Documentation

* **examples:** add airports-notes.md and airport-hubs.csv ([#24](https://github.com/biocypher/biotope/issues/24)) ([29b1487](https://github.com/biocypher/biotope/commit/29b14878f177a408b03d2cffacc53b4a69f29ed6))

## [0.6.0](https://github.com/biocypher/biotope/compare/biotope-v0.5.0...biotope-v0.6.0) (2026-05-19)

### Features

- add bio.tools registry integration to search command ([72b996c](https://github.com/biocypher/biotope/commit/72b996cf190c02e3c35dba147cf10e5717bfc78c))
- add composite scoring option to search command ([d3c7d68](https://github.com/biocypher/biotope/commit/d3c7d681573cc32dd04041dd7d0ab7eb7bc074bf))
- Add GitHub star count ranking to biotope search ([7439f2b](https://github.com/biocypher/biotope/commit/7439f2bf064289ffea5a5f571f7abd0e925c9179))
- add MCP registry status to biotope status command ([668e720](https://github.com/biocypher/biotope/commit/668e720d33b7f2a5873efbc8811884f02453dd8c))
- enhance add and annotate commands to skip biotope's own annotation files ([f38063e](https://github.com/biocypher/biotope/commit/f38063ef473335a9032fcc9d5471e15289f88a09))
- enhance bio.tools integration with smart column labeling and composite scoring ([9d32b83](https://github.com/biocypher/biotope/commit/9d32b83a9aee094f0da89aed501885586c072de0))
- enhance file management capabilities with mv command and improved metadata handling ([#6](https://github.com/biocypher/biotope/issues/6)) ([21c9e3d](https://github.com/biocypher/biotope/commit/21c9e3d30aa83f0826045fa7e8357a2cda8c2c9a))
- **get:** Add file download and annotation command ([25de2a1](https://github.com/biocypher/biotope/commit/25de2a1850d973190482888e547005446212fa6f))
- git-like metadata management ([1cea6f6](https://github.com/biocypher/biotope/commit/1cea6f6ad8d289a68737138d958daab4e660d6e1))
- git-like metadata management ([1cea6f6](https://github.com/biocypher/biotope/commit/1cea6f6ad8d289a68737138d958daab4e660d6e1))
- implement biotope search command for MCP registry integration ([1aabef1](https://github.com/biocypher/biotope/commit/1aabef155cbab52df7c31f11f6b41fbe96dba740))
- implement registry infrastructure for BioContext integration ([dfebf6d](https://github.com/biocypher/biotope/commit/dfebf6d2e5286da15eee9594a20a4e505cb579ff))
- improve relevance scoring and GitHub API integration ([64ac804](https://github.com/biocypher/biotope/commit/64ac804308373ff6f7d11c23e48a943efbd23278))
- setuptools entry point ([7e1f4c5](https://github.com/biocypher/biotope/commit/7e1f4c56478d7fb884b68feeb21fcae97dc3b0cd))
- update init to more comprehensive workflow ([#4](https://github.com/biocypher/biotope/issues/4)) ([bab0fc7](https://github.com/biocypher/biotope/commit/bab0fc7f7e3d42a45d3702a98e196cdd0c8550ef))
- upgrade to git-on-top process, test battery, docs ([5531d10](https://github.com/biocypher/biotope/commit/5531d10f938a008c9f5de5f16c830f00ec3daf60))

### Bug Fixes

- improve error handling for registry cache loading ([efc1053](https://github.com/biocypher/biotope/commit/efc1053c4fc0e7c6c6994999783676a8adbd13c2))
- preserve registry ranking in combined search ([5106907](https://github.com/biocypher/biotope/commit/5106907d39490ebcf51263e099a2e8bfcf3111a7))

### Build System

- add release-please for automated version bumping ([6f82eba](https://github.com/biocypher/biotope/commit/6f82ebad2d8406866acc74764a1e8cdba0a473a2))

### Refactoring

- optimize score normalization in BioToolsRegistry ([c7d3791](https://github.com/biocypher/biotope/commit/c7d3791d5f3a305c7a445cfa7433ba7b7cb12518))
- streamline metadata context retrieval in Croissant file creation ([28001cb](https://github.com/biocypher/biotope/commit/28001cbbffffe01abb52af87e8a2b2634bc02b0f))
- streamline test setup and metadata handling ([4898529](https://github.com/biocypher/biotope/commit/4898529060560eab214161b1ce6dbded11dfa806))
- use sha256 to have the same hashes in different python sessions ([0ca1a16](https://github.com/biocypher/biotope/commit/0ca1a163862449b72178fab66a4acfdeaa6bc145))
