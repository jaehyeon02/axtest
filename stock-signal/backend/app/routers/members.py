from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Member
from app.schemas import MemberCreate, MemberOut

router = APIRouter(prefix="/members", tags=["회원"])


@router.get("", response_model=list[MemberOut], summary="회원 목록")
def list_members(db: Session = Depends(get_db)):
    return db.scalars(select(Member).order_by(Member.member_id)).all()


@router.post("", response_model=MemberOut, status_code=201, summary="회원 등록 (닉네임만, 로그인 없음)")
def create_member(body: MemberCreate, db: Session = Depends(get_db)):
    member = Member(nickname=body.nickname)
    db.add(member)
    db.commit()  # 닉네임 중복 → 409 (errors.py)
    db.refresh(member)
    return member


@router.delete("/{member_id}", status_code=204, summary="회원 삭제 (관심종목·모의거래도 함께 삭제)")
def delete_member(member_id: int, db: Session = Depends(get_db)):
    member = db.get(Member, member_id)
    if member is None:
        raise HTTPException(404, "존재하지 않는 회원입니다.")
    db.delete(member)  # 하위 데이터는 DB 의 ON DELETE CASCADE 가 지운다
    db.commit()
