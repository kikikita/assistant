from __future__ import annotations

"""Pydantic models for Tomoru.Team external API (see `tomoru-external-api.yaml`).

Only a subset of the incredibly large original OpenAPI specification is
implemented – enough to comfortably work with the endpoints that are currently
used in the project:

*   `GET  /external-api/user/{userTelegramId}`
*   `PATCH /external-api/user/{userTelegramId}`
*   `GET  /external-api/cities`
*   `GET  /external-api/industries`

The spec introduces a lot of nested discriminated-union objects.  Modelling the
entire tree would result in hundreds of classes that won’t be used right now,
so for the less-important nested structures we fall back to `dict` to keep the
codebase concise.  The public interface is 100 % compatible with the original
schema – all field names are preserved verbatim – so the service can be safely
extended later without breaking changes (just replace `dict` with proper
models if you need stricter typing).

Whenever the OpenAPI marks a field as «required» it’s still declared as
``Optional`` here.  This is intentional: the real-world backend might omit some
values or evolve in time and we prefer resilient parsing over brittle runtime
errors.  If consistency is critical for your use-case – simply enable
``model_config = ConfigDict(strict=True)``.
"""

from datetime import date
from enum import Enum
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


# ============================================================================
# Enumerations
# ============================================================================


class WorkFormat(str, Enum):
    FULL_TIME = "FULL_TIME"
    PROJECT_WORK = "PROJECT_WORK"
    NOT_CONSIDERING = "NOT_CONSIDERING"
    PART_TIME = "PART_TIME"
    INTERNSHIP = "INTERNSHIP"
    ANY = "ANY"


class WorkStatus(str, Enum):
    ACTIVE_SEARCH = "ACTIVE_SEARCH"
    CONSIDERING_OFFERS = "CONSIDERING_OFFERS"
    PART_TIME = "PART_TIME"
    NOT_IN_SEARCH = "NOT_IN_SEARCH"


class WhenReadyForWork(str, Enum):
    RIGHT_AWAY = "RIGHT_AWAY"
    AFTER_1_2_WEEKS = "AFTER_1_2_WEEKS"
    AFTER_3_4_WEEKS = "AFTER_3_4_WEEKS"
    NOT_URGENT = "NOT_URGENT"


class Timezone(str, Enum):
    MSK = "MSK"
    GMT = "GMT"


class WorkMode(str, Enum):
    IN_THE_OFFICE = "IN_THE_OFFICE"
    REMOTE = "REMOTE"
    HYBRID = "HYBRID"
    ITINERANT = "ITINERANT"


class PositionType(str, Enum):
    SALES_MANAGER = "SALES_MANAGER"
    ACCOUNT_MANAGER = "ACCOUNT_MANAGER"
    SUPPORT = "SUPPORT"
    HEAD_OF_SALES = "HEAD_OF_SALES"
    OTHER = "OTHER"


class PositionCategory(str, Enum):
    SALES = "SALES"
    OTHER = "OTHER"


class SalesCycle(str, Enum):
    FAST = "FAST"
    MEDIUM = "MEDIUM"
    LONG = "LONG"


# Lists returned by dedicated endpoints -------------------------------------------------


class City(BaseModel):
    """A city recognised by Tomoru.Team."""

    id: UUID
    name: str
    popular: bool


class GetCitiesListResponseDto(BaseModel):
    list: List[City]


class Industry(BaseModel):
    id: UUID
    title: str
    group: str


class GetIndustriesListResponseDto(BaseModel):
    list: List[Industry]


# User profile -------------------------------------------------------------------------


class _FeatureToggles(BaseModel):
    enableChat: Optional[bool] = None
    enableAIPortrait: Optional[bool] = None
    enableNewResumeUI: Optional[bool] = None


class AiPortraitThesis(BaseModel):
    title: str
    content: str


