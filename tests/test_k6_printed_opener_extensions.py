"""4331 source-reviewed Schedule I divisions, omission stubs and explanations.

Owner export m q1 as-drafted / q2 v5-and-fix; K6's data-gated route uses
existing source_printed_rule_openers. No entry means no new behavior.
"""
import pytest

from nizam.corpus.segment import assign_paths, segment


def b(i, text, y):
    return dict(id=i,text=text,page_no=1,y0=y,page_height=792,x0=70,x1=560)


DOC = [
    b(1,"1. Short title.– This Act may be called the Test Stamp Act, 1899.",60),
    b(2,"SCHEDULE I",100),
    b(3,"46. \nPARTNERSHIP– \nA-INSTRUMENT OF– \n(a) where the capital of the partnership does not exceed Rs. 500; Two hundred rupees.\n(b) in any other case One thousand rupees.\nB-DISSOLUTION OF– \nHalf of the Stamp duty payable on original.",130),
    b(4,"47. \nRE-CONVEYANCE OF MORTGAGE PROPERTY– \n(a) 1[* * * * *] \n(b) 3[* * * * *] \nOne thousand rupees.",260),
    b(5,"48. \nAUTHENTICATED DECLARATIONS of newspapers. \nTwenty rupees. \nEXPLANATION I.– The duty shall be paid by the declarant. \nEXPLANATION II.– The declaration shall not be authenticated unless stamped.",330),
    b(6,"49. \nPARTITION-Instrument of. Two percent. \n1[Exception.– Notwithstanding anything contained herein, a fixed stamp duty of five hundred rupees shall be charged.]",420),
]
SPEC={"source_printed_rule_openers":[
    dict(source_block_id=3,label="A",source_prefix="A-INSTRUMENT OF",kind="subsection"),
    dict(source_block_id=3,label="B",source_prefix="B-DISSOLUTION OF",kind="subsection"),
    dict(source_block_id=4,label="b",source_prefix="(b) 3[* * * * *]",kind="clause"),
    dict(source_block_id=5,label="Explanation",source_prefix="EXPLANATION I.",kind="explanation"),
    dict(source_block_id=5,label="Explanation",source_prefix="EXPLANATION II.",kind="explanation"),
    dict(source_block_id=6,label="Exception",source_prefix="1[Exception.",kind="explanation"),
]}


def paths(seg):
    return {p:n for n,p in assign_paths(seg,"test")}


@pytest.mark.parametrize("profile",["default","unreleased-v4"])
def test_reviewed_divisions_preserve_items_and_source_under_the_article(profile):
    got=paths(segment(DOC,profile=profile,structural_overrides=SPEC))
    divisions=sorted((p,n) for p,n in got.items() if n.kind=="subsection" and n.label in ("A","B"))
    assert [n.label for p,n in divisions]==["A","B"]
    a=divisions[0][0]
    assert a.endswith("cl_46.ss_A")
    assert any(p.startswith(a+".cl_a") for p in got)
    assert any(p.startswith(a+".cl_b") for p in got)
    assert all(n.first_block==3 for p,n in divisions)
    assert "INSTRUMENT OF" in got[a].text and not got[a].text.startswith("A-")
    stubs=[n for n in got.values() if n.kind=="clause" and n.label=="b" and "3[*" in (n.text or "")]
    assert len(stubs)==1 and stubs[0].first_block==4
    explanations=[n for p,n in sorted(got.items()) if n.kind=="explanation" and n.label=="Explanation"]
    assert [n.text[:4] for n in explanations]==["I.– ","II.–"]
    exception=[n for n in got.values() if n.kind=="explanation" and n.label=="Exception"]
    assert len(exception)==1 and exception[0].text.startswith("Notwithstanding")


@pytest.mark.parametrize("bad",[
    dict(source_block_id=3,label="a",source_prefix="A-INSTRUMENT OF",kind="subsection"),
    dict(source_block_id=5,label="Note",source_prefix="EXPLANATION I.",kind="explanation"),
    dict(source_block_id=5,label="Explanation",source_prefix="The duty shall be",kind="explanation"),
    dict(source_block_id=4,label="b",source_prefix="(b) 3[ dummy text",kind="clause"),
])
def test_malformed_entries_refused(bad):
    with pytest.raises(ValueError,match="malformed"):
        segment(DOC,structural_overrides={"source_printed_rule_openers":[bad]})


def test_missing_source_prefix_refused():
    entry=dict(source_block_id=6,label="C",source_prefix="C-INSURANCE BY",kind="subsection")
    with pytest.raises(ValueError):
        segment(DOC,structural_overrides={"source_printed_rule_openers":[entry]})


def test_new_behavior_inert_without_reviewed_entries():
    a=paths(segment(DOC,profile="unreleased-v4"))
    c=paths(segment(DOC,profile="unreleased-v4",structural_overrides={}))
    assert [(p,n.kind,n.label,n.text) for p,n in a.items()]==[(p,n.kind,n.label,n.text) for p,n in c.items()]
    assert not any(n.kind=="subsection" and n.label in ("A","B") for n in a.values())


@pytest.mark.parametrize("prefix",["A---INSTRUMENT OF","A. INSTRUMENT OF","A  INSTRUMENT OF"])
def test_reviewed_division_separator_variants(prefix):
    doc=[b(1,"SCHEDULE I",80),b(2,"46. PARTNERSHIP\n"+prefix+"\n(a) The instrument shall be stamped.",120)]
    got=paths(segment(doc,structural_overrides={"source_printed_rule_openers":[
        dict(source_block_id=2,label="A",source_prefix=prefix,kind="subsection")]}))
    assert any(p.endswith("cl_46.ss_A.cl_a") for p in got)


@pytest.mark.parametrize("label",["I","V","X"])
def test_existing_parenthesized_roman_subsections_keep_their_grammar(label):
    doc=[b(1,"1. Application.- The following provisions apply.",60),
         b(2,f"({label}) The duty shall be payable by the applicant.",100)]
    got=paths(segment(doc,structural_overrides={"source_printed_rule_openers":[
        dict(source_block_id=2,label=label,source_prefix=f"({label}) The duty shall",kind="subsection")]}))
    node=next(n for n in got.values() if n.kind=="subsection" and n.label==label)
    assert node.parent.label=="1" and node.text.startswith("The duty shall")
