from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import RadarPredictRequest, RadarPredictResponse
from ..services.radar import predict_adjustment_rate

router = APIRouter(prefix="/radar", tags=["radar"])


@router.post("/predict", response_model=RadarPredictResponse)
def predict_radar(payload: RadarPredictRequest, db: Session = Depends(get_db)) -> RadarPredictResponse:
    try:
        result = predict_adjustment_rate(
            db,
            score=payload.score,
            category=payload.category,
            area=payload.area,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return RadarPredictResponse(**result.__dict__)
