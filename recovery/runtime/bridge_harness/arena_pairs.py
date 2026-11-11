"""Unambiguous match IDs, retaining legacy two-character IDs."""
def pair_id(a,b):
    if '~' in a or '~' in b:raise ValueError('Invalid generation ID')
    return a+b if len(a)==len(b)==1 else a+'~'+b

def pair_members(pair):
    if isinstance(pair,(list,tuple)) and len(pair)==2:return tuple(pair)
    if isinstance(pair,str):
        if '~' in pair:
            parts=pair.split('~')
            if len(parts)==2 and all(parts):return tuple(parts)
        elif len(pair)==2:return tuple(pair)
    raise ValueError('A pair requires two distinct explicit generation fields')
