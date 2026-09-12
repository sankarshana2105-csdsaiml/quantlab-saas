import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from quantlab.auth import AuthService, AuthServiceError, DuplicateEmail, InvalidCredentials
from quantlab.config import Settings

from .auth_routes import router as auth_router
from .routes import router
from .service import ApiInputError, PersistenceError, QuantService, ResourceNotFound


logger = logging.getLogger("quantlab.api")


def create_app(service: QuantService | None = None, auth_service: AuthService | None = None) -> FastAPI:
    settings = Settings.from_environment()
    application = FastAPI(
        title="QuantLab API",
        version="0.1.0",
        description="Local-first API for validated OHLCV data and next-open quantitative backtests.",
    )
    if settings.allowed_hosts:
        application.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))
    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=False,
            allow_methods=["GET", "POST", "DELETE"], allow_headers=["Authorization", "Content-Type"],
        )
    application.state.quant_service = service or QuantService()
    application.state.auth_service = auth_service or AuthService(application.state.quant_service.repository)
    application.state.settings = settings
    application.include_router(auth_router)
    application.include_router(router)

    @application.exception_handler(InvalidCredentials)
    async def invalid_credentials(_: Request, exc: InvalidCredentials) -> JSONResponse:
        return JSONResponse(
            status_code=401, content={"detail": str(exc)}, headers={"WWW-Authenticate": "Bearer"},
        )

    @application.exception_handler(DuplicateEmail)
    async def duplicate_email(_: Request, exc: DuplicateEmail) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @application.exception_handler(AuthServiceError)
    async def auth_unavailable(_: Request, __: AuthServiceError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": "Authentication service unavailable"})

    @application.exception_handler(ApiInputError)
    async def input_error(_: Request, exc: ApiInputError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @application.exception_handler(ResourceNotFound)
    async def not_found(_: Request, exc: ResourceNotFound) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @application.exception_handler(PersistenceError)
    async def persistence_error(_: Request, __: PersistenceError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": "Persistence service unavailable"})

    @application.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled API error on %s %s", request.method, request.url.path, exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    return application


app = create_app()
