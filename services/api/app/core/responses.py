from starlette.responses import JSONResponse


class UTF8JSONResponse(JSONResponse):
    """Make the JSON character encoding explicit at every API boundary."""

    media_type = "application/json; charset=utf-8"
