from enum import Enum


class SeasonStatus(str, Enum):
    DRAFT = "DRAFT"
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class RuleStatus(str, Enum):
    DRAFT = "DRAFT"
    LOCKED = "LOCKED"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"


class GameStatus(str, Enum):
    IN_PROGRESS = "IN_PROGRESS"
    ACTIVE = "ACTIVE"
    CANCELED = "CANCELED"


class GameSide(str, Enum):
    A = "A"
    B = "B"


class GameSource(str, Enum):
    TEAM_BUILDER = "team_builder"
    MANUAL = "manual"
    LEGACY_IMPORT = "legacy_import"


class Permission(str, Enum):
    GAME_CREATE = "game:create"
    GAME_CANCEL = "game:cancel"
    GAME_RESTORE = "game:restore"
    MMR_MANAGE = "mmr:manage"
    SEASON_MANAGE = "season:manage"
    NOTICE_MANAGE = "notice:manage"
    ADMIN_MANAGE = "admin:manage"
    PLAYER_MANAGE = "player:manage"


ALL_PERMISSIONS = frozenset(permission.value for permission in Permission)
