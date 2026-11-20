# Notes for the legal review: cases where the gold may be narrower than the law

These came from the gate's error analysis (D-102, D-103, 20 Nov 2026). The system's leading results were read in
full. The draft gold is **not** changed: case authoring (A0) never takes the system's output as an answer. Annotators
should decide in stage A1 whether each provision below belongs in the case, using the provision's own text. If it
does, record it in `your_missing_law_and_section`.

| Case | Split | Question | Gold | Also led by the system | Why it may belong |
|---|---|---|---|---|---|
| S3-P03 | dev | Forum for a workplace harassment complaint in Punjab | Protection against Harassment of Women at the Workplace Act, 2010 s.8 | Punjab Labour Code, 2026 s.51 (Grievance Redressal Committee) and s.393 | s.393 says harassment cases "shall be dealt with under" the 2010 Act and the PPC. s.51 requires every establishment of more than ten employees to set up a committee that hears harassment complaints. Both are Punjab law in force on the case's date |
| S2-C06 | test | The police station in Multan refuses to register my complaint. Who can I go to? | CrPC s.22A (Justice of the Peace) | Police Act, 1861 s.55(1)(a) (District Public Safety Commission) | s.55(1)(a) lets the Commission direct the District Police Officer to inquire into an unjustified refusal to register an FIR. The question is whether that text is in force in Punjab on the case's date |

One more finding was a corpus defect, not a gold question. S4-C05 (test) served the West Pakistan Maternity
Benefit Ordinance, 1958 in KP, where the KP Maternity Benefits Act, 2013 s.18 repeals it. Fixed by D-103.
