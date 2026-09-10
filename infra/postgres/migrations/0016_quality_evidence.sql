-- Append-only quality evidence. Metrics, human/source assertions and OCR
-- candidates are observations; none replaces or deletes an extraction.
CREATE TABLE extraction_verification (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id         bigint NOT NULL REFERENCES document(id) ON DELETE RESTRICT,
    verifier            text NOT NULL,
    reference_extractor text NOT NULL,
    outcome             text NOT NULL CHECK (outcome IN ('passed','review','unverifiable')),
    char_recall         numeric(8,7),
    char_precision      numeric(8,7),
    raw_char_precision  numeric(8,7),
    token_recall        numeric(8,7),
    problems            jsonb NOT NULL DEFAULT '[]',
    hints               jsonb NOT NULL DEFAULT '[]',
    detail              jsonb NOT NULL DEFAULT '{}',
    verified_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX extraction_verification_document
    ON extraction_verification(document_id, verified_at DESC);

CREATE TABLE extraction_assertion (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sha256      char(64) NOT NULL REFERENCES blob(sha256) ON DELETE RESTRICT,
    page_no     integer CHECK (page_no IS NULL OR page_no >= 1),
    kind        text NOT NULL CHECK (kind IN
                ('source_content_confirmed','decode_damage','visibility_review')),
    evidence    text NOT NULL,
    detail      jsonb NOT NULL DEFAULT '{}',
    asserted_by text NOT NULL,
    asserted_at timestamptz NOT NULL DEFAULT now(),
    is_active   boolean NOT NULL DEFAULT true
);
CREATE INDEX extraction_assertion_sha ON extraction_assertion(sha256, is_active);

CREATE TABLE page_ocr_candidate (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id     bigint NOT NULL REFERENCES document(id) ON DELETE RESTRICT,
    page_no         integer NOT NULL,
    engine          text NOT NULL,
    languages       text NOT NULL,
    dpi             integer NOT NULL,
    text            text NOT NULL,
    mean_confidence numeric(5,4),
    word_count      integer NOT NULL,
    blocks          jsonb NOT NULL DEFAULT '[]',
    created_at      timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (document_id,page_no) REFERENCES page(document_id,page_no)
        ON DELETE RESTRICT
);
CREATE INDEX page_ocr_candidate_page
    ON page_ocr_candidate(document_id,page_no,created_at DESC);
