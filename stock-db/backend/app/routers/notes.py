from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Company, Note
from app.schemas import NoteCreate, NoteOut, NoteUpdate

router = APIRouter(prefix="/notes", tags=["종목 메모"])


def _get_note_or_404(db: Session, note_id: int) -> Note:
    note = db.get(Note, note_id)
    if note is None:
        raise HTTPException(404, "존재하지 않는 메모입니다.")
    return note


@router.get("", response_model=list[NoteOut], summary="메모 목록 (최신순)")
def list_notes(
    company_id: int | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    stmt = select(Note).order_by(Note.created_at.desc(), Note.note_id.desc()).limit(limit)
    if company_id is not None:
        stmt = stmt.where(Note.company_id == company_id)
    return db.scalars(stmt).all()


@router.get("/{note_id}", response_model=NoteOut, summary="메모 1건 조회")
def get_note(note_id: int, db: Session = Depends(get_db)):
    return _get_note_or_404(db, note_id)


@router.post("", response_model=NoteOut, status_code=201, summary="메모 등록")
def create_note(body: NoteCreate, db: Session = Depends(get_db)):
    if db.get(Company, body.company_id) is None:
        raise HTTPException(404, "존재하지 않는 종목입니다.")
    note = Note(**body.model_dump())
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.put("/{note_id}", response_model=NoteOut, summary="메모 수정 (보낸 항목만)")
def update_note(note_id: int, body: NoteUpdate, db: Session = Depends(get_db)):
    note = _get_note_or_404(db, note_id)
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, "수정할 항목이 없습니다.")
    for key, value in changes.items():
        setattr(note, key, value)
    db.commit()
    db.refresh(note)
    return note


@router.delete("/{note_id}", status_code=204, summary="메모 삭제")
def delete_note(note_id: int, db: Session = Depends(get_db)):
    note = _get_note_or_404(db, note_id)
    db.delete(note)
    db.commit()
