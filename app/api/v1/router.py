from fastapi import APIRouter

router = APIRouter()


@router.get("/hello")
async def hello() -> dict[str, str]:
    return {"message": "Hello from v1"}
