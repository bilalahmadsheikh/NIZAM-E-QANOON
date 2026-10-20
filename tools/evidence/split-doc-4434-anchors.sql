-- adopted by builder BZ 16 Oct 2026 (renamed from -DRAFT; applied by the owner-run batch).
-- DRAFT by agent K5 (15 Oct 2026, prepare mode; NOT applied). Source-verified boundary evidence anchoring expressions
-- 1-42 and 45 of document 4434 at their printed titles, for the reviewed plan
-- tools/evidence/multi-instrument-plans/doc-4434.json (to be adopted as doc-4434.json; 4434 then leaves
-- PRIMARY_DOCUMENTS in tools/materialize_multi_instrument.py).
--
-- Why: the materializer refused the plan on 13 Oct ('expressions [1..42] need a recorded confirmed_split boundary
-- candidate at their first span start'). The 42 legacy candidates were archived and deleted by
-- tools/prune_retired_instruments.sql (instrument_revision_archive_manifest batch 45fea3b9-16a6-42ac-b3bc-fcb521a0c294)
-- and were never adjudicated. Each is cited below, not revived (lead decision 13 Oct, route (a)). Expressions 43 and 44
-- already have confirmed_split candidates (a2b5033b..., a77aa5e2..., applied 13 Oct from split-doc-4434-boundaries-DRAFT.sql).
--
-- Every span start was checked against its printed title on the page image (title crops:
-- .artifacts/release-work-2026-09-24/claude/agK5/montage-1..8.png; full pages and sha256 per row below).
-- Four released starts are CORRECTED (lead decision 15 Oct under the owner's delegation; CLAUDE-CLAIMS 'OWNER (15 Oct, chat)'):
--   e3 792689 -> 792687; e10 793192 -> 793189 (+ 793192..; e9 keeps 793190-1); e20 794459 -> 794453 (BZ named 794456;
--   the title's first line is 794453 on p323); e39 794784 -> 794787.
-- NEW expression 45 (lead 15 Oct: e38 prints two titles): the Constitution (Amendment) Order, 1985, President's Order
--   No. 11 of 1985, starts at its printed title 794777 (p352); e38 (P.O. No. 6 of 1985) ends at 794776. No earlier
--   candidate existed at 794777, so its row cites none.
--
-- Keyed to the active UNRELEASED expression-0 instrument b59f4939-bef4-471a-ae10-790f1f7e0359 (observation 2810), as
-- the lead directed: no released instrument is touched by this SQL. Guards refuse unless the e0 instrument is the
-- active unreleased canonical one, every start block is on its stated page, and exactly 43 candidates and 43
-- confirmed_split adjudications exist afterwards. Idempotent (ON CONFLICT / NOT EXISTS).

\set ON_ERROR_STOP on
BEGIN;

CREATE TEMP TABLE k5_proposed(ordinal int, start_block_id bigint, source_page int, detected_title text, detected_kind text,
  detected_year int, detected_number text, archived_candidate_id uuid, archived_method text, archived_block bigint,
  archive_manifest text, corrected boolean, source_facts jsonb, renders jsonb, rationale text) ON COMMIT DROP;
INSERT INTO k5_proposed VALUES
    (1,792606::bigint,207,'The Constitution (First Amendment) Act, 1974','act',1974,'XXXIII','a064e800-f45a-4fcd-b68e-b9f6285b4a9b'::uuid,'nizam.multi_instrument_detector/1',792608,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 207 prints the title of The Constitution (First Amendment) Act, 1974 at block 792606 (''1The Constitution (First Amendment) Act, 1974'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 207, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p207.png", "render_sha256": "5c8f41198cc09eb6cd4e818036a27210d3d6861c42243c1cd2a361aaae0e3a56"}]'::jsonb,
     'Block 792606 (p207) begins The Constitution (First Amendment) Act, 1974 at its printed title. Supersedes, by citation, the unadjudicated archived candidate a064e800-f45a-4fcd-b68e-b9f6285b4a9b (nizam.multi_instrument_detector/1, block 792608).'),
    (2,792676::bigint,212,'The Constitution (Second Amendment) Act, 1974','act',1974,'XLIX','d173bb26-5051-430a-bb91-133b79652efb'::uuid,'nizam.multi_instrument_detector/1',792679,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 212 prints the title of The Constitution (Second Amendment) Act, 1974 at block 792676 (''1The Constitution (Second Amendment) Act, 1974'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 212, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p212.png", "render_sha256": "67d889efd2b4be612063f7cf2f8ecf1dfb281bb4a0384c75728f963a3f8024c0"}]'::jsonb,
     'Block 792676 (p212) begins The Constitution (Second Amendment) Act, 1974 at its printed title. Supersedes, by citation, the unadjudicated archived candidate d173bb26-5051-430a-bb91-133b79652efb (nizam.multi_instrument_detector/1, block 792679).'),
    (3,792687::bigint,213,'The Constitution (Third Amendment) Act, 1974','act',1975,NULL,'ce22a3c4-814d-4dfa-b147-62a5ff8ea00f'::uuid,'nizam.multi_instrument_detector/1',792689,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',true,
     '["page 213 prints the title ''The Constitution (Third Amendment) Act, 1974'' (b792687, note marker 2) and ''(XXII of 1975)'' (b792688) above ''[18 February 1975] An Act'' (b792689)", "page 212 before it ends the Second Amendment Act at s.3 and its assent footnote 1 (b792685); the p213 running header (b792686) stays with the Second Amendment Act", "the archived detector candidate sat at b792689, the date line after the title"]'::jsonb,
     '[{"page": 213, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p213.png", "render_sha256": "e5b8e3d81cd0378486849132999715a7aa209b24ed90404e2c050bad67ea05e3"}]'::jsonb,
     'Block 792687 (p213) begins The Constitution (Third Amendment) Act, 1974 at its printed title -- corrected from the released span start (lead 15 Oct). Supersedes, by citation, the unadjudicated archived candidate ce22a3c4-814d-4dfa-b147-62a5ff8ea00f (nizam.multi_instrument_detector/1, block 792689).'),
    (4,792704::bigint,214,'The Constitution (Fourth Amendment) Act, 1975','act',1975,'LXXI','ae454648-e8f9-4d1f-a949-004c816fb8f1'::uuid,'nizam.multi_instrument_detector/1',792707,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 214 prints the title of The Constitution (Fourth Amendment) Act, 1975 at block 792704 (''1The Constitution (Fourth Amendment) Act, 1975'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 214, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p214.png", "render_sha256": "a069d6d8fe35b2de2534b6206ea3a6a39a323c1c387a88643198bbfb822202d4"}]'::jsonb,
     'Block 792704 (p214) begins The Constitution (Fourth Amendment) Act, 1975 at its printed title. Supersedes, by citation, the unadjudicated archived candidate ae454648-e8f9-4d1f-a949-004c816fb8f1 (nizam.multi_instrument_detector/1, block 792707).'),
    (5,792866::bigint,222,'The Constitution (Fifth Amendment) Act, 1976','act',1976,'LXII','4c0e922c-dbc5-4fea-b7d1-acbd9b0d1ee5'::uuid,'nizam.multi_instrument_detector/1',792869,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 222 prints the title of The Constitution (Fifth Amendment) Act, 1976 at block 792866 (''1The Constitution (Fifth Amendment) Act, 1976'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 222, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p222.png", "render_sha256": "b12a67f2ace8129e5cf67dce1097970ee4b2fc09115bce043839866e9a019a53"}]'::jsonb,
     'Block 792866 (p222) begins The Constitution (Fifth Amendment) Act, 1976 at its printed title. Supersedes, by citation, the unadjudicated archived candidate 4c0e922c-dbc5-4fea-b7d1-acbd9b0d1ee5 (nizam.multi_instrument_detector/1, block 792869).'),
    (6,792963::bigint,228,'The Constitution (Sixth Amendment) Act, 1976','act',1976,'LXXXIV','ffe12af2-853a-4579-9624-291a571843b7'::uuid,'nizam.multi_instrument_detector/1',792965,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 228 prints the title of The Constitution (Sixth Amendment) Act, 1976 at block 792963 (''1The Constitution (Sixth Amendment) Act, 1976'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 228, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p228.png", "render_sha256": "e65d0efc73c8e9b497e84890fb02c6698f9ee757e1e9436b5d05defffaf497bb"}]'::jsonb,
     'Block 792963 (p228) begins The Constitution (Sixth Amendment) Act, 1976 at its printed title. Supersedes, by citation, the unadjudicated archived candidate ffe12af2-853a-4579-9624-291a571843b7 (nizam.multi_instrument_detector/1, block 792965).'),
    (7,792988::bigint,230,'The Constitution (Seventh Amendment) Act, 1977','act',1977,'XXIII','dc683bc3-8e7b-47f1-9ed7-91db258ea1e2'::uuid,'nizam.multi_instrument_detector/1',792991,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 230 prints the title of The Constitution (Seventh Amendment) Act, 1977 at block 792988 (''1The Constitution (Seventh Amendment) Act, 1977'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 230, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p230.png", "render_sha256": "84c3d5be05022d0a3f8134c8f4c151518b5fa4ecb651bf6ac3491cac4b341a84"}]'::jsonb,
     'Block 792988 (p230) begins The Constitution (Seventh Amendment) Act, 1977 at its printed title. Supersedes, by citation, the unadjudicated archived candidate dc683bc3-8e7b-47f1-9ed7-91db258ea1e2 (nizam.multi_instrument_detector/1, block 792991).'),
    (8,793014::bigint,232,'The Constitution (Eighth Amendment) Act, 1985','act',1985,'XVIII','05535d1b-342b-4fa3-8451-f5f1f7f0b6ec'::uuid,'nizam.multi_instrument_detector/1',793017,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 232 prints the title of The Constitution (Eighth Amendment) Act, 1985 at block 793014 (''1The Constitution (Eighth Amendment) Act, 1985'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 232, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p232.png", "render_sha256": "40580d0eb42781c98c02dffbb8b30e5c3670003db1735d26ff1b5ef9fcc90f96"}]'::jsonb,
     'Block 793014 (p232) begins The Constitution (Eighth Amendment) Act, 1985 at its printed title. Supersedes, by citation, the unadjudicated archived candidate 05535d1b-342b-4fa3-8451-f5f1f7f0b6ec (nizam.multi_instrument_detector/1, block 793017).'),
    (9,793182::bigint,242,'The Constitution (Tenth Amendment) Act, 1987','act',1987,'1','561d8f4d-aff2-4492-8463-6993d5ed7159'::uuid,'nizam.multi_instrument_detector/1',793184,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 242 prints the title of The Constitution (Tenth Amendment) Act, 1987 at block 793182 (''1The Constitution (Tenth Amendment) Act, 1987'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 242, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p242.png", "render_sha256": "08b29466f7ae2f6698dbd8d961ad15c9cb036062e321043bb8f91193ec267fc6"}]'::jsonb,
     'Block 793182 (p242) begins The Constitution (Tenth Amendment) Act, 1987 at its printed title. Supersedes, by citation, the unadjudicated archived candidate 561d8f4d-aff2-4492-8463-6993d5ed7159 (nizam.multi_instrument_detector/1, block 793184).'),
    (10,793189::bigint,242,'The Constitution (Twelfth Amendment) Act, 1991','act',1991,'XIV','93db16c9-25a3-4798-b392-970eaec35b8e'::uuid,'nizam.multi_instrument_detector/1',793195,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',true,
     '["page 242 prints, below the Tenth Amendment Act''s s.3, the first line of the next title, ''The Constitution'' (b793189, note marker 2), then the Tenth Amendment Act''s own assent footnote 1 (b793190)", "page 243 continues the title ''(Twelfth Amendment) Act, 1991'' (b793192), ''(XIV of 1991)'', ''[28 July 1991]''; its footnote 2 gives the assent of 27 July 1991", "the expression has two spans, b793189 and b793192 onward; b793190-1 (footnote 1, p243 header) stay with the Tenth Amendment Act"]'::jsonb,
     '[{"page": 242, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p242.png", "render_sha256": "08b29466f7ae2f6698dbd8d961ad15c9cb036062e321043bb8f91193ec267fc6"}, {"page": 243, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p243.png", "render_sha256": "e133c1c8bd5f6ffc2173cfbdf6abd5108be7553ee55870972be5fae26ceffb9a"}]'::jsonb,
     'Block 793189 (p242) begins The Constitution (Twelfth Amendment) Act, 1991 at its printed title -- corrected from the released span start (lead 15 Oct). Supersedes, by citation, the unadjudicated archived candidate 93db16c9-25a3-4798-b392-970eaec35b8e (nizam.multi_instrument_detector/1, block 793195).'),
    (11,793249::bigint,247,'The Constitution (Thirteenth Amendment) Act, 1997','act',1997,'I','59462c45-9282-4609-a950-aadd35ee6868'::uuid,'nizam.multi_instrument_detector/1',793252,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 247 prints the title of The Constitution (Thirteenth Amendment) Act, 1997 at block 793249 (''1The Constitution (Thirteenth Amendment) Act, 1997'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 247, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p247.png", "render_sha256": "c85ee9287c7274d8191b18ea76d8f84f1dbd81cd2861eb4510d82796d1f3f7b4"}]'::jsonb,
     'Block 793249 (p247) begins The Constitution (Thirteenth Amendment) Act, 1997 at its printed title. Supersedes, by citation, the unadjudicated archived candidate 59462c45-9282-4609-a950-aadd35ee6868 (nizam.multi_instrument_detector/1, block 793252).'),
    (12,793306::bigint,251,'The Constitution (Seventeenth Amendment) Act, 2003','act',2003,'III','169019e5-f5e7-447d-be90-5523eb2ac8f0'::uuid,'nizam.multi_instrument_detector/1',793309,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 251 prints the title of The Constitution (Seventeenth Amendment) Act, 2003 at block 793306 (''1The Constitution (Seventeenth Amendment) Act, 2003'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 251, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p251.png", "render_sha256": "bb7df14a2cf40071b103dbd2b011b4fa9654b3f0d5caac313acf5211d83d6d17"}]'::jsonb,
     'Block 793306 (p251) begins The Constitution (Seventeenth Amendment) Act, 2003 at its printed title. Supersedes, by citation, the unadjudicated archived candidate 169019e5-f5e7-447d-be90-5523eb2ac8f0 (nizam.multi_instrument_detector/1, block 793309).'),
    (13,793353::bigint,256,'The Constitution (Eighteenth Amendment) Act, 2010','act',2010,'X','7295f227-1bd8-4258-8d81-0918b66b8d43'::uuid,'boundary-anchor-review/1',793353,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 256 prints the title of The Constitution (Eighteenth Amendment) Act, 2010 at block 793353 (''1The Constitution (Eighteenth Amendment) Act, 2010'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 256, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p256.png", "render_sha256": "6b1a3e90f6310ca87183d593d80902720872704c25b4d853dc9487493d85e4d7"}]'::jsonb,
     'Block 793353 (p256) begins The Constitution (Eighteenth Amendment) Act, 2010 at its printed title. Supersedes, by citation, the unadjudicated archived candidate 7295f227-1bd8-4258-8d81-0918b66b8d43 (boundary-anchor-review/1, block 793353).'),
    (14,794161::bigint,304,'The Constitution (Nineteenth Amendment) Act, 2010','act',2010,NULL,'955da832-d671-43c5-aea2-f28d3c555249'::uuid,'nizam.multi_instrument_detector/1',794163,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 304 prints the title of The Constitution (Nineteenth Amendment) Act, 2010 at block 794161 (''1The Constitution (Nineteenth Amendment) Act, 2010'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 304, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p304.png", "render_sha256": "c68e1c4d885fa98ea49679468880cf2410430a99f34258f50de6330e68d50ad9"}]'::jsonb,
     'Block 794161 (p304) begins The Constitution (Nineteenth Amendment) Act, 2010 at its printed title. Supersedes, by citation, the unadjudicated archived candidate 955da832-d671-43c5-aea2-f28d3c555249 (nizam.multi_instrument_detector/1, block 794163).'),
    (15,794233::bigint,308,'The Constitution (Twentieth Amendment) Act, 2012','act',2012,'V','7c6352b6-eba9-4f39-8ab4-146a50fb896a'::uuid,'nizam.multi_instrument_detector/1',794236,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 308 prints the title of The Constitution (Twentieth Amendment) Act, 2012 at block 794233 (''1The Constitution (Twentieth Amendment) Act, 2012'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 308, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p308.png", "render_sha256": "5d8bf9e9c8e95e92d55569fcafef13b18f57c5fe358aa5c9bb1daf4e249ef03d"}]'::jsonb,
     'Block 794233 (p308) begins The Constitution (Twentieth Amendment) Act, 2012 at its printed title. Supersedes, by citation, the unadjudicated archived candidate 7c6352b6-eba9-4f39-8ab4-146a50fb896a (nizam.multi_instrument_detector/1, block 794236).'),
    (16,794311::bigint,312,'The Constitution (Twenty-First Amendment) Act, 2015','act',2015,'I','104da82f-9f09-49a4-8176-4014db27b2da'::uuid,'nizam.multi_instrument_detector/1',794314,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 312 prints the title of The Constitution (Twenty-First Amendment) Act, 2015 at block 794311 (''1The Constitution (Twenty-First Amendment) Act, 2015'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 312, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p312.png", "render_sha256": "043dfda412c2d322a7c09cf8fc233d76c38744600f44449ab11d106732c90606"}]'::jsonb,
     'Block 794311 (p312) begins The Constitution (Twenty-First Amendment) Act, 2015 at its printed title. Supersedes, by citation, the unadjudicated archived candidate 104da82f-9f09-49a4-8176-4014db27b2da (nizam.multi_instrument_detector/1, block 794314).'),
    (17,794335::bigint,314,'The Constitution (Twenty-second Amendment) Act, 2016','act',2016,'XXV','00a0e1a6-d2e3-4228-b27e-8420ea6f9750'::uuid,'nizam.multi_instrument_detector/1',794337,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 314 prints the title of The Constitution (Twenty-second Amendment) Act, 2016 at block 794335 (''1The Constitution (Twenty-second Amendment) Act, 2016'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 314, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p314.png", "render_sha256": "37a0aa91b035457ca828d42cbffff4d938ab2f8a571004821f7c49a529f44289"}]'::jsonb,
     'Block 794335 (p314) begins The Constitution (Twenty-second Amendment) Act, 2016 at its printed title. Supersedes, by citation, the unadjudicated archived candidate 00a0e1a6-d2e3-4228-b27e-8420ea6f9750 (nizam.multi_instrument_detector/1, block 794337).'),
    (18,794394::bigint,318,'The Constitution (Amendment) Order, 1979','order',1979,NULL,'0e1e483d-7cf1-4cbf-94a8-571ff738f5ea'::uuid,'nizam.multi_instrument_detector/1',794397,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 318 prints the title of The Constitution (Amendment) Order, 1979 at block 794394 (''1The Constitution (Amendment) Order, 1979'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 318, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p318.png", "render_sha256": "310c52f90846601c58421b261d1335e66479f1e6e59c9253c358b2f9aa35033b"}]'::jsonb,
     'Block 794394 (p318) begins The Constitution (Amendment) Order, 1979 at its printed title. Supersedes, by citation, the unadjudicated archived candidate 0e1e483d-7cf1-4cbf-94a8-571ff738f5ea (nizam.multi_instrument_detector/1, block 794397).'),
    (19,794440::bigint,322,'The Constitution (Second Amendment) Order, 1979','order',1979,NULL,'eab2a9fe-d89d-47ae-8fae-9c73736a4a40'::uuid,'nizam.multi_instrument_detector/1',794443,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 322 prints the title of The Constitution (Second Amendment) Order, 1979 at block 794440 (''1The Constitution (Second Amendment) Order, 1979'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 322, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p322.png", "render_sha256": "609003f8b86dd73a8ddcfd8779fa7d138042c0eb52f89759a6c08e9b0b7838a7"}]'::jsonb,
     'Block 794440 (p322) begins The Constitution (Second Amendment) Order, 1979 at its printed title. Supersedes, by citation, the unadjudicated archived candidate eab2a9fe-d89d-47ae-8fae-9c73736a4a40 (nizam.multi_instrument_detector/1, block 794443).'),
    (20,794453::bigint,323,'Constitution (Amendment) Order, 1980','order',1980,NULL,'8803e9b7-6032-4c25-99ba-eee2073b8543'::uuid,'nizam.multi_instrument_detector/1',794459,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',true,
     '["page 323 prints, after the Second Amendment Order 1979''s last words, the first line of the next title ''The Constitution'' (b794453, note marker 1) and footnote 1 ''Issued by the President on 26 May 1980 ...'' (b794454), which belongs to this Order", "page 324 continues the title ''(Amendment) Order, 1980'' (b794456), ''(President''s Order No. 1 of 1980)'', ''[26 May 1980]'', then the enacting formula (b794459)", "builder BZ''s title check named b794456-8; the printed title begins at b794453"]'::jsonb,
     '[{"page": 323, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p323.png", "render_sha256": "f19afcc762082aa116b5856ed1a1f061cd360dfa647e8e446ec5d7703cc33e11"}, {"page": 324, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p324.png", "render_sha256": "3d6bdc1d568dfec479595cba318ce19f1385d64d609ba288f9e626b14f11697a"}]'::jsonb,
     'Block 794453 (p323) begins Constitution (Amendment) Order, 1980 at its printed title -- corrected from the released span start (lead 15 Oct). Supersedes, by citation, the unadjudicated archived candidate 8803e9b7-6032-4c25-99ba-eee2073b8543 (nizam.multi_instrument_detector/1, block 794459).'),
    (21,794525::bigint,329,'The Constitution (Second Amendment) Order, 1980','order',1980,NULL,'c802d48f-f1d4-4684-a0ad-82440a8b3cce'::uuid,'nizam.multi_instrument_detector/1',794530,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 329 prints the title of The Constitution (Second Amendment) Order, 1980 at block 794525 (''1The Constitution (Second Amendment) Order, 1980'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 329, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p329.png", "render_sha256": "00a55f4f14ecd1ff9912484400d21802add3fb752aad5c981314ab6a3fda3bef"}]'::jsonb,
     'Block 794525 (p329) begins The Constitution (Second Amendment) Order, 1980 at its printed title. Supersedes, by citation, the unadjudicated archived candidate c802d48f-f1d4-4684-a0ad-82440a8b3cce (nizam.multi_instrument_detector/1, block 794530).'),
    (22,794552::bigint,331,'The Constitution (Third Amendment) Order, 1980','order',1980,NULL,'8f9d4dbd-fb9a-4a39-bb08-c4e140485811'::uuid,'nizam.multi_instrument_detector/1',794557,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 331 prints the title of The Constitution (Third Amendment) Order, 1980 at block 794552 (''1The Constitution (Third Amendment) Order, 1980'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 331, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p331.png", "render_sha256": "3cf36d234a87fa213d72d89b7c63989dcdcba2ca2848a91a3339c6208d7d2a06"}]'::jsonb,
     'Block 794552 (p331) begins The Constitution (Third Amendment) Order, 1980 at its printed title. Supersedes, by citation, the unadjudicated archived candidate 8f9d4dbd-fb9a-4a39-bb08-c4e140485811 (nizam.multi_instrument_detector/1, block 794557).'),
    (23,794561::bigint,332,'The Constitution (Fourth Amendment) Order, 1980','order',1980,NULL,'20ec6475-1707-4146-8496-22f5a9577ef4'::uuid,'nizam.multi_instrument_detector/1',794567,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 332 prints the title of The Constitution (Fourth Amendment) Order, 1980 at block 794561 (''1The Constitution (Fourth Amendment) Order, 1980'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 332, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p332.png", "render_sha256": "c2cb7bbad437f72c18ae577cdd2b7ae652d1faf5aabb31bcf97ca6a8434d4c5b"}]'::jsonb,
     'Block 794561 (p332) begins The Constitution (Fourth Amendment) Order, 1980 at its printed title. Supersedes, by citation, the unadjudicated archived candidate 20ec6475-1707-4146-8496-22f5a9577ef4 (nizam.multi_instrument_detector/1, block 794567).'),
    (24,794572::bigint,334,'The Constitution (Amendment) Order, 1981','order',1981,NULL,'fe0a99b3-68d0-44bb-b4f5-10bcaa07b2bd'::uuid,'nizam.multi_instrument_detector/1',794575,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 334 prints the title of The Constitution (Amendment) Order, 1981 at block 794572 (''1The Constitution (Amendment) Order, 1981'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 334, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p334.png", "render_sha256": "b64659085a08599dbfdfa572d73e95fb2b7b7875faee955d72ab31b48f7fcf7d"}]'::jsonb,
     'Block 794572 (p334) begins The Constitution (Amendment) Order, 1981 at its printed title. Supersedes, by citation, the unadjudicated archived candidate fe0a99b3-68d0-44bb-b4f5-10bcaa07b2bd (nizam.multi_instrument_detector/1, block 794575).'),
    (25,794585::bigint,335,'The Constitution (Second Amendment) Order, 1981','order',1981,NULL,'50e9d681-0923-4c30-9e10-09264d6964c1'::uuid,'nizam.multi_instrument_detector/1',794588,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 335 prints the title of The Constitution (Second Amendment) Order, 1981 at block 794585 (''1The Constitution (Second Amendment) Order, 1981'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 335, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p335.png", "render_sha256": "95e43dc0ca4233564b7d85bde20be90bdf12f91746d95c0caa4f84675ee8fcd5"}]'::jsonb,
     'Block 794585 (p335) begins The Constitution (Second Amendment) Order, 1981 at its printed title. Supersedes, by citation, the unadjudicated archived candidate 50e9d681-0923-4c30-9e10-09264d6964c1 (nizam.multi_instrument_detector/1, block 794588).'),
    (26,794596::bigint,336,'The Constitution (Third Amendment) Order, 1981','order',1981,NULL,'497a2a96-edca-4321-9070-ac3b0f5b6919'::uuid,'nizam.multi_instrument_detector/1',794599,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 336 prints the title of The Constitution (Third Amendment) Order, 1981 at block 794596 (''1The Constitution (Third Amendment) Order, 1981'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 336, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p336.png", "render_sha256": "6721f6261c9f512734bb2cab06c51b92ef3466783e3675e9f7da762ec4cb6d95"}]'::jsonb,
     'Block 794596 (p336) begins The Constitution (Third Amendment) Order, 1981 at its printed title. Supersedes, by citation, the unadjudicated archived candidate 497a2a96-edca-4321-9070-ac3b0f5b6919 (nizam.multi_instrument_detector/1, block 794599).'),
    (27,794604::bigint,337,'The Constitution (Fourth Amendment) Order, 1981','order',1981,NULL,'a96e34d1-5279-4aea-9490-24eaf48f96b3'::uuid,'nizam.multi_instrument_detector/1',794607,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 337 prints the title of The Constitution (Fourth Amendment) Order, 1981 at block 794604 (''1The Constitution (Fourth Amendment) Order, 1981'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 337, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p337.png", "render_sha256": "4be4fe5bb5ef6fa4348b9a27915054a72bf6176280f2c56c1ffeac70c77ea172"}]'::jsonb,
     'Block 794604 (p337) begins The Constitution (Fourth Amendment) Order, 1981 at its printed title. Supersedes, by citation, the unadjudicated archived candidate a96e34d1-5279-4aea-9490-24eaf48f96b3 (nizam.multi_instrument_detector/1, block 794607).'),
    (28,794616::bigint,338,'The Constitution (Fifth Amendment) Order, 1981','order',1981,NULL,'6c2972ca-a5fc-4b1b-b146-157167acb0e9'::uuid,'nizam.multi_instrument_detector/1',794619,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 338 prints the title of The Constitution (Fifth Amendment) Order, 1981 at block 794616 (''1The Constitution (Fifth Amendment) Order, 1981'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 338, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p338.png", "render_sha256": "2289cf7e84e5a75368a70daef3a8524128c7d0c8f800ee3a4a57e82a89d4d7a7"}]'::jsonb,
     'Block 794616 (p338) begins The Constitution (Fifth Amendment) Order, 1981 at its printed title. Supersedes, by citation, the unadjudicated archived candidate 6c2972ca-a5fc-4b1b-b146-157167acb0e9 (nizam.multi_instrument_detector/1, block 794619).'),
    (29,794625::bigint,339,'The Constitution (Amendment) Order, 1982','order',1982,NULL,'bee574c1-c54b-4150-9036-0e10f399011f'::uuid,'nizam.multi_instrument_detector/1',794628,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 339 prints the title of The Constitution (Amendment) Order, 1982 at block 794625 (''1The Constitution (Amendment) Order, 1982'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 339, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p339.png", "render_sha256": "4dbaca8b1120c374c79c7e029a84abec5001a42ebb02cab6fbb2292fe266e5ec"}]'::jsonb,
     'Block 794625 (p339) begins The Constitution (Amendment) Order, 1982 at its printed title. Supersedes, by citation, the unadjudicated archived candidate bee574c1-c54b-4150-9036-0e10f399011f (nizam.multi_instrument_detector/1, block 794628).'),
    (30,794635::bigint,340,'The Constitution (Second Amendment) Order, 1982','order',1982,NULL,'22bae2e5-7ba5-444c-81c8-403888f7b60a'::uuid,'nizam.multi_instrument_detector/1',794638,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 340 prints the title of The Constitution (Second Amendment) Order, 1982 at block 794635 (''1The Constitution (Second Amendment) Order, 1982'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 340, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p340.png", "render_sha256": "32bc8e9285935db6f528ac325316596fe7a49ac554352174b91890b6833a4aa9"}]'::jsonb,
     'Block 794635 (p340) begins The Constitution (Second Amendment) Order, 1982 at its printed title. Supersedes, by citation, the unadjudicated archived candidate 22bae2e5-7ba5-444c-81c8-403888f7b60a (nizam.multi_instrument_detector/1, block 794638).'),
    (31,794668::bigint,343,'The Constitution (Third Amendment) Order, 1982','order',1982,NULL,'0aa52174-3c13-46f4-bb77-d4b968be65ff'::uuid,'nizam.multi_instrument_detector/1',794671,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 343 prints the title of The Constitution (Third Amendment) Order, 1982 at block 794668 (''1The Constitution (Third Amendment) Order, 1982'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 343, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p343.png", "render_sha256": "31d32605e83fe27d2556a4d642bd8f92838f87903feb3a1f0524eb9a6085a55f"}]'::jsonb,
     'Block 794668 (p343) begins The Constitution (Third Amendment) Order, 1982 at its printed title. Supersedes, by citation, the unadjudicated archived candidate 0aa52174-3c13-46f4-bb77-d4b968be65ff (nizam.multi_instrument_detector/1, block 794671).'),
    (32,794680::bigint,344,'The Constitution (Fourth Amendment) Order, 1982','order',1982,NULL,'3874482a-70b9-4a2e-b4d1-74a1563a02a9'::uuid,'nizam.multi_instrument_detector/1',794683,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 344 prints the title of The Constitution (Fourth Amendment) Order, 1982 at block 794680 (''1The Constitution (Fourth Amendment) Order, 1982'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 344, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p344.png", "render_sha256": "165c829fb79b4990085d5e036deed81035bbc0c1bf6ff4659053557c00ebc846"}]'::jsonb,
     'Block 794680 (p344) begins The Constitution (Fourth Amendment) Order, 1982 at its printed title. Supersedes, by citation, the unadjudicated archived candidate 3874482a-70b9-4a2e-b4d1-74a1563a02a9 (nizam.multi_instrument_detector/1, block 794683).'),
    (33,794689::bigint,345,'The Constitution (Amendment) Order, 1983','order',1983,NULL,'e74b42b4-fcb0-465e-b7db-7a2a1e3c1449'::uuid,'nizam.multi_instrument_detector/1',794692,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 345 prints the title of The Constitution (Amendment) Order, 1983 at block 794689 (''1The Constitution (Amendment) Order, 1983'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 345, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p345.png", "render_sha256": "11d2b935a872955a5ac19ed85ecb565710349203b626510f175de50264667184"}]'::jsonb,
     'Block 794689 (p345) begins The Constitution (Amendment) Order, 1983 at its printed title. Supersedes, by citation, the unadjudicated archived candidate e74b42b4-fcb0-465e-b7db-7a2a1e3c1449 (nizam.multi_instrument_detector/1, block 794692).'),
    (34,794702::bigint,346,'The Constitution (Second Amendment) Order, 1983','order',1983,NULL,'141d690b-8173-4fdc-b071-9d95a2b24bfb'::uuid,'nizam.multi_instrument_detector/1',794705,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 346 prints the title of The Constitution (Second Amendment) Order, 1983 at block 794702 (''1The Constitution (Second Amendment) Order, 1983'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 346, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p346.png", "render_sha256": "3159cb4a2b3193c15b96ae1ebcbe6531c061e8a89496df6dbf9c205fabe73090"}]'::jsonb,
     'Block 794702 (p346) begins The Constitution (Second Amendment) Order, 1983 at its printed title. Supersedes, by citation, the unadjudicated archived candidate 141d690b-8173-4fdc-b071-9d95a2b24bfb (nizam.multi_instrument_detector/1, block 794705).'),
    (35,794711::bigint,347,'The Constitution (Third Amendment) Order, 1983','order',1983,NULL,'f16152af-9a88-40e0-aeea-ce57a1ff348c'::uuid,'nizam.multi_instrument_detector/1',794714,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 347 prints the title of The Constitution (Third Amendment) Order, 1983 at block 794711 (''1The Constitution (Third Amendment) Order, 1983'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 347, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p347.png", "render_sha256": "cc01e20a938b480607a50e00342686c02026cdfe9f29a98f6fcaf42127d22ea3"}]'::jsonb,
     'Block 794711 (p347) begins The Constitution (Third Amendment) Order, 1983 at its printed title. Supersedes, by citation, the unadjudicated archived candidate f16152af-9a88-40e0-aeea-ce57a1ff348c (nizam.multi_instrument_detector/1, block 794714).'),
    (36,794721::bigint,348,'The Constitution (Amendment) Order, 1984','order',1984,NULL,'c74b40be-c4ab-4051-964e-498f5de10d1e'::uuid,'nizam.multi_instrument_detector/1',794724,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 348 prints the title of The Constitution (Amendment) Order, 1984 at block 794721 (''1The Constitution (Amendment) Order, 1984'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 348, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p348.png", "render_sha256": "12a221fdec2dd4e26f5b4cd6e085a8a72d64e5a5ff788709ddeb993cfaa27bde"}]'::jsonb,
     'Block 794721 (p348) begins The Constitution (Amendment) Order, 1984 at its printed title. Supersedes, by citation, the unadjudicated archived candidate c74b40be-c4ab-4051-964e-498f5de10d1e (nizam.multi_instrument_detector/1, block 794724).'),
    (37,794735::bigint,349,'The Constitution (Second Amendment) Order, 1984','order',1984,NULL,'0e7edae5-6397-40f8-b02a-26cf31684d21'::uuid,'nizam.multi_instrument_detector/1',794738,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 349 prints the title of The Constitution (Second Amendment) Order, 1984 at block 794735 (''2The Constitution (Second Amendment) Order, 1984'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 349, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p349.png", "render_sha256": "a29eeffe2afcdaedf63ca3e8934857ffcc8a06ceec7dbe2d30912c932cf61c7a"}]'::jsonb,
     'Block 794735 (p349) begins The Constitution (Second Amendment) Order, 1984 at its printed title. Supersedes, by citation, the unadjudicated archived candidate 0e7edae5-6397-40f8-b02a-26cf31684d21 (nizam.multi_instrument_detector/1, block 794738).'),
    (38,794744::bigint,350,'The Constitution (Amendment) Order, 1985','order',1985,NULL,'d1121c8a-f264-466a-a775-543ffe648266'::uuid,'nizam.multi_instrument_detector/1',794747,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 350 prints the title of The Constitution (Amendment) Order, 1985 at block 794744 (''1The Constitution (Amendment) Order, 1985'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 350, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p350.png", "render_sha256": "3c05390f770ee901324022b4b29ad5ba846f21b9108cb7bce2008376edfdf8f5"}]'::jsonb,
     'Block 794744 (p350) begins The Constitution (Amendment) Order, 1985 at its printed title. Supersedes, by citation, the unadjudicated archived candidate d1121c8a-f264-466a-a775-543ffe648266 (nizam.multi_instrument_detector/1, block 794747).'),
    (39,794787::bigint,353,'Revival of the Constitution of 1973 Order, 1985','order',1985,NULL,'ce56ec59-791f-49eb-a866-0d5ca3a421a1'::uuid,'nizam.multi_instrument_detector/1',794784,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',true,
     '["page 353 prints the title ''The Revival of the Constitution of 1973 Order, 1985'' (b794787, note marker 1), ''(President''s Order No. 14 of 1985)'', ''[17 March 1985]''", "page 352 before it prints the Constitution (Amendment) Order, 1985 (President''s Order No. 11 of 1985), whose s.2 quotes the new Article 165A (b794784) -- quoted text of that Order, not of this one", "the archived detector candidate sat at the quoted Article 165A, b794784"]'::jsonb,
     '[{"page": 353, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p353.png", "render_sha256": "13ff5b071380e5a88442b79f42f99784b0377a1dd8b880acd4880eebae6f659f"}]'::jsonb,
     'Block 794787 (p353) begins Revival of the Constitution of 1973 Order, 1985 at its printed title -- corrected from the released span start (lead 15 Oct). Supersedes, by citation, the unadjudicated archived candidate ce56ec59-791f-49eb-a866-0d5ca3a421a1 (nizam.multi_instrument_detector/1, block 794784).'),
    (40,794868::bigint,360,'THE CONSTITUTION (SECOND AMENDMENT) ORDER, 1985','order',1985,NULL,'5339887e-80c7-460a-bb3c-a8dd0f5d6644'::uuid,'nizam.multi_instrument_detector/1',794868,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 360 prints the title of THE CONSTITUTION (SECOND AMENDMENT) ORDER, 1985 at block 794868 (''1THE CONSTITUTION (SECOND AMENDMENT) ORDER, 1985'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 360, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p360.png", "render_sha256": "b40734ab913991ff69901aa7aed16f0298d7cdd504800b7cc559b8d319e4e982"}]'::jsonb,
     'Block 794868 (p360) begins THE CONSTITUTION (SECOND AMENDMENT) ORDER, 1985 at its printed title. Supersedes, by citation, the unadjudicated archived candidate 5339887e-80c7-460a-bb3c-a8dd0f5d6644 (nizam.multi_instrument_detector/1, block 794868).'),
    (41,794885::bigint,362,'The Constitution (Third Amendment) Order, 1985','order',1985,NULL,'b479db5c-5f23-4b77-8579-4eff9ae62276'::uuid,'nizam.multi_instrument_detector/1',794888,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 362 prints the title of The Constitution (Third Amendment) Order, 1985 at block 794885 (''1The Constitution (Third Amendment) Order, 1985'')", "the span start opens on the printed title (page image read, claude/agK5/montage-*.png); unchanged from the active manifest"]'::jsonb,
     '[{"page": 362, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p362.png", "render_sha256": "e9a896586019833d6e6948e7c4bd460978f7649c90069d7a0cab7eec77677aa3"}]'::jsonb,
     'Block 794885 (p362) begins The Constitution (Third Amendment) Order, 1985 at its printed title. Supersedes, by citation, the unadjudicated archived candidate b479db5c-5f23-4b77-8579-4eff9ae62276 (nizam.multi_instrument_detector/1, block 794888).'),
    (42,794910::bigint,364,'The Constitution (Amendment) Order, 2007','order',2007,NULL,'f17fc441-4bf9-4533-a148-9fcd5488e1d2'::uuid,'nizam.multi_instrument_detector/1',794918,'45fea3b9-16a6-42ac-b3bc-fcb521a0c294:9f32dee1-8472-4056-8428-11503f2a82ae',false,
     '["page 364 opens with its running header (b794910) and then prints the title ''The Constitution (Amendment) Order, 2007'' (b794911)", "the span start is the page''s first block, as the active manifest has it; unchanged"]'::jsonb,
     '[{"page": 364, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p364.png", "render_sha256": "ecfe62bf203e8e4beafcfb2d429fe40470ae1dd8a8319e3a85b29cb545faaa92"}]'::jsonb,
     'Block 794910 (p364) begins The Constitution (Amendment) Order, 2007 at its printed title. Supersedes, by citation, the unadjudicated archived candidate f17fc441-4bf9-4533-a148-9fcd5488e1d2 (nizam.multi_instrument_detector/1, block 794918).'),
    (45,794777::bigint,352,'The Constitution (Amendment) Order, 1985','order',1985,NULL,NULL,NULL,NULL,NULL,false,
     '["page 352 prints the title ''1The Constitution (Amendment) Order, 1985'' (b794777), ''(President''s Order No. 11 of 1985)'' (b794778), ''[24 February 1985]'' (b794779), its enacting formula and ss.1-2 (s.2 adding Article 165A), and its own footnote 1 ''Published in the Gazette of Pakistan (Extraordinary), Part-I, dated: 24 February 1985, pp.83-84'' (b794785)", "page 350 prints the other Order of the same short title, President''s Order No. 6 of 1985, [17 January 1985] (b794744-6), which ends on page 351; the p352 running header (b794776) stays with it", "no candidate was ever recorded at this block: the legacy detector folded both Orders into expression 38"]'::jsonb,
     '[{"page": 352, "render": ".artifacts/release-work-2026-09-24/claude/renders/doc4434-p352.png", "render_sha256": "f0feaf2fd5bbdc5280af57c3e389c444765a1764842409b1d6bcfe58def44660"}]'::jsonb,
     'Block 794777 (p352) begins The Constitution (Amendment) Order, 1985 at its printed title. A second Order printed inside legacy expression 38; split on the lead''s decision of 15 Oct (no earlier candidate).');

DO $$
BEGIN
  IF (SELECT count(*) FROM k5_proposed) <> 43 THEN RAISE EXCEPTION 'expected 43 proposed anchors'; END IF;
  IF NOT EXISTS (SELECT 1 FROM instrument i WHERE i.id='b59f4939-bef4-471a-ae10-790f1f7e0359' AND i.document_id=4434
                    AND i.expression_ordinal=0 AND i.is_active AND i.duplicate_of IS NULL AND i.source_observation_id=2810)
     OR EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id='b59f4939-bef4-471a-ae10-790f1f7e0359') THEN
    RAISE EXCEPTION 'instrument b59f4939 is not the active unreleased canonical expression 0 of 4434';
  END IF;
  IF EXISTS (SELECT 1 FROM k5_proposed p LEFT JOIN text_block t ON t.id=p.start_block_id
              WHERE t.document_id IS DISTINCT FROM 4434 OR t.page_no<>p.source_page) THEN
    RAISE EXCEPTION 'a proposed start block is not on its stated page of document 4434';
  END IF;
END $$;

INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT i.id,i.source_observation_id,4434,p.start_block_id,p.source_page,
       p.detected_title,p.detected_kind,p.detected_year,p.detected_number,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-4434.json',
         'expression_ordinal',p.ordinal,
         'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json',
         'question_id','q2',
         'boundary_correction',CASE WHEN p.corrected THEN 'lead decision 15 Oct 2026 under the owner''s chat delegation (CLAUDE-CLAIMS): the released start moves to the printed title' END,
         'archived_candidate_id',p.archived_candidate_id,
         'archived_candidate_note',p.archived_method||' at block '||p.archived_block||', archive manifest '||p.archive_manifest||'; never adjudicated',
         'source_facts',p.source_facts,
         'reviewed_pages',(SELECT jsonb_agg(x->'page') FROM jsonb_array_elements(p.renders) x),
         'renders',p.renders,
         'title_crops','.artifacts/release-work-2026-09-24/claude/agK5/montage-1..8.png')
  FROM k5_proposed p
  JOIN instrument i ON i.id='b59f4939-bef4-471a-ae10-790f1f7e0359'
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id,resolution,review_basis,method,rationale,evidence,decided_by
)
SELECT c.id,'confirmed_split','source_verified','claude.multi-expression-plan/1',p.rationale,
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'expression_ordinal',p.ordinal,
                          'archived_candidate_id',p.archived_candidate_id,
                          'plan','tools/evidence/multi-instrument-plans/doc-4434.json',
                          'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
  JOIN k5_proposed p ON p.start_block_id=c.start_block_id
 WHERE c.document_id=4434
   AND c.instrument_id='b59f4939-bef4-471a-ae10-790f1f7e0359'
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (SELECT 1 FROM segmentation_boundary_adjudication a
                    WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

DO $$
DECLARE n_c int; n_a int;
BEGIN
  SELECT count(*), count(*) FILTER (WHERE EXISTS (SELECT 1 FROM v_boundary_adjudication_latest a
                                                   WHERE a.candidate_id=c.id AND a.resolution='confirmed_split'))
    INTO n_c, n_a
    FROM segmentation_boundary_candidate c JOIN k5_proposed p ON p.start_block_id=c.start_block_id
   WHERE c.document_id=4434 AND c.instrument_id='b59f4939-bef4-471a-ae10-790f1f7e0359'
     AND c.method='claude.multi-expression-plan/1';
  IF n_c <> 43 OR n_a <> 43 THEN
    RAISE EXCEPTION 'expected 43 candidates / 43 confirmed_split, got % / %', n_c, n_a;
  END IF;
END $$;

COMMIT;
