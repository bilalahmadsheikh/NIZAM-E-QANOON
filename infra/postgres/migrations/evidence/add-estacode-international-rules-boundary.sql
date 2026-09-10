-- Source-verified exceptional boundary: the official compilation prints the
-- complete 2016 Rules but omits their original gazette formula.  The numbered
-- editorial title, Rule 1 self-name and Rule 2 reset are all present in three
-- consecutive immutable blocks.  This is stronger than inferring from title
-- similarity and does not alter any source text.

INSERT INTO segmentation_boundary_candidate
    (instrument_id,source_observation_id,document_id,start_block_id,source_page,
     detected_title,detected_kind,detected_year,detected_number,confidence,
     method,evidence)
SELECT i.id,i.source_observation_id,i.document_id,title.id,title.page_no,
       'Civil Servants (Service in International Organizations) Rules, 2016',
       'rules',2016,NULL,1.0,'nizam.source_verified_estacode_boundary/1',
       jsonb_build_object(
         'rules',jsonb_build_array('numbered_compilation_title',
                    'rule_one_self_names_instrument','rule_two_sequence',
                    'source_formula_omitted_by_official_compilation'),
         'supporting_blocks',jsonb_build_array(
           jsonb_build_object('block_id',title.id,'page',title.page_no,
                              'sha256',encode(digest(title.text,'sha256'),'hex'),
                              'preview',left(regexp_replace(title.text,E'[\n\r]+',' ','g'),240)),
           jsonb_build_object('block_id',rule1.id,'page',rule1.page_no,
                              'sha256',encode(digest(rule1.text,'sha256'),'hex'),
                              'preview',left(regexp_replace(rule1.text,E'[\n\r]+',' ','g'),240)),
           jsonb_build_object('block_id',rule2.id,'page',rule2.page_no,
                              'sha256',encode(digest(rule2.text,'sha256'),'hex'),
                              'preview',left(regexp_replace(rule2.text,E'[\n\r]+',' ','g'),240))))
  FROM instrument i
  JOIN text_block title ON title.id=894191 AND title.document_id=i.document_id
  JOIN text_block rule1 ON rule1.id=894192 AND rule1.document_id=i.document_id
  JOIN text_block rule2 ON rule2.id=894195 AND rule2.document_id=i.document_id
 WHERE i.source_observation_id=1038 AND i.is_active AND i.duplicate_of IS NULL
   AND title.text ILIKE '%22.3 Civil Servants%International%Rules,2016%'
   AND rule1.text ILIKE '%These rules may be%called%International Organizations%Rules,2016%'
   AND rule2.text ~ '^[[:space:]]*2[.]'
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;
