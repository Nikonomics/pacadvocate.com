from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from models.database import get_db
from models.legislation import Bill, BillCreate, BillResponse
from services.legislation.bill_service import BillService

router = APIRouter()

@router.post("/bills/", response_model=BillResponse)
async def create_bill(bill: BillCreate, db: Session = Depends(get_db)):
    bill_service = BillService(db)
    return bill_service.create_bill(bill)

@router.get("/bills/", response_model=List[BillResponse])
async def get_bills(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    bill_service = BillService(db)
    return bill_service.get_bills(skip=skip, limit=limit)

@router.get("/bills/{bill_id}", response_model=BillResponse)
async def get_bill(bill_id: int, db: Session = Depends(get_db)):
    bill_service = BillService(db)
    bill = bill_service.get_bill(bill_id)
    if bill is None:
        raise HTTPException(status_code=404, detail="Bill not found")
    return bill