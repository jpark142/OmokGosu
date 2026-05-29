"""Service layer: business logic that crosses the boundary between the
game engine, DB models, and websocket dispatchers. Pure functions where
possible, all DB writes inside one transaction per call.
"""
