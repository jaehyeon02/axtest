"""내 분석 노트 CRUD. 노트에는 근거(뉴스·공시 또는 주가 변동일)를 여러 개 담을 수 있어요."""
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import client_id
from ..models import Company, Document, Note, NoteEvidence, PriceDaily
from ..schemas import DocumentOut, EvidenceComment, EvidenceIn, EvidenceOut, EvidencePrice, NoteIn, NoteOut, NoteUpdate

router = APIRouter(prefix="/api/notes", tags=["notes"])


def _doc_out(d: Document) -> DocumentOut:
    out = DocumentOut.model_validate(d)
    out.user_added = d.created_by is not None
    return out


def _evidence_out(db: Session, e: NoteEvidence) -> EvidenceOut:
    if e.document is not None:
        return EvidenceOut(evidence_id=e.evidence_id, kind="document", comment=e.comment, document=_doc_out(e.document))
    p = e.price
    prev = db.scalar(
        select(PriceDaily.close).where(PriceDaily.company_id == p.company_id, PriceDaily.trade_date < p.trade_date)
        .order_by(desc(PriceDaily.trade_date)).limit(1)
    )
    ret = round((float(p.close) / float(prev) - 1) * 100, 2) if prev else None
    return EvidenceOut(evidence_id=e.evidence_id, kind="price", comment=e.comment,
                       price=EvidencePrice(price_id=p.price_id, trade_date=p.trade_date, close=float(p.close), ret_pct=ret))


def _out(db: Session, n: Note) -> NoteOut:
    return NoteOut(note_id=n.note_id, company_code=n.company.code, company_name=n.company.name, title=n.title, memo=n.memo,
                   stance=n.stance, created_at=n.created_at, updated_at=n.updated_at,
                   evidence=[_evidence_out(db, e) for e in n.evidence])


def _mine(db: Session, note_id: int, cid: str) -> Note:
    n = db.get(Note, note_id)
    if not n or n.client_id != cid:  # 남의 노트는 "없는 것"처럼 보이게 해요.
        raise HTTPException(404, "노트를 찾을 수 없어요.")
    return n


@router.get("", response_model=List[NoteOut])
def list_notes(company_code: str = Query("", max_length=12), cid: str = Depends(client_id), db: Session = Depends(get_db)):
    q = select(Note).where(Note.client_id == cid).options(selectinload(Note.evidence)).order_by(desc(Note.updated_at))
    if company_code:
        q = q.join(Company).where(Company.code == company_code)
    return [_out(db, n) for n in db.scalars(q).all()]


@router.post("", response_model=NoteOut, status_code=201)
def create_note(body: NoteIn, cid: str = Depends(client_id), db: Session = Depends(get_db)):
    company = db.scalar(select(Company).where(Company.code == body.company_code))
    if not company:
        raise HTTPException(404, "종목을 찾을 수 없어요.")
    now = datetime.now()
    n = Note(client_id=cid, company_id=company.company_id, title=body.title, memo=body.memo, stance=body.stance, created_at=now, updated_at=now)
    db.add(n)
    db.commit()
    db.refresh(n)
    return _out(db, n)


@router.get("/{note_id}", response_model=NoteOut)
def get_note(note_id: int, cid: str = Depends(client_id), db: Session = Depends(get_db)):
    return _out(db, _mine(db, note_id, cid))


@router.put("/{note_id}", response_model=NoteOut)
def update_note(note_id: int, body: NoteUpdate, cid: str = Depends(client_id), db: Session = Depends(get_db)):
    n = _mine(db, note_id, cid)
    for key, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(n, key, value)
    n.updated_at = datetime.now()
    db.commit()
    db.refresh(n)
    return _out(db, n)


@router.delete("/{note_id}", status_code=204)
def delete_note(note_id: int, cid: str = Depends(client_id), db: Session = Depends(get_db)):
    db.delete(_mine(db, note_id, cid))
    db.commit()


@router.post("/{note_id}/evidence", response_model=NoteOut, status_code=201)
def add_evidence(note_id: int, body: EvidenceIn, cid: str = Depends(client_id), db: Session = Depends(get_db)):
    n = _mine(db, note_id, cid)
    if (body.doc_id is None) == (body.price_id is None):
        raise HTTPException(422, "doc_id 와 price_id 중 하나만 보내 주세요.")
    if body.doc_id is not None:
        d = db.get(Document, body.doc_id)
        if not d or d.company_id != n.company_id or (d.created_by not in (None, cid)):
            raise HTTPException(404, "이 종목의 문서를 찾을 수 없어요.")
    else:
        p = db.get(PriceDaily, body.price_id)
        if not p or p.company_id != n.company_id:
            raise HTTPException(404, "이 종목의 주가 기록을 찾을 수 없어요.")
    if any((e.doc_id and e.doc_id == body.doc_id) or (e.price_id and e.price_id == body.price_id) for e in n.evidence):
        raise HTTPException(409, "이미 담은 근거예요.")
    db.add(NoteEvidence(note_id=n.note_id, doc_id=body.doc_id, price_id=body.price_id, comment=body.comment))
    n.updated_at = datetime.now()
    db.commit()
    db.refresh(n)
    return _out(db, n)


@router.delete("/{note_id}/evidence/{evidence_id}", response_model=NoteOut)
def remove_evidence(note_id: int, evidence_id: int, cid: str = Depends(client_id), db: Session = Depends(get_db)):
    n = _mine(db, note_id, cid)
    e = next((x for x in n.evidence if x.evidence_id == evidence_id), None)
    if not e:
        raise HTTPException(404, "근거를 찾을 수 없어요.")
    n.evidence.remove(e)
    n.updated_at = datetime.now()
    db.commit()
    db.refresh(n)
    return _out(db, n)


@router.put("/{note_id}/evidence/{evidence_id}", response_model=NoteOut)
def update_evidence(note_id: int, evidence_id: int, body: EvidenceComment, cid: str = Depends(client_id), db: Session = Depends(get_db)):
    """근거에 내 한 줄 코멘트를 달거나 고쳐요."""
    n = _mine(db, note_id, cid)
    e = next((x for x in n.evidence if x.evidence_id == evidence_id), None)
    if not e:
        raise HTTPException(404, "근거를 찾을 수 없어요.")
    e.comment = body.comment
    n.updated_at = datetime.now()
    db.commit()
    db.refresh(n)
    return _out(db, n)