class ExternalApiGetUserResponseDto(BaseModel):
    cvId: UUID
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    position: Optional[str] = None
    desiredPosition: Optional[str] = None
    citiesList: List[City] = Field(default_factory=list)
    about: Optional[str] = None
    workFormats: Optional[List[WorkFormat]] = None
    avatar: Optional[HttpUrl] = None
    avatarMiniature: Optional[HttpUrl] = None
    readyForColdCalls: Optional[bool] = None
    skills: Optional[List[str]] = None
    workStatus: Optional[WorkStatus] = None
    whenReadyForWork: Optional[WhenReadyForWork] = None
    timezone: Optional[Timezone] = None
    timezoneFrom: Optional[int] = None
    timezoneTo: Optional[int] = None
    salary: Optional[int] = None
    hideSalary: Optional[bool] = None
    birthday: Optional[date] = None
    workModes: Optional[List[WorkMode]] = None
    profileExists: bool = Field(..., description="Flag that indicates whether the user profile exists")
    attributes: Optional[List[Dict]] = None  # see spec for the full discriminated-union structure
    impact: Optional[float] = None
    isNotificationsEnabled: Optional[bool] = None
    hasB2bProfile: bool
    cvExist: bool
    recruitersCheckStatus: Optional[str] = None
    phone: Optional[str] = None
    coverPicture: Optional[HttpUrl] = None
    coverPictureMiniature: Optional[HttpUrl] = None
    hideBirthday: Optional[bool] = None
    positionType: Optional[PositionType] = None
    positionCategory: Optional[PositionCategory] = None
    aiPortraitTheses: Optional[List[AiPortraitThesis]] = None
    salesCycleEnum: Optional[SalesCycle] = None
    profileAvatarUrl: Optional[HttpUrl] = None
    profileAvatarUrlMiniature: Optional[HttpUrl] = None
    featureToggles: Optional[_FeatureToggles] = None
    preferredIndustriesList: Optional[List[Industry]] = None


class ExternalApiUpdateUserRequestDto(BaseModel):
    """Payload accepted by `PATCH /external-api/user/{id}`.

    All fields are optional, so only the values that the caller want to update
    should be passed in.  ``TomoruTeamApiService.update_user`` takes care of
    filtering out unset values before sending the request.
    """

    firstName: Optional[str] = None
    lastName: Optional[str] = None
    position: Optional[str] = None
    positionType: Optional[PositionType] = None
    positionCategory: Optional[PositionCategory] = None
    desiredPosition: Optional[str] = None
    citiesIds: Optional[List[UUID]] = None
    about: Optional[str] = None
    workFormats: Optional[List[WorkFormat]] = None
    avatar: Optional[HttpUrl] = None
    avatarMiniature: Optional[HttpUrl] = None
    readyForColdCalls: Optional[bool] = None
    skills: Optional[List[str]] = None
    workStatus: Optional[WorkStatus] = None
    whenReadyForWork: Optional[WhenReadyForWork] = None
    timezone: Optional[Timezone] = None  # deprecated in the spec but still supported
    timezoneFrom: Optional[int] = None  # deprecated in the spec but still supported
    timezoneTo: Optional[int] = None  # deprecated in the spec but still supported
    salary: Optional[int] = None
    hideSalary: Optional[bool] = None
    birthday: Optional[date] = None
    workModes: Optional[List[WorkMode]] = None
    coverPicture: Optional[HttpUrl] = None
    coverPictureMiniature: Optional[HttpUrl] = None
    profileAvatarUrl: Optional[HttpUrl] = None
    profileAvatarUrlMiniature: Optional[HttpUrl] = None
    hideBirthday: Optional[bool] = None
    salesCycleEnum: Optional[SalesCycle] = None
    phone: Optional[str] = None
    aiPortraitTheses: Optional[List[AiPortraitThesis]] = None
    tools: Optional[List[Dict]] = None
    languages: Optional[List[Dict]] = None
    achievements: Optional[List[Dict]] = None
    educations: Optional[List[Dict]] = None
    experiences: Optional[List[Dict]] = None
    preferredIndustriesIds: Optional[List[UUID]] = None

    def dict(self, *args, **kwargs):  # noqa: D401 (simple override)
        """Alias for ``model_dump`` (Pydantic v2 compatibility shim)."""
        return super().model_dump(*args, **kwargs)
