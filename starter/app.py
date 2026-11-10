"""Week 11 teaching starter. Run locally with: python -m uvicorn app:app --port 8000"""
from pathlib import Path
import json,re
import spacy,textstat,nltk
from fastapi import FastAPI,HTTPException,Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
BASE=Path(__file__).parent
nltk.data.path.insert(0, str(BASE.parent / '.venv' / 'nltk_data'))
nltk.data.path.insert(0, str(BASE.parent / 'nltk_data'))
app=FastAPI(title='Week 11 language analysis teaching prototype')
from .hints import router as hints_router
app.include_router(hints_router)
from .security import RequestSizeLimit, allowed_origins, protect_analysis
app.add_middleware(RequestSizeLimit)
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins(),
    allow_methods=['GET', 'POST'], allow_headers=['Content-Type', 'X-Classroom-Code'],
    allow_credentials=False, expose_headers=['Retry-After'], max_age=600)
nlp=spacy.load('en_core_web_sm')
textstat.set_lang('en_US')
class Input(BaseModel):
    text:str=Field(max_length=20000)

def analyse(text):
    doc=nlp(text)
    # A word contains a letter, may have internal apostrophes, and has no digits.
    # spaCy determines contraction boundaries. All display counts use this same set.
    tokens=[t for t in doc if re.fullmatch(r"[A-Za-z]+(?:['’][A-Za-z]+)*",t.text)]
    W=len(tokens)
    if not W: raise ValueError('Enter an English sample containing words.')
    spans=[s for s in doc.sents if any(t in tokens for t in s)]
    S=len(spans); forms=[t.text.lower() for t in tokens]; V=len(set(forms))
    win=50
    mattr=sum(len(set(forms[i:i+win]))/win for i in range(W-win+1))/(W-win+1) if W>=win else None
    content=[t for t in tokens if t.pos_ in {'NOUN','PROPN','VERB','ADJ','ADV'}]
    syll=sum(textstat.syllable_count(t.text) for t in tokens)
    fre=206.835-1.015*W/S-84.6*syll/W
    fk=.39*W/S+11.8*syll/W-15.59
    # Transparent finite-clause proxy. It is NOT an implementation of L2SCA.
    heads=[]
    for t in doc:
        if t.pos_ not in {'VERB','AUX','ADJ','NOUN'}: continue
        if t.dep_ not in {'ROOT','conj','advcl','ccomp','xcomp','relcl','acl','csubj'}:continue
        if 'Fin' in t.morph.get('VerbForm') or any('Fin' in c.morph.get('VerbForm') for c in t.children if c.dep_ in {'aux','auxpass','cop'}): heads.append(t)
    dep=[t for t in heads if t.dep_ in {'advcl','ccomp','xcomp','relcl','acl','csubj'}]
    flags=[]
    patterns=[(r'\bsince\s+\d+\s+(?:days?|weeks?|months?|years?)\b','duration','Check whether this is a duration requiring for. Also check the verb phrase.'),
    (r'\bsince\s+(?:two|three|four|five|six)\s+(?:days?|weeks?|months?|years?)\b','duration','This appears to express duration. Consider for and check the intended meaning.'),
    (r'\bfeedback\s+are\b','agreement','Feedback is normally uncountable in this context. Check subject–verb agreement.'),
    (r'\bcan\s+offers\b','modal_base','After can, check whether the base form offer is required.'),
    (r'\byesterday\s+I\s+have\s+\w+\b','past_time','A completed event with yesterday usually requires past simple.')]
    for pattern,skill,msg in patterns:
        for m in re.finditer(pattern,text,re.I):flags.append({'span':m.group(),'start':m.start(),'end':m.end(),'skill':skill,'message':msg})
    return {'counts':{'words':W,'sentences':S,'types':V,'estimated_syllables':syll,'content_words':len(content),'finite_clause_heads':len(heads)},
    'metrics':{'mean_sentence_length':round(W/S,2),'TTR':round(V/W,3),'MATTR_50':None if mattr is None else round(mattr,3),'lexical_density_percent':round(100*len(content)/W,2),'Flesch_Reading_Ease':round(fre,2),'Flesch_Kincaid_Grade':round(fk,2),'finite_clauses_per_sentence_proxy':round(len(heads)/S,2),'dependent_finite_clauses_per_clause_proxy':None if not heads else round(len(dep)/len(heads),3)},
    'sentence_lengths':[{'sentence':s.text,'words':sum(t in tokens for t in s)} for s in spans],
    'syntax_evidence':[{'head':t.text,'relation':t.dep_,'sentence':t.sent.text} for t in heads],
    'flags':flags,'methods':{'tokenizer':f'spaCy {spacy.__version__}; en_core_web_sm {nlp.meta.get("version")}', 'syllables':f'textstat {getattr(textstat,"__version__","installed version")}, en_US, estimated per included token','lexical_density':'NOUN, PROPN, VERB, ADJ, ADV; excludes AUX','syntax':'Finite-head dependency proxy. Inspect head evidence. Not L2SCA and not suitable for unqualified comparison with published L2SCA norms.','grammar':'Five narrow demonstration rules. Zero flags does not mean error-free.','MATTR':'50-word window, lowercased surface forms, undefined for fewer than 50 words.'},
    'warnings':['Descriptive profile, not a proficiency grade.','Compare similar tasks and audiences.','Readability is an English text estimate, not a CEFR or Hong Kong year level.']+(['Sample below 50 words: MATTR unavailable and readability unstable.'] if W<50 else [])}
@app.get('/api/data')
def data():
    source=json.loads((BASE.parent/'03_Data.json').read_text(encoding='utf-8-sig'))
    return {'version':source.get('version'), 'samples':source['samples']}
@app.get('/healthz')
def health():return {'status':'ok'}
@app.post('/api/analyse', dependencies=[Depends(protect_analysis)])
def api_analyse(body:Input):
    try:return analyse(body.text)
    except ValueError as e:raise HTTPException(400,str(e))
@app.get('/')
def home():return FileResponse(BASE/'static/index.html')
app.mount('/static',StaticFiles(directory=BASE/'static'),name='static')
