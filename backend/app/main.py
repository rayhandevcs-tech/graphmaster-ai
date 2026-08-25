"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.v1.router import api_router
from app.assessment.registry import warm_up as warm_up_assessment
from app.core.config import get_settings
from app.core.exceptions import GraphMasterError, RateLimitError
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestIDMiddleware, SecurityHeadersMiddleware
from app.nlp.pipeline import warm_up as warm_up_nlp
from app.ocr.chain import OCRChain
from app.ocr.factory import get_ocr_chain

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown.

    Expensive singletons (the OCR provider chain, the spaCy pipeline) are
    initialised here rather than per request — both load models measured in tens
    of megabytes, and constructing them per request would add seconds to every
    call. They are registered by their own sprints.
    """
    settings = get_settings()
    configure_logging()
    logger.info("Starting %s v%s (%s)", settings.PROJECT_NAME, __version__, settings.ENVIRONMENT)

    # Probe provider availability once, here, rather than per upload: it is a
    # configuration question whose answer cannot change within a process
    # lifetime, and probing Google Vision per request would add a network round
    # trip to every submission (07-ocr-architecture.md §3.1).
    chain = get_ocr_chain()
    if not chain.is_operational:
        logger.warning(
            "No OCR provider is available. Handwriting upload will be refused; "
            "typed answers are unaffected."
        )
    else:
        _warm_up_ocr(chain)

    # Loading the spaCy model and running one throwaway parse. Analysis is not
    # optional the way OCR is — without it nothing can be scored — but a
    # missing model still must not stop the server: students can then still
    # sign in, read their history and practise, and the operator sees one
    # actionable warning instead of every submission failing at 500.
    if not warm_up_nlp():
        logger.warning(
            "The analysis engine is unavailable. Scoring will return 503 until the "
            "spaCy model is installed."
        )

    # The diagnostic analyzers' own preloading — a megabyte of spelling
    # dictionary, and whatever the provider-backed ones need. Same reason as
    # above: without it the cost lands on whichever student submits first.
    warm_up_assessment()

    yield
    logger.info("Shutting down %s", settings.PROJECT_NAME)


def _warm_up_ocr(chain: OCRChain) -> None:
    """Load recognition models during boot.

    Otherwise the several seconds of model loading land on whichever student
    happens to upload first, and count against the 10-second budget of
    NFR-1.3 for that one unlucky request.
    """
    for provider in chain.available_providers:
        warm_up = getattr(provider, "warm_up", None)
        if warm_up is None:
            continue
        try:
            warm_up()
        except Exception as exc:
            logger.warning("Could not warm up OCR provider %s: %s", provider.name, exc)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=(
            "AI-powered gamified graph description learning platform. "
            "Students describe charts by typing or by uploading handwriting; "
            "responses are scored on graph-description vocabulary usage and "
            "rewarded with animated gamified feedback."
        ),
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Order matters: middleware added last runs first, so the request ID is
    # set before anything else can log.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,  # the refresh-token cookie needs this
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    _register_exception_handlers(app)

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "name": settings.PROJECT_NAME,
            "version": __version__,
            "docs": "/docs",
            "health": f"{settings.API_V1_PREFIX}/health/live",
        }

    return app


def _register_exception_handlers(app: FastAPI) -> None:
    """Map every error to the envelope in docs/architecture/04-api-design.md §5.2.

    Centralised here so the domain-to-HTTP mapping exists once, rather than
    being repeated in each router.
    """

    @app.exception_handler(GraphMasterError)
    async def handle_domain_error(request: Request, exc: GraphMasterError) -> JSONResponse:
        headers: dict[str, str] = {}
        if isinstance(exc, RateLimitError):
            headers["Retry-After"] = str(exc.retry_after)

        log = logger.warning if exc.status_code < 500 else logger.error
        log("%s: %s", exc.code, exc.message)

        return JSONResponse(status_code=exc.status_code, content=exc.to_dict(), headers=headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Reshaped into the same envelope so clients parse one error format.
        fields: dict[str, str] = {}
        for error in exc.errors():
            location = ".".join(str(p) for p in error["loc"] if p != "body")
            fields[location or "body"] = error["msg"]

        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "The request could not be processed.",
                    "details": {"fields": fields},
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        codes = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": codes.get(exc.status_code, "HTTP_ERROR"),
                    "message": str(exc.detail),
                    "details": {},
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "-")
        logger.exception("Unhandled error [%s]: %s", request_id, exc)
        # The traceback is logged, never returned: a stack trace in a response
        # body discloses internal structure to anyone who can trigger an error.
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred.",
                    "details": {"request_id": request_id},
                }
            },
        )


app = create_app()
