from fastapi import FastAPI, HTTPException
from api.schemas import ReceiveRequest, OperationResponse
# Import your automation classes

app = FastAPI(title="RF Automation API")

@app.post("/receive", response_model=OperationResponse)
async def receive_item(request: ReceiveRequest):
    """Execute receiving operation via API"""
    try:
        # Initialize browser and run operation
        # with BrowserManager() as browser_mgr:
        #     page = browser_mgr.new_page()
        #     ... execute receive operation
        return OperationResponse(
            success=True,
            message=f"Successfully received {request.quantity} units of {request.item}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy"}