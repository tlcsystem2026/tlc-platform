from difflib import SequenceMatcher
from parser.normalizer import clean_text

class LineMatcher:
    def match(self,pdf_lines,excel_lines):
        remaining=set(range(len(excel_lines))); pairs=[]
        for p in pdf_lines:
            idx=self._best(p,excel_lines,remaining)
            if idx is None: pairs.append((p,None))
            else:
                pairs.append((p,excel_lines[idx])); remaining.remove(idx)
        pairs.extend((None,excel_lines[i]) for i in sorted(remaining))
        return pairs

    def _best(self,p,lines,candidates):
        code=clean_text(getattr(p,"product_code",""))
        if code:
            for i in candidates:
                if clean_text(getattr(lines[i],"product_code",""))==code:return i
        name=clean_text(getattr(p,"product_name",""))
        exact=[i for i in candidates if name and clean_text(getattr(lines[i],"product_name",""))==name]
        if exact:return exact[0]
        best=None
        for i in candidates:
            other=clean_text(getattr(lines[i],"product_name",""))
            score=SequenceMatcher(None,name,other).ratio() if name and other else 0
            amount_bonus=0.15 if str(getattr(p,"amount",""))==str(getattr(lines[i],"amount","")) else 0
            score+=amount_bonus
            if best is None or score>best[1]:best=(i,score)
        return best[0] if best and best[1]>=0.72 else None
