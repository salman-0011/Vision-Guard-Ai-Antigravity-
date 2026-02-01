"""
VisionGuard AI - Camera API Routes

Endpoints for camera registration and control.
POST /cameras/register
POST /cameras/{id}/start
POST /cameras/{id}/stop
GET  /cameras/status
GET  /cameras/{id}/status
DELETE /cameras/{id}
"""

from fastapi import APIRouter, Depends, HTTPException, Path

from app.services.camera_manager import get_camera_manager, CameraManager
from app.models.cameras import (
    CameraRegisterRequest,
    CameraResponse,
    CameraStatusResponse,
    AllCamerasStatusResponse
)
from app.utils.logging import get_logger

router = APIRouter(prefix="/cameras", tags=["Cameras"])
logger = get_logger(__name__)


@router.post("/register", response_model=CameraResponse)
async def register_camera(
    request: CameraRegisterRequest,
    camera_manager: CameraManager = Depends(get_camera_manager)
) -> CameraResponse:
    """
    Register a new camera.
    
    Camera must be registered before it can be started.
    Registration validates the camera configuration but does not
    connect to the stream.
    """
    logger.info(f"Registering camera: {request.camera_id}")
    
    result = camera_manager.register(
        camera_id=request.camera_id,
        rtsp_url=request.rtsp_url,
        fps=request.fps,
        motion_threshold=request.motion_threshold
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail=result["message"]
        )
    
    return CameraResponse(**result)


@router.delete("/{camera_id}", response_model=CameraResponse)
async def unregister_camera(
    camera_id: str = Path(..., description="Camera ID to unregister"),
    camera_manager: CameraManager = Depends(get_camera_manager)
) -> CameraResponse:
    """
    Unregister a camera.
    
    Camera must be stopped before unregistering.
    """
    logger.info(f"Unregistering camera: {camera_id}")
    
    result = camera_manager.unregister(camera_id)
    
    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail=result["message"]
        )
    
    return CameraResponse(**result)


@router.post("/{camera_id}/start", response_model=CameraResponse)
async def start_camera(
    camera_id: str = Path(..., description="Camera ID to start"),
    camera_manager: CameraManager = Depends(get_camera_manager)
) -> CameraResponse:
    """
    Start a registered camera.
    
    Begins capturing frames from the RTSP stream and processing
    through the motion detection pipeline.
    """
    logger.info(f"Starting camera: {camera_id}")
    
    result = await camera_manager.start_camera(camera_id)
    
    if not result["success"]:
        raise HTTPException(
            status_code=500,
            detail=result["message"]
        )
    
    return CameraResponse(**result)


@router.post("/{camera_id}/stop", response_model=CameraResponse)
async def stop_camera(
    camera_id: str = Path(..., description="Camera ID to stop"),
    camera_manager: CameraManager = Depends(get_camera_manager)
) -> CameraResponse:
    """
    Stop a running camera.
    
    Gracefully stops the camera capture process.
    """
    logger.info(f"Stopping camera: {camera_id}")
    
    result = await camera_manager.stop_camera(camera_id)
    
    if not result["success"]:
        raise HTTPException(
            status_code=500,
            detail=result["message"]
        )
    
    return CameraResponse(**result)


@router.post("/start-all", response_model=CameraResponse)
async def start_all_cameras(
    camera_manager: CameraManager = Depends(get_camera_manager)
) -> CameraResponse:
    """
    Start all registered cameras.
    """
    logger.info("Starting all cameras")
    
    result = await camera_manager.start_all()
    
    return CameraResponse(
        success=result["success"],
        message=result["message"],
        camera=None
    )


@router.post("/stop-all", response_model=CameraResponse)
async def stop_all_cameras(
    camera_manager: CameraManager = Depends(get_camera_manager)
) -> CameraResponse:
    """
    Stop all running cameras.
    """
    logger.info("Stopping all cameras")
    
    result = await camera_manager.stop_all()
    
    return CameraResponse(
        success=result["success"],
        message=result["message"],
        camera=None
    )


@router.get("/status")
async def get_all_cameras_status(
    camera_manager: CameraManager = Depends(get_camera_manager)
) -> dict:
    """
    Get status of all registered cameras.
    """
    return camera_manager.get_all_status()


@router.get("/{camera_id}/status")
async def get_camera_status(
    camera_id: str = Path(..., description="Camera ID"),
    camera_manager: CameraManager = Depends(get_camera_manager)
) -> dict:
    """
    Get status of a specific camera.
    """
    status = camera_manager.get_camera_status(camera_id)
    
    if status is None:
        raise HTTPException(
            status_code=404,
            detail=f"Camera {camera_id} not found"
        )
    
    return status
