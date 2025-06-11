from fastapi import APIRouter, status

router = APIRouter()


@router.get("/health_check", status_code=status.HTTP_200_OK)
def health_check() -> dict[str, str]:
    return {"status": "ok"}
