"""Stable class colors shared by RGB, world masks, BEV, and legends."""
import colorsys
import hashlib

BASE={'car':(56,189,248),'person':(250,204,21),'truck':(251,146,60),
      'bus':(244,114,182),'motorcycle':(192,132,252),'bicycle':(45,212,191),
      'potted plant':(74,222,128),'road':(34,197,94)}


def class_color(name):
    name=str(name).strip().casefold()
    if name in BASE:return BASE[name]
    hue=int.from_bytes(hashlib.sha256(name.encode()).digest()[:4],'big')/2**32
    return tuple(round(v*255) for v in colorsys.hsv_to_rgb(hue,.68,.98))


def query_legend(query):
    from collections import Counter
    counts=Counter(d.get('class_name') or d.get('query') or query.get('query','object') for d in query.get('detections',[])) if query else {}
    return [{'name':name,'color':list(class_color(name)),'count':count} for name,count in sorted(counts.items())]
