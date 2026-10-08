"""내 자료(기사·메모) 추가/수정/삭제. 수집된 공시는 건드릴 수 없고, 내가 추가한 자료만 바꿀 수 있어요."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import client_id
from ..models import Company, Document
from ..schemas import DocumentIn, DocumentOut, DocumentUpdate

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _out(d: Document) -> DocumentOut:
    out = DocumentOut.model_validate(d)
    out.user_added = d.created_by is not None
    return out


def _mine(db: Session, doc_id: int, cid: str) -> Document:
    d = db.get(Document, doc_id)
    if not d:
        raise HTTPException(404, "문서를 찾을 수 없어요.")
    if d.created_by != cid:
        raise HTTPException(403, "내가 추가한 문서만 수정·삭제할 수 있어요.")
    return d


@router.post("", response_model=DocumentOut, status_code=201)
def create(body: DocumentIn, cid: str = Depends(client_id), db: Session = Depends(get_db)):
    company = db.scalar(select(Company).where(Company.code == body.company_code))
    if not company:
        raise HTTPException(404, "종목을 찾을 수 없어요.")
    d = Document(company_id=company.company_id, doc_type="news", title=body.title, body=body.body,
                 source=body.source, url=body.url, sentiment=body.sentiment, published_date=body.published_date, created_by=cid)
    db.add(d)
    db.commit()
    db.refresh(d)
    return _out(d)


@router.put("/{doc_id}", response_model=DocumentOut)
def update(doc_id: int, body: DocumentUpdate, cid: str = Depends(client_id), db: Session = Depends(get_db)):
    d = _mine(db, doc_id, cid)
    for key, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(d, key, value)
    db.commit()
    db.refresh(d)
    return _out(d)


@router.delete("/{doc_id}", status_code=204)
def delete(doc_id: int, cid: str = Depends(client_id), db: Session = Depends(get_db)):
    db.delete(_mine(db, doc_id, cid))
    db.commit()
