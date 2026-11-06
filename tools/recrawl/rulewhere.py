"""rulewhere.py RULE [RULE ...] : which segmentation profiles carry each rule (read-only)"""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.corpus import segment as S
for r in sys.argv[1:]:
    print(r, [k for k, v in S.SEGMENTATION_PROFILES.items() if r in v])
