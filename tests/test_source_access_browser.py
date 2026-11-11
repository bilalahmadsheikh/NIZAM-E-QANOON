"""The durable uncertainty notice must precede the browser scan and raw OCR."""
import importlib.util
from pathlib import Path
from unittest.mock import patch
from tests.test_source_access_notice import notice

spec = importlib.util.spec_from_file_location('source_access_browser', Path('tools/corpus-browser/serve.py'))
browser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(browser)


def test_document_notice_precedes_pdf_and_raw_ocr():
    meta = [('Order1957',69,180488,'E3',1,'a'*64,'pk-sindh','https://sindhlaws.gov.pk/source.pdf','en')]
    with patch.object(browser, 'q', side_effect=[meta,[(notice(),)],[(1,0,'UNCERTIFIED_RAW_OCR',None,None)]]):
        rendered = browser.document(9361).decode()
    assert rendered.index('Legal-text release remains held') < rendered.index('<iframe')
    assert rendered.index('Legal-text release remains held') < rendered.index('UNCERTIFIED_RAW_OCR')


def test_plain_text_download_carries_notice_before_any_raw_text():
    with patch.object(browser, 'q', side_effect=[[(1,'UNCERTIFIED_RAW_OCR')],[('Order1957',69)],[(notice(),)]]):
        rendered = browser.plain(9361).decode()
    assert rendered.index('Legal-text release remains held') < rendered.index('UNCERTIFIED_RAW_OCR')
