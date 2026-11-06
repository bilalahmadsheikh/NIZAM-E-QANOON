"""c_cls.py TEXT... : what classify() returns for each text (read-only)"""
import sys
sys.path.insert(0, "/mnt/e/Nizam_e_Qanoon")
from nizam.corpus.segment import classify
for t in sys.argv[1:]:
    t = t.replace("\n", "\n")
    print(repr(t), "->", classify(t))
